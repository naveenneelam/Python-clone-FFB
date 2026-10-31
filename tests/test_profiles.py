from __future__ import annotations

from pyffb.presets import DESKTOP_PROFILE_ID, GENERIC_PROFILE_ID, PROFILES


def test_profile_ids_unique():
    ids = [profile.id for profile in PROFILES]
    assert len(ids) == len(set(ids))


def test_required_profiles_exist():
    ids = {profile.id for profile in PROFILES}
    required = {
        DESKTOP_PROFILE_ID,
        GENERIC_PROFILE_ID,
        "acc",
        "assetto-corsa",
        "iracing",
        "rf2",
        "le-mans-ultimate",
        "ams2",
        "f1",
        "ea-wrc",
        "forza-horizon-5",
        "beamng",
        "euro-truck-simulator-2",
    }
    assert required <= ids


def test_profiles_are_valid_and_conservative():
    for profile in PROFILES:
        fixed, warnings = profile.validated()
        assert warnings == [], (profile.id, warnings)
        assert fixed.settings.power_pct <= 90
        assert 90 <= fixed.settings.rotation_deg <= 2520
        assert fixed.settings.endstop_pct <= 60
        for exe in fixed.exe_names:
            assert exe == exe.lower()
            assert "\\" not in exe and "/" not in exe


def test_only_automation_profiles_have_executables():
    for profile in PROFILES:
        if profile.id in {DESKTOP_PROFILE_ID, GENERIC_PROFILE_ID}:
            assert profile.exe_names == ()


def test_effect_gain_defaults():
    acc = next(profile for profile in PROFILES if profile.id == "acc")
    assert acc.settings.spring_gain_pct < 100
    assert acc.settings.friction_gain_pct == 100
