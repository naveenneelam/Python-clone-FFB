"""Deterministic in-process simulator for demos, UI development and tests."""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Iterable

from ..models import (
    BackendDescriptor,
    DeviceInfo,
    SettingsRead,
    Telemetry,
    WheelSettings,
)
from ..protocol import Reply, ReplyKind, format_raw
from .base import BackendCommandError, BackendError, WheelBackend
from .openffboard import FIELD_MAP, decode_field, encode_field


class SimulatedBackend(WheelBackend):
    key = "simulator"
    display_name = "Simulator (no hardware)"
    supports_save = True

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._connected = False
        self._info: DeviceInfo | None = None
        self._settings = WheelSettings()
        self._saved = WheelSettings()
        self._save_count = 0
        self._estop_count = 0
        self._estop = False
        self._epoch = time.monotonic()
        self.write_history: list[tuple[WheelSettings, tuple[str, ...]]] = []
        self.raw_history: list[str] = []
        self.fail_next_write = False
        self.fail_save = False

    @classmethod
    def list_devices(cls) -> list[BackendDescriptor]:
        return [
            BackendDescriptor(
                key=cls.key,
                display_name="Built-in simulator",
                port="simulator",
                description="No hardware required",
                simulated=True,
            )
        ]

    def connect(self, port: str = "simulator") -> DeviceInfo:
        with self._lock:
            self._connected = True
            self._info = DeviceInfo(
                backend_key=self.key,
                display_name="PyFFB simulator",
                port=port or "simulator",
                firmware="sim-2.0",
                hardware="virtual-ffb-wheel",
                serial_number="SIM-0001",
            )
            self._epoch = time.monotonic()
            return self._info

    def disconnect(self) -> None:
        with self._lock:
            self._connected = False
            self._info = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def info(self) -> DeviceInfo | None:
        return self._info

    def _assert_connected(self) -> None:
        if not self._connected:
            raise BackendError("simulator is not connected")

    def read_settings(self) -> SettingsRead:
        with self._lock:
            self._assert_connected()
            raw = {
                field: encode_field(field, self._settings)
                for field in FIELD_MAP
            }
            return SettingsRead(settings=self._settings, raw=raw)

    def write_settings(
        self,
        target: WheelSettings,
        fields: Iterable[str],
        previous: WheelSettings,
        persist: bool = False,
    ) -> None:
        with self._lock:
            self._assert_connected()
            if self.fail_next_write:
                self.fail_next_write = False
                raise BackendError("simulated write failure")
            requested = tuple(field for field in fields if field in FIELD_MAP)
            values = self._settings.to_dict()
            for field in requested:
                values[field] = getattr(target, field)
            self._settings = WheelSettings.from_dict(values)
            self.write_history.append((self._settings, requested))
            if persist:
                self.save()

    def save(self) -> None:
        with self._lock:
            self._assert_connected()
            if self.fail_save:
                self.fail_save = False
                raise BackendError("simulated flash failure")
            self._saved = self._settings
            self._save_count += 1

    def center_axis(self) -> None:
        with self._lock:
            self._assert_connected()
            self.raw_history.append("axis.0.zeroenc?")

    def read_telemetry(self, rotation_deg: int) -> Telemetry:
        with self._lock:
            self._assert_connected()
            t = time.monotonic() - self._epoch
            power = self._settings.power_pct / 100.0
            if self._estop:
                return Telemetry(
                    position_deg=0.0,
                    position_pct=0.0,
                    torque_pct=0.0,
                    speed_dps=0.0,
                    ffb_active=False,
                    supply_voltage=48.0,
                    temperature_c=36.0,
                )
            pos_norm = 0.58 * math.sin(t * 0.55) + 0.07 * math.sin(t * 2.1)
            pos_norm = max(-1.0, min(1.0, pos_norm))
            speed = (
                0.58 * 0.55 * math.cos(t * 0.55)
                + 0.07 * 2.1 * math.cos(t * 2.1)
            ) * (rotation_deg / 2.0)
            torque = (
                0.32 * math.sin(t * 0.9)
                + 0.10 * math.sin(t * 2.7)
                + 0.04 * math.sin(t * 7.3)
            ) * power
            torque = max(-1.0, min(1.0, torque))
            return Telemetry(
                position_deg=pos_norm * (rotation_deg / 2.0),
                position_pct=pos_norm * 100.0,
                torque_pct=torque * 100.0,
                speed_dps=speed,
                ffb_active=True,
                supply_voltage=48.0 + 0.25 * math.sin(t * 0.4),
                temperature_c=37.0 + 1.5 * math.sin(t * 0.05),
            )

    def emergency_stop(self) -> None:
        with self._lock:
            self._assert_connected()
            self._estop = True
            self._estop_count += 1
            self._settings = self._settings.merged(power_pct=0)

    def clear_emergency_stop_for_tests(self) -> None:
        with self._lock:
            self._estop = False

    def raw_command(self, command: str) -> Reply:
        with self._lock:
            self._assert_connected()
            self.raw_history.append(command)
            payload = format_raw(command).strip()
            if payload.endswith("?"):
                path = payload[:-1]
                if path == "sys.swver":
                    value = "sim-2.0"
                    return Reply(raw=f"[{path}?|{value}]", kind=ReplyKind.GET, path=path, value=value)
                if path == "sys.hwtype":
                    value = "virtual-ffb-wheel"
                    return Reply(raw=f"[{path}?|{value}]", kind=ReplyKind.GET, path=path, value=value)
                for field, spec in FIELD_MAP.items():
                    if spec.path.lower() == path.lower():
                        raw = encode_field(field, self._settings)
                        return Reply(
                            raw=f"[{path}?|{raw}]",
                            kind=ReplyKind.GET,
                            path=path,
                            value=str(raw),
                        )
                raise BackendCommandError(f"simulator does not know {path}")
            if "=" in payload:
                path, raw_text = payload.split("=", 1)
                try:
                    raw = int(raw_text, 0)
                except ValueError as exc:
                    raise BackendCommandError("simulator only accepts integer writes") from exc
                for field, spec in FIELD_MAP.items():
                    if spec.path.lower() == path.lower():
                        values = self._settings.to_dict()
                        values[field] = decode_field(field, raw)
                        self._settings = WheelSettings.from_dict(values)
                        return Reply(
                            raw=f"[{path}={raw}|OK]",
                            kind=ReplyKind.SET,
                            path=path,
                            sent_value=str(raw),
                            status="OK",
                        )
                raise BackendCommandError(f"simulator does not know {path}")
            if payload == "sys.save":
                self.save()
                return Reply(
                    raw="[sys.save|OK]",
                    kind=ReplyKind.EXECUTE,
                    path="sys.save",
                    status="OK",
                )
            raise BackendCommandError(f"simulator does not know {payload}")

    # Test/demo conveniences -------------------------------------------------
    @property
    def settings(self) -> WheelSettings:
        with self._lock:
            return self._settings

    @property
    def saved_settings(self) -> WheelSettings:
        with self._lock:
            return self._saved

    @property
    def save_count(self) -> int:
        with self._lock:
            return self._save_count

    @property
    def estop_count(self) -> int:
        with self._lock:
            return self._estop_count
