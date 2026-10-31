from __future__ import annotations

import threading
import time
from collections import deque

import pytest

import serial

from pyffb.backends.openffboard import FIELD_MAP, OpenFFBoardBackend, encode_field, decode_field
from pyffb.models import WheelSettings


class FakeSerial:
    """Minimal OpenFFBoard stand-in for transport/codec tests."""

    def __init__(self, **kwargs) -> None:
        self._queue: deque[bytes] = deque()
        self._lock = threading.Lock()
        self._settings = WheelSettings()
        self.closed = False
        self._telemetry = {
            "axis.0.curpos": 12000,
            "axis.0.curtorque": 4000,
            "axis.0.curspd": 220,
            "main.0.ffbactive": 1,
            "sys.vext": 48000,
            "sys.temp": 41,
        }

    def write(self, payload: bytes) -> int:
        command = payload.decode("ascii").strip()
        if command.endswith("?"):
            path = command[:-1]
            if path == "sys.swver":
                value = "1.16.5-test"
            elif path == "sys.hwtype":
                value = "7"
            elif path in self._telemetry:
                value = str(self._telemetry[path])
            elif path == "axis.0.zeroenc":
                value = "OK"
            else:
                value = None
                for field, spec in FIELD_MAP.items():
                    if spec.path.lower() == path.lower():
                        value = str(encode_field(field, self._settings))
                        break
                if value is None:
                    self._queue.append(b"[unknown|ERR]\r\n")
                    return len(payload)
            with self._lock:
                self._queue.append(f"[{path}?|{value}]\r\n".encode("ascii"))
            return len(payload)
        if "=" in command:
            path, raw_text = command.split("=", 1)
            raw = int(raw_text)
            for field, spec in FIELD_MAP.items():
                if spec.path.lower() == path.lower():
                    values = self._settings.to_dict()
                    values[field] = decode_field(field, raw)
                    self._settings = WheelSettings.from_dict(values)
                    break
            with self._lock:
                self._queue.append(f"[{path}={raw}|OK]\r\n".encode("ascii"))
            return len(payload)
        with self._lock:
            self._queue.append(b"[sys.save|OK]\r\n")
        return len(payload)

    def readline(self) -> bytes:
        with self._lock:
            if self._queue:
                return self._queue.popleft()
        time.sleep(0.002)
        return b""

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def test_openffboard_fake_transport(monkeypatch):
    monkeypatch.setattr(serial, "Serial", FakeSerial)
    backend = OpenFFBoardBackend()
    info = backend.connect("COM_TEST")
    try:
        assert info.firmware == "1.16.5-test"
        read = backend.read_settings()
        assert read.complete
        assert read.settings.power_pct == 70
        assert read.settings.rotation_deg == 900
        telemetry = backend.read_telemetry(900)
        assert telemetry.ffb_active is True
        assert telemetry.supply_voltage == pytest.approx(48.0)
        assert telemetry.temperature_c == 41
        target = read.settings.merged(power_pct=50, rotation_deg=540)
        backend.write_settings(target, ["power_pct", "rotation_deg"], read.settings, persist=True)
        after = backend.read_settings()
        assert after.settings.power_pct == 50
        assert after.settings.rotation_deg == 540
        reply = backend.raw_command("sys.swver?")
        assert reply.value == "1.16.5-test"
        backend.center_axis()
        backend.emergency_stop()
    finally:
        backend.disconnect()
    assert backend.connected is False
