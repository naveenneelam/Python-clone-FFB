"""OpenFFBoard CDC command codec and value scaling.

OpenFFBoard exposes a line-oriented command interface over USB CDC/UART.  The
wire grammar is public and documented at:

https://github.com/Ultrawipf/OpenFFBoard/wiki/Commands

Request examples::

    axis.0.power?        -> [axis.0.power?|22937]
    axis.0.power=20000   -> [axis.0.power=20000|OK]
    sys.save             -> [sys.save|OK]

This module only implements the grammar used by PyFFB.  It contains no EMC
code or reverse-engineered private protocol.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

COMMAND_TERMINATOR = "\r\n"
_PATH_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.]*$")
_MAX_LINE = 4096


class ProtocolError(ValueError):
    """Malformed command or reply."""


class ReplyKind(str, Enum):
    GET = "get"
    SET = "set"
    EXECUTE = "execute"
    NOTIFICATION = "notification"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Reply:
    raw: str
    kind: ReplyKind
    path: str = ""
    value: str | None = None
    status: str = ""
    sent_value: str | None = None

    @property
    def ok(self) -> bool:
        return self.status != "ERR" and self.status != "ERROR"

    def as_int(self, default: int | None = None) -> int | None:
        parsed = parse_int(self.value)
        return default if parsed is None else parsed

    def as_float(self, default: float | None = None) -> float | None:
        parsed = parse_float(self.value)
        return default if parsed is None else parsed

    def as_bool(self, default: bool | None = None) -> bool | None:
        if self.value is None:
            return default
        text = self.value.strip().lower()
        if text in {"1", "true", "on", "yes"}:
            return True
        if text in {"0", "false", "off", "no"}:
            return False
        return default


def _check_path(path: str) -> str:
    path = path.strip()
    if not _PATH_RE.match(path):
        raise ProtocolError(f"invalid command path: {path!r}")
    return path


def _check_value(value: object) -> str:
    text = str(value).strip()
    if not text or "\r" in text or "\n" in text or "|" in text:
        raise ProtocolError(f"invalid command value: {value!r}")
    return text


def format_get(path: str) -> str:
    return f"{_check_path(path)}?{COMMAND_TERMINATOR}"


def format_set(path: str, value: object) -> str:
    return f"{_check_path(path)}={_check_value(value)}{COMMAND_TERMINATOR}"


def format_execute(path: str) -> str:
    return f"{_check_path(path)}{COMMAND_TERMINATOR}"


def format_set_at(path: str, value: object, address: object) -> str:
    return (
        f"{_check_path(path)}={_check_value(value)}?{_check_value(address)}"
        f"{COMMAND_TERMINATOR}"
    )


def format_get_at(path: str, address: object) -> str:
    return f"{_check_path(path)}?{_check_value(address)}{COMMAND_TERMINATOR}"


def format_raw(text: str) -> str:
    """Turn user-entered console text into a terminated command."""

    text = text.strip()
    if not text:
        raise ProtocolError("empty command")
    if text.endswith("\r\n"):
        text = text[:-2]
    elif text.endswith(("\r", "\n")):
        text = text[:-1]
    if any(ch in text for ch in "\r\n"):
        raise ProtocolError("command must be a single line")
    if text.startswith("["):
        raise ProtocolError("enter a command, not a reply")
    return text + COMMAND_TERMINATOR


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if text.lower().startswith("x"):
            return int(text[1:], 16)
        if text.lower().startswith("0x"):
            return int(text[2:], 16)
        return int(text, 10)
    except ValueError:
        return None


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def parse_line(line: str) -> Reply | None:
    """Parse one serial line, tolerating boot logs and partial noise."""

    raw = line.rstrip("\r\n")
    if not raw.strip():
        return None
    if len(raw) > _MAX_LINE:
        return Reply(raw=raw[:_MAX_LINE], kind=ReplyKind.UNKNOWN)
    text = raw.strip()
    if not text.startswith("["):
        return Reply(raw=raw, kind=ReplyKind.UNKNOWN)
    end = text.rfind("]")
    if end <= 0:
        return Reply(raw=raw, kind=ReplyKind.UNKNOWN)
    body = text[1:end]
    left, sep, right = body.partition("|")
    left = left.strip()
    value = right.strip() if sep else None
    status = ""
    if value is not None and value.upper() in {"OK", "ERR", "ERROR"}:
        status = value.upper()
        if status in {"OK", "ERR", "ERROR"}:
            # For a SET reply the right side is an acknowledgement, not data.
            value = None
    if left.endswith("?"):
        return Reply(
            raw=raw,
            kind=ReplyKind.GET,
            path=left[:-1],
            value=value,
            status=status,
        )
    if "=" in left:
        path, sent = left.split("=", 1)
        return Reply(
            raw=raw,
            kind=ReplyKind.SET,
            path=path,
            sent_value=sent,
            value=None,
            status=status or (value or ""),
        )
    return Reply(
        raw=raw,
        kind=ReplyKind.EXECUTE if sep else ReplyKind.NOTIFICATION,
        path=left,
        value=value,
        status=status,
    )


def pct_to_raw(value: int | float, maximum: int) -> int:
    """Map 0..100 percent to a 0..maximum integer, rounded and clipped."""

    pct = max(0.0, min(100.0, float(value)))
    return int(round(pct / 100.0 * maximum))


def raw_to_pct(value: int | float, maximum: int) -> int:
    if maximum <= 0:
        return 0
    return int(round(max(0.0, min(float(maximum), float(value))) / maximum * 100.0))


def pct_to_u8(value: int | float) -> int:
    return pct_to_raw(value, 255)


def u8_to_pct(value: int | float) -> int:
    return raw_to_pct(value, 255)


def pct_to_15bit(value: int | float) -> int:
    return pct_to_raw(value, 32767)


def value_15bit_to_pct(value: int | float) -> int:
    return raw_to_pct(value, 32767)


def signed_pct_to_15bit(value: int | float) -> int:
    pct = max(-100.0, min(100.0, float(value)))
    return int(round(pct / 100.0 * 32767))


def signed_15bit_to_pct(value: int | float) -> float:
    return max(-100.0, min(100.0, float(value) / 32767.0 * 100.0))


def command_path_for(field_name: str) -> str:
    """Return the raw command for a canonical field (diagnostics helper)."""

    from .backends.openffboard import FIELD_MAP

    try:
        return FIELD_MAP[field_name].path
    except KeyError as exc:
        raise ProtocolError(f"field has no OpenFFBoard mapping: {field_name}") from exc
