from __future__ import annotations

import pytest

from pyffb.models import (
    ModelError,
    Profile,
    WheelSettings,
    profile_diff,
)


def test_defaults_validate_without_warnings():
    settings, warnings = WheelSettings().validated()
    assert warnings == []
    assert settings == WheelSettings()


def test_clamp_power_and_rotation():
    settings = WheelSettings(power_pct=180, rotation_deg=10)
    fixed, warnings = settings.validated()
    assert fixed.power_pct == 100
    assert fixed.rotation_deg == 90
    assert any("power_pct" in warning for warning in warnings)
    assert any("rotation_deg" in warning for warning in warnings)


def test_from_dict_bool_and_unknown_fields():
    settings = WheelSettings.from_dict(
        {"invert": "true", "condition_filters_enabled": "on", "something_new": 1}
    )
    assert settings.invert is True
    assert settings.condition_filters_enabled is True


def test_profile_roundtrip():
    profile = Profile(
        id="custom-test",
        name="Test",
        game="Demo",
        exe_names=("Demo.EXE", "demo.exe"),
        settings=WheelSettings(power_pct=66),
        notes=("one",),
    )
    fixed, warnings = profile.validated()
    assert warnings == []
    assert fixed.exe_names == ("demo.exe",)
    restored = Profile.from_dict(fixed.to_dict())
    assert restored == fixed


def test_profile_rejects_bad_id():
    with pytest.raises(ModelError):
        Profile(id="Bad ID!", name="Nope").validated()


def test_profile_requires_id():
    with pytest.raises(ModelError):
        Profile.from_dict({"name": "missing id"})


def test_profile_diff():
    before = WheelSettings()
    after = before.merged(power_pct=80, rotation_deg=540)
    changed = profile_diff(before, after)
    assert "power_pct" in changed
    assert "rotation_deg" in changed
    assert "spring_gain_pct" not in changed
