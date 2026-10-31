from __future__ import annotations

import json
from pathlib import Path

import pytest

from pyffb.config import (
    AppConfig,
    ConfigStore,
    ProfileLibrary,
    export_profile,
    import_profile,
    slugify,
)
from pyffb.models import ModelError, Profile, WheelSettings
from pyffb.presets import DESKTOP_PROFILE_ID, PROFILES


def test_app_config_roundtrip():
    config = AppConfig(backend_key="simulator", poll_hz=99, safety_max_power_pct=500)
    fixed, warnings = config.validated()
    assert fixed.backend_key == "simulator"
    assert fixed.poll_hz == 20
    assert fixed.safety_max_power_pct == 100
    assert warnings
    again = AppConfig.from_dict(fixed.to_dict())
    assert again == fixed


def test_config_store_corruption_backup(tmp_path: Path):
    store = ConfigStore(tmp_path)
    store.ensure_dirs()
    store.path.write_text("{not json", encoding="utf-8")
    config = store.load()
    assert config == AppConfig()
    assert store.warnings
    backups = list(tmp_path.glob("config.json.backup-*"))
    assert len(backups) == 1


def test_config_store_roundtrip(tmp_path: Path):
    store = ConfigStore(tmp_path)
    config = AppConfig(backend_key="simulator", port="simulator", auto_switch_games=False)
    store.save(config)
    loaded = store.load()
    assert loaded.backend_key == "simulator"
    assert loaded.port == "simulator"
    assert loaded.auto_switch_games is False


def test_library_custom_profiles():
    library = ProfileLibrary()
    profile = library.make_custom("My ACC", WheelSettings(power_pct=60), game="ACC")
    assert profile.id.startswith("custom-")
    assert profile.id in {p.id for p in library.custom()}
    assert library.get(profile.id).name == "My ACC"
    library.remove_custom(profile.id)
    assert profile.id not in {p.id for p in library.custom()}


def test_builtin_id_collision_rejected():
    library = ProfileLibrary()
    profile = Profile(id="acc", name="Collision", settings=WheelSettings())
    with pytest.raises(ModelError):
        library.add_custom(profile)


def test_builtin_cannot_be_deleted():
    library = ProfileLibrary()
    with pytest.raises(ModelError):
        library.remove_custom(DESKTOP_PROFILE_ID)


def test_profile_export_import(tmp_path: Path):
    source = PROFILES[2]
    path = tmp_path / "profile.json"
    export_profile(source, path)
    loaded = import_profile(path)
    assert loaded.id == source.id
    assert loaded.settings == source.settings
    assert loaded.builtin is False


def test_find_by_executable():
    library = ProfileLibrary()
    match = library.find_by_executable(["AC2-Win64-Shipping.EXE"])
    assert match is not None
    assert match[0].id == "acc"


def test_slugify():
    assert slugify("My Wheel / Setup!") == "my-wheel-setup"
    assert slugify("") == ""


def test_custom_profile_in_config():
    library = ProfileLibrary()
    profile = library.make_custom("Custom", WheelSettings(power_pct=42))
    config = AppConfig.from_dict(
        {**AppConfig().to_dict(), "custom_profiles": [profile.to_dict()]}
    )
    assert len(config.custom_profiles) == 1
    assert config.custom_profiles[0].id == profile.id
    json.dumps(config.to_dict())
