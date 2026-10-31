"""OpenFFBoard USB-CDC backend.

PyFFB talks to OpenFFBoard's public ASCII command interface.  It deliberately
does not touch motor driver, encoder, current limit, brake resistor or flash
layout commands.  Those are hardware-commissioning operations and remain the
responsibility of OpenFFBoard's own configurator.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from ..models import (
    BackendDescriptor,
    DeviceInfo,
    SettingsRead,
    Telemetry,
    WheelSettings,
)
from ..protocol import (
    ProtocolError,
    Reply,
    ReplyKind,
    format_execute,
    format_get,
    format_raw,
    format_set,
    parse_line,
    pct_to_15bit,
    pct_to_u8,
    raw_to_pct,
    u8_to_pct,
)
from .base import (
    BackendCommandError,
    BackendError,
    BackendTimeout,
    BackendUnavailable,
    WheelBackend,
)

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 0.9
CONNECT_TIMEOUT = 2.5


@dataclass(frozen=True)
class FieldSpec:
    path: str
    raw_max: int | None = None
    boolean: bool = False


# Canonical model field -> OpenFFBoard command.  ``raw_max`` means the UI value
# is a percentage that must be scaled to 0..raw_max.
FIELD_MAP: dict[str, FieldSpec] = {
    "power_pct": FieldSpec("axis.0.power", raw_max=32767),
    "rotation_deg": FieldSpec("axis.0.degrees"),
    "invert": FieldSpec("axis.0.invert", boolean=True),
    "endstop_pct": FieldSpec("axis.0.esgain", raw_max=255),
    "idle_spring_pct": FieldSpec("axis.0.idlespring", raw_max=255),
    "global_damper_pct": FieldSpec("axis.0.axisdamper", raw_max=255),
    "global_friction_pct": FieldSpec("axis.0.axisfriction", raw_max=255),
    "global_inertia_pct": FieldSpec("axis.0.axisinertia", raw_max=255),
    "game_effect_ratio_pct": FieldSpec("axis.0.fxratio", raw_max=255),
    "max_speed_dps": FieldSpec("axis.0.maxspeed"),
    "torque_rate": FieldSpec("axis.0.maxtorquerate"),
    "expo": FieldSpec("axis.0.expo"),
    "spring_gain_pct": FieldSpec("fx.0.spring", raw_max=255),
    "damper_gain_pct": FieldSpec("fx.0.damper", raw_max=255),
    "friction_gain_pct": FieldSpec("fx.0.friction", raw_max=255),
    "inertia_gain_pct": FieldSpec("fx.0.inertia", raw_max=255),
    "friction_ramp_pct": FieldSpec("fx.0.frictionPctSpeedToRampup"),
    "constant_filter_hz": FieldSpec("fx.0.filterCfFreq"),
    "constant_filter_q": FieldSpec("fx.0.filterCfQ"),
    "condition_filters_enabled": FieldSpec("fx.0.filterProfile_id", boolean=True),
    "condition_friction_hz": FieldSpec("fx.0.friction_f"),
    "condition_friction_q": FieldSpec("fx.0.friction_q"),
    "condition_damper_hz": FieldSpec("fx.0.damper_f"),
    "condition_damper_q": FieldSpec("fx.0.damper_q"),
    "condition_inertia_hz": FieldSpec("fx.0.inertia_f"),
    "condition_inertia_q": FieldSpec("fx.0.inertia_q"),
}

# Writing gains/conditioning before geometry and power reduces the chance of a
# sudden force transient.  Power is handled separately so it can be moved down
# first and up last.
WRITE_ORDER: tuple[str, ...] = (
    "spring_gain_pct",
    "damper_gain_pct",
    "friction_gain_pct",
    "inertia_gain_pct",
    "friction_ramp_pct",
    "endstop_pct",
    "idle_spring_pct",
    "global_damper_pct",
    "global_friction_pct",
    "global_inertia_pct",
    "rotation_deg",
    "invert",
    "game_effect_ratio_pct",
    "max_speed_dps",
    "torque_rate",
    "expo",
    "constant_filter_hz",
    "constant_filter_q",
    "condition_friction_hz",
    "condition_friction_q",
    "condition_damper_hz",
    "condition_damper_q",
    "condition_inertia_hz",
    "condition_inertia_q",
    "condition_filters_enabled",
)

CONDITION_FILTER_FIELDS: tuple[str, ...] = (
    "condition_friction_hz",
    "condition_friction_q",
    "condition_damper_hz",
    "condition_damper_q",
    "condition_inertia_hz",
    "condition_inertia_q",
)


def encode_field(field: str, settings: WheelSettings) -> int:
    spec = FIELD_MAP[field]
    value = getattr(settings, field)
    if spec.boolean:
        return 1 if bool(value) else 0
    if spec.raw_max is not None:
        if spec.raw_max == 255:
            return pct_to_u8(int(value))
        if spec.raw_max == 32767:
            return pct_to_15bit(int(value))
        return int(round(int(value) / 100.0 * spec.raw_max))
    return int(value)


def decode_field(field: str, raw: int) -> int | bool:
    spec = FIELD_MAP[field]
    if spec.boolean:
        return bool(raw)
    if spec.raw_max == 255:
        return u8_to_pct(raw)
    if spec.raw_max == 32767:
        return raw_to_pct(raw, 32767)
    return int(raw)


class OpenFFBoardBackend(WheelBackend):
    key = "openffboard"
    display_name = "OpenFFBoard (USB CDC)"
    supports_save = True

    def __init__(self, baudrate: int = 115200) -> None:
        self.baudrate = baudrate
        self._serial = None
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()
        self._connected = False
        self._closing = False
        self._info: DeviceInfo | None = None
        self._io_lock = threading.RLock()
        self._cv = threading.Condition(self._io_lock)
        self._inbox: deque[Reply] = deque(maxlen=1024)
        self._ignored: deque[str] = deque(maxlen=100)
        self._last_error = ""

    # ------------------------------------------------------------------ ports
    @classmethod
    def list_devices(cls) -> list[BackendDescriptor]:
        try:
            from serial.tools import list_ports
        except ImportError:
            return []
        result: list[BackendDescriptor] = []
        for port in sorted(list_ports.comports(), key=lambda item: item.device):
            description = " ".join(
                part
                for part in (getattr(port, "manufacturer", None), getattr(port, "product", None))
                if part
            ) or (getattr(port, "description", "") or "Serial port")
            result.append(
                BackendDescriptor(
                    key=cls.key,
                    display_name=description,
                    port=port.device,
                    description=getattr(port, "description", "") or "",
                    hwid=getattr(port, "hwid", "") or "",
                )
            )
        return result

    # --------------------------------------------------------------- lifecycle
    def connect(self, port: str = "") -> DeviceInfo:
        if not port:
            raise BackendError("select a serial port")
        try:
            import serial
        except ImportError as exc:
            raise BackendUnavailable(
                "pyserial is not installed. Run: pip install pyserial"
            ) from exc
        self.disconnect()
        self._stop.clear()
        self._closing = False
        self._last_error = ""
        try:
            self._serial = serial.Serial(
                port=port,
                baudrate=self.baudrate,
                timeout=0.05,
                write_timeout=0.75,
            )
        except Exception as exc:
            self._serial = None
            raise BackendError(f"cannot open {port}: {exc}") from exc

        self._reader = threading.Thread(
            target=self._reader_loop,
            name="openffboard-reader",
            daemon=True,
        )
        self._reader.start()
        self._connected = True
        try:
            firmware = self._probe_identity()
            hardware = self._optional_query("sys.hwtype")
            info = DeviceInfo(
                backend_key=self.key,
                display_name="OpenFFBoard",
                port=port,
                firmware=firmware,
                hardware="" if hardware is None else str(hardware),
            )
            self._info = info
            log.info("Connected to OpenFFBoard on %s (firmware %s)", port, firmware)
            return info
        except Exception:
            self.disconnect()
            raise

    def _probe_identity(self) -> str:
        reply = self._request("sys.swver", "get", CONNECT_TIMEOUT, "sys.swver")
        if reply is None or not reply.ok:
            raise BackendTimeout(
                "the port did not answer the OpenFFBoard version query; "
                "check the firmware, cable and selected port"
            )
        value = reply.value or ""
        # Some releases return a decimal integer; keep it readable without
        # pretending to know the version formatting.
        return value.strip() or "unknown"

    def _optional_query(self, path: str) -> str | None:
        try:
            reply = self._request(path, "get", 0.8, path)
        except BackendError:
            return None
        if reply is None or not reply.ok:
            return None
        return reply.value

    def disconnect(self) -> None:
        self._closing = True
        self._connected = False
        self._stop.set()
        with self._cv:
            self._cv.notify_all()
        serial_obj = self._serial
        self._serial = None
        if serial_obj is not None:
            try:
                serial_obj.close()
            except Exception:
                pass
        reader = self._reader
        self._reader = None
        if reader is not None and reader.is_alive() and reader is not threading.current_thread():
            reader.join(timeout=1.0)
        self._info = None
        with self._cv:
            self._inbox.clear()

    @property
    def connected(self) -> bool:
        return self._connected and self._serial is not None

    @property
    def info(self) -> DeviceInfo | None:
        return self._info

    # ------------------------------------------------------------------ reader
    def _reader_loop(self) -> None:
        serial_obj = self._serial
        if serial_obj is None:
            return
        while not self._stop.is_set():
            try:
                raw = serial_obj.readline()
            except Exception as exc:
                if not self._closing:
                    self._last_error = str(exc)
                    log.warning("OpenFFBoard serial read failed: %s", exc)
                self._connected = False
                with self._cv:
                    self._cv.notify_all()
                return
            if not raw:
                continue
            try:
                line = raw.decode("utf-8", errors="replace")
            except Exception:
                continue
            reply = parse_line(line)
            if reply is None:
                continue
            if reply.kind is ReplyKind.UNKNOWN:
                self._ignored.append(line.rstrip())
                continue
            with self._cv:
                self._inbox.append(reply)
                self._cv.notify_all()

    # ---------------------------------------------------------------- transport
    def _request(
        self,
        path: str,
        kind: str,
        timeout: float,
        command_path: str | None = None,
    ) -> Reply:
        expected_path = command_path or path
        if kind == "get":
            payload = format_get(path)
        elif kind == "set":
            raise AssertionError("use _set for writes")
        else:
            payload = format_execute(path)
        return self._exchange(payload, expected_path, kind, timeout)

    def _set(self, path: str, value: object, timeout: float = DEFAULT_TIMEOUT) -> Reply:
        return self._exchange(format_set(path, value), path, "set", timeout)

    def _exchange(self, payload: str, path: str, kind: str, timeout: float) -> Reply:
        if not self.connected or self._serial is None:
            raise BackendError("device is not connected")
        deadline = time.monotonic() + max(0.1, timeout)
        with self._cv:
            self._inbox.clear()
            try:
                self._serial.write(payload.encode("ascii"))
                self._serial.flush()
            except Exception as exc:
                self._connected = False
                raise BackendError(f"serial write failed: {exc}") from exc
            while True:
                for index, reply in enumerate(self._inbox):
                    if not self._matches(reply, path, kind):
                        continue
                    del self._inbox[index]
                    return reply
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._cv.wait(min(remaining, 0.1))
            if not self._connected:
                raise BackendError(
                    f"serial connection lost while waiting for {path}"
                    + (f": {self._last_error}" if self._last_error else "")
                )
            raise BackendTimeout(
                f"timeout waiting for {path!r}; no reply from firmware"
            )

    @staticmethod
    def _matches(reply: Reply, path: str, kind: str) -> bool:
        if reply.path.lower() != path.lower():
            return False
        if kind == "get":
            return reply.kind is ReplyKind.GET
        if kind == "set":
            return reply.kind is ReplyKind.SET
        return reply.kind in {ReplyKind.EXECUTE, ReplyKind.NOTIFICATION, ReplyKind.SET}

    def _get_int(self, path: str, timeout: float = DEFAULT_TIMEOUT) -> int | None:
        reply = self._request(path, "get", timeout, path)
        if reply is None or not reply.ok:
            return None
        return reply.as_int()

    def _require_set(self, path: str, value: object, timeout: float = DEFAULT_TIMEOUT) -> None:
        reply = self._set(path, value, timeout)
        if not reply.ok:
            raise BackendCommandError(f"firmware rejected {path}={value}: {reply.raw}")
        if reply.status == "" and reply.kind is not ReplyKind.SET:
            raise BackendCommandError(f"unexpected reply for {path}: {reply.raw}")

    # ----------------------------------------------------------------- settings
    def read_settings(self) -> SettingsRead:
        if not self.connected:
            raise BackendError("device is not connected")
        values: dict[str, int] = {}
        missing: list[str] = []
        raw_map: dict[str, int] = {}
        for field, spec in FIELD_MAP.items():
            try:
                raw = self._get_int(spec.path)
            except BackendError:
                raw = None
            if raw is None:
                missing.append(field)
                continue
            raw_map[field] = raw
            values[field] = decode_field(field, raw)
        settings_dict = WheelSettings().to_dict()
        settings_dict.update(values)
        settings = WheelSettings.from_dict(settings_dict)
        return SettingsRead(settings=settings, raw=raw_map, missing=tuple(missing))

    def _expanded_fields(
        self,
        target: WheelSettings,
        fields: set[str],
        previous: WheelSettings,
    ) -> set[str]:
        expanded = set(fields)
        if "condition_filters_enabled" in expanded and target.condition_filters_enabled:
            if not previous.condition_filters_enabled:
                expanded.update(CONDITION_FILTER_FIELDS)
        return expanded

    def write_settings(
        self,
        target: WheelSettings,
        fields: Iterable[str],
        previous: WheelSettings,
        persist: bool = False,
    ) -> None:
        if not self.connected:
            raise BackendError("device is not connected")
        requested = {field for field in fields if field in FIELD_MAP}
        if not requested:
            if persist:
                self.save()
            return
        requested = self._expanded_fields(target, requested, previous)
        power_field = "power_pct"
        has_power = power_field in requested
        target_raw = encode_field(power_field, target)
        previous_raw = encode_field(power_field, previous)
        if has_power and target_raw <= previous_raw:
            self._require_set(FIELD_MAP[power_field].path, target_raw)

        for field in WRITE_ORDER:
            if field not in requested:
                continue
            self._require_set(FIELD_MAP[field].path, encode_field(field, target))

        if has_power and target_raw > previous_raw:
            self._require_set(FIELD_MAP[power_field].path, target_raw)

        if persist:
            self.save()

    def save(self) -> None:
        reply = self._request("sys.save", "execute", 2.5, "sys.save")
        if reply is not None and not reply.ok:
            raise BackendCommandError(f"firmware rejected sys.save: {reply.raw}")

    def center_axis(self) -> None:
        # OpenFFBoard executes zeroenc on a GET and acknowledges with OK.
        reply = self._request("axis.0.zeroenc", "get", 1.2, "axis.0.zeroenc")
        if reply is not None and not reply.ok:
            raise BackendCommandError(f"firmware rejected axis.0.zeroenc: {reply.raw}")

    # ---------------------------------------------------------------- telemetry
    def read_telemetry(self, rotation_deg: int) -> Telemetry:
        if not self.connected:
            raise BackendError("device is not connected")
        reads: dict[str, int] = {}
        failures = 0
        for key, path in (
            ("pos", "axis.0.curpos"),
            ("torque", "axis.0.curtorque"),
            ("speed", "axis.0.curspd"),
            ("ffb", "main.0.ffbactive"),
            ("voltage", "sys.vext"),
            ("temp", "sys.temp"),
        ):
            try:
                value = self._get_int(path, timeout=0.55)
            except BackendError:
                failures += 1
                continue
            if value is not None:
                reads[key] = value
        if failures >= 6:
            raise BackendTimeout("telemetry queries timed out")

        pos_raw = reads.get("pos")
        torque_raw = reads.get("torque")
        speed_raw = reads.get("speed")
        voltage_raw = reads.get("voltage")
        position_pct = None
        position_deg = None
        if pos_raw is not None:
            position_pct = max(-100.0, min(100.0, pos_raw / 32767.0 * 100.0))
            position_deg = position_pct / 100.0 * (rotation_deg / 2.0)
        torque_pct = None
        if torque_raw is not None:
            torque_pct = max(-100.0, min(100.0, torque_raw / 32767.0 * 100.0))
        supply_voltage = None
        if voltage_raw is not None:
            supply_voltage = voltage_raw / 1000.0 if voltage_raw > 2000 else float(voltage_raw)
        return Telemetry(
            position_deg=position_deg,
            position_pct=position_pct,
            torque_pct=torque_pct,
            speed_dps=float(speed_raw) if speed_raw is not None else None,
            ffb_active=bool(reads["ffb"]) if "ffb" in reads else None,
            supply_voltage=supply_voltage,
            temperature_c=float(reads["temp"]) if "temp" in reads else None,
        )

    # ------------------------------------------------------------------- safety
    def emergency_stop(self) -> None:
        if not self.connected:
            raise BackendError("device is not connected")
        errors: list[str] = []
        # Zero the axis scaler first (immediate), then invoke the firmware stop.
        try:
            self._require_set("axis.0.power", 0, timeout=0.7)
        except BackendError as exc:
            errors.append(f"axis power: {exc}")
        try:
            self._require_set("main.0.estop", 1, timeout=0.7)
        except BackendError as exc:
            errors.append(f"estop: {exc}")
        if len(errors) == 2:
            raise BackendError("emergency stop failed: " + "; ".join(errors))
        log.warning("Emergency stop sent to OpenFFBoard")

    # ------------------------------------------------------------------- raw IO
    def raw_command(self, command: str) -> Reply:
        if not self.connected:
            raise BackendError("device is not connected")
        try:
            payload = format_raw(command)
        except ProtocolError as exc:
            raise BackendError(str(exc)) from exc
        text = payload.strip()
        if text.endswith("?"):
            path = text[:-1]
            return self._exchange(payload, path, "get", 2.0)
        if "=" in text:
            path = text.split("=", 1)[0]
            return self._exchange(payload, path, "set", 2.0)
        return self._exchange(payload, text, "execute", 2.0)
