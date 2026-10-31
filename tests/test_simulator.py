from __future__ import annotations

from dataclasses import replace

import pytest

from pyffb.backends.simulator import SimulatedBackend
from pyffb.controller import SafetyPolicy, WheelController
from pyffb.models import WheelSettings


def make_controller(**policy) -> tuple[WheelController, SimulatedBackend]:
    backend = SimulatedBackend()
    backend.connect()
    controller = WheelController(backend, SafetyPolicy(**policy))
    return controller, backend


def test_apply_settings_geometry_and_persistence():
    controller, backend = make_controller()
    target = WheelSettings(power_pct=55, rotation_deg=540, endstop_pct=44, invert=True)
    report = controller.apply_settings(target, include_geometry=True, persist=True)
    assert report.ok
    assert report.rolled_back is False
    assert report.persisted is True
    assert backend.settings.rotation_deg == 540
    assert backend.settings.power_pct == 55
    assert backend.settings.invert is True
    assert backend.save_count == 1


def test_auto_apply_skips_geometry():
    controller, backend = make_controller()
    target = WheelSettings(power_pct=48, rotation_deg=360)
    report = controller.apply_settings(target, include_geometry=False)
    assert report.ok
    assert "rotation_deg" in report.skipped
    assert backend.settings.rotation_deg == 900
    assert backend.settings.power_pct == 48


def test_safety_cap():
    controller, backend = make_controller(max_power_pct=70)
    report = controller.apply_settings(WheelSettings(power_pct=100))
    assert report.ok
    assert any("safety cap" in warning for warning in report.warnings)
    assert backend.settings.power_pct == 70


def test_rollback_on_write_failure():
    controller, backend = make_controller()
    initial = backend.settings
    backend.fail_next_write = True
    report = controller.apply_settings(WheelSettings(power_pct=40, rotation_deg=450))
    assert not report.ok
    assert report.rolled_back is True
    assert backend.settings == initial


def test_emergency_stop():
    controller, backend = make_controller()
    controller.emergency_stop()
    assert backend.estop_count == 1
    assert backend.settings.power_pct == 0
    telemetry = controller.read_telemetry()
    assert telemetry.ffb_active is False
    assert telemetry.torque_pct == 0


def test_center_axis():
    controller, backend = make_controller()
    controller.center_axis()
    assert "axis.0.zeroenc?" in backend.raw_history


def test_refuses_apply_when_required_fields_missing():
    class PartialReadBackend(SimulatedBackend):
        def read_settings(self):
            read = super().read_settings()
            return replace(read, missing=("power_pct",))

    backend = PartialReadBackend()
    backend.connect()
    controller = WheelController(backend)
    report = controller.apply_settings(WheelSettings(power_pct=50))
    assert not report.ok
    assert "core fields" in report.errors[0]
    assert backend.write_history == []


def test_telemetry():
    controller, _backend = make_controller()
    telemetry = controller.read_telemetry(900)
    assert telemetry.position_deg is not None
    assert telemetry.torque_pct is not None
    assert telemetry.supply_voltage is not None


def test_raw_command_roundtrip():
    controller, _backend = make_controller()
    reply = controller.raw_command("axis.0.power?")
    assert reply.as_int() == 22937
    with pytest.raises(Exception, match="read-only"):
        controller.raw_command("axis.0.power=1234")
    with pytest.raises(Exception, match="side effects"):
        controller.raw_command("sys.reboot?")
