"""Application settings, config paths and profile-library operations."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import presets
from .models import (
    ModelError,
    Profile,
    WheelSettings,
    clamp_int,
)
from .version import CONFIG_SCHEMA_VERSION

log = logging.getLogger(__name__)


def default_config_dir() -> Path:
    override = os.environ.get("PYFFB_CONFIG_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        root = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(root) / "PyFFB"
    if sys_platform() == "darwin":
        return Path.home() / "Library" / "Application Support" / "PyFFB"
    root = os.environ.get("XDG_CONFIG_HOME")
    return (Path(root) if root else Path.home() / ".config") / "pyffb"


def sys_platform() -> str:
    import sys

    return sys.platform


def default_log_dir() -> Path:
    return default_config_dir() / "logs"


@dataclass(frozen=True)
class AppConfig:
    schema_version: int = CONFIG_SCHEMA_VERSION
    backend_key: str = "openffboard"
    port: str = ""
    baudrate: int = 115200
    auto_switch_games: bool = True
    auto_apply_geometry: bool = False
    auto_persist: bool = False
    poll_hz: int = 4
    desktop_profile_id: str = presets.DESKTOP_PROFILE_ID
    last_profile_id: str = presets.DESKTOP_PROFILE_ID
    safety_max_power_pct: int = 90
    window_geometry: str = "1280x840"
    custom_profiles: tuple[Profile, ...] = field(default_factory=tuple)
    seen_welcome: bool = False

    def validated(self) -> tuple[AppConfig, list[str]]:
        warnings: list[str] = []
        backend = self.backend_key if self.backend_key in {"openffboard", "simulator"} else "openffboard"
        if backend != self.backend_key:
            warnings.append(f"unknown backend {self.backend_key!r}; using openffboard")
        baud = clamp_int(self.baudrate, 115200, 9600, 1_000_000, "baudrate", warnings)
        poll = clamp_int(self.poll_hz, 4, 1, 20, "poll_hz", warnings)
        cap = clamp_int(self.safety_max_power_pct, 90, 10, 100, "safety_max_power_pct", warnings)
        customs: list[Profile] = []
        ids = {profile.id for profile in presets.PROFILES}
        for profile in self.custom_profiles:
            try:
                valid, profile_warnings = profile.validated()
            except ModelError as exc:
                warnings.append(f"ignored custom profile {profile.id!r}: {exc}")
                continue
            warnings.extend(profile_warnings)
            if valid.id in ids:
                warnings.append(f"ignored duplicate custom profile id {valid.id!r}")
                continue
            ids.add(valid.id)
            customs.append(replace(valid, builtin=False))
        desktop = self.desktop_profile_id or presets.DESKTOP_PROFILE_ID
        if desktop not in ids:
            warnings.append(f"desktop profile {desktop!r} does not exist; using 'desktop'")
            desktop = presets.DESKTOP_PROFILE_ID
        last = self.last_profile_id or presets.GENERIC_PROFILE_ID
        if last not in ids:
            warnings.append(f"last profile {last!r} does not exist; using 'generic'")
            last = presets.GENERIC_PROFILE_ID
        return (
            replace(
                self,
                schema_version=CONFIG_SCHEMA_VERSION,
                backend_key=backend,
                port=str(self.port),
                baudrate=baud,
                poll_hz=poll,
                safety_max_power_pct=cap,
                desktop_profile_id=desktop,
                last_profile_id=last,
                custom_profiles=tuple(customs),
                window_geometry=str(self.window_geometry or "1280x840"),
            ),
            warnings,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "backend_key": self.backend_key,
            "port": self.port,
            "baudrate": self.baudrate,
            "auto_switch_games": self.auto_switch_games,
            "auto_apply_geometry": self.auto_apply_geometry,
            "auto_persist": self.auto_persist,
            "poll_hz": self.poll_hz,
            "desktop_profile_id": self.desktop_profile_id,
            "last_profile_id": self.last_profile_id,
            "safety_max_power_pct": self.safety_max_power_pct,
            "window_geometry": self.window_geometry,
            "custom_profiles": [profile.to_dict() for profile in self.custom_profiles],
            "seen_welcome": self.seen_welcome,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AppConfig:
        if not isinstance(data, Mapping):
            raise ModelError("config must be a JSON object")
        raw_profiles = data.get("custom_profiles", [])
        if not isinstance(raw_profiles, list):
            raw_profiles = []
        customs: list[Profile] = []
        for item in raw_profiles:
            try:
                customs.append(Profile.from_dict(item))
            except (ModelError, TypeError, ValueError) as exc:
                log.warning("Ignoring invalid custom profile: %s", exc)
        candidate = cls(
            schema_version=int(data.get("schema_version", CONFIG_SCHEMA_VERSION)),
            backend_key=str(data.get("backend_key", "openffboard")),
            port=str(data.get("port", "")),
            baudrate=int(data.get("baudrate", 115200)),
            auto_switch_games=bool(data.get("auto_switch_games", True)),
            auto_apply_geometry=bool(data.get("auto_apply_geometry", False)),
            auto_persist=bool(data.get("auto_persist", False)),
            poll_hz=int(data.get("poll_hz", 4)),
            desktop_profile_id=str(data.get("desktop_profile_id", presets.DESKTOP_PROFILE_ID)),
            last_profile_id=str(data.get("last_profile_id", presets.DESKTOP_PROFILE_ID)),
            safety_max_power_pct=int(data.get("safety_max_power_pct", 90)),
            window_geometry=str(data.get("window_geometry", "1280x840")),
            custom_profiles=tuple(customs),
            seen_welcome=bool(data.get("seen_welcome", False)),
        )
        return candidate.validated()[0]


class ConfigStore:
    """Small crash-safe JSON store with timestamped backups on corruption."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else default_config_dir()
        self.path = self.base_dir / "config.json"
        self.log_dir = self.base_dir / "logs"
        self.warnings: list[str] = []

    def ensure_dirs(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> AppConfig:
        self.warnings = []
        if not self.path.exists():
            return AppConfig()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            config = AppConfig.from_dict(data)
            self.warnings.extend(config.validated()[1])
            return config
        except Exception as exc:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = self.path.with_name(f"config.json.backup-{stamp}")
            try:
                self.path.replace(backup)
                message = f"config was unreadable ({exc}); backup saved to {backup.name}"
            except OSError:
                message = f"config was unreadable ({exc}); could not create a backup"
            self.warnings.append(message)
            log.warning(message)
            return AppConfig()

    def save(self, config: AppConfig) -> None:
        self.ensure_dirs()
        config, warnings = config.validated()
        payload = json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n"
        fd, tmp_name = tempfile.mkstemp(prefix="config-", suffix=".tmp", dir=self.base_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        finally:
            try:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            except OSError:
                pass
        if warnings:
            log.warning("Config normalized: %s", "; ".join(warnings))


class ProfileLibrary:
    """Read-only built-ins plus user profiles loaded into memory."""

    def __init__(self, custom_profiles: Iterable[Profile] = ()) -> None:
        self._builtins: dict[str, Profile] = {p.id: p for p in presets.PROFILES}
        self._custom: dict[str, Profile] = {}
        for profile in custom_profiles:
            try:
                self.add_custom(profile, replace_existing=True)
            except ModelError as exc:
                log.warning("Skipping custom profile %s: %s", getattr(profile, "id", "?"), exc)

    def all(self) -> tuple[Profile, ...]:
        return tuple(self._builtins.values()) + tuple(self._custom.values())

    def builtins(self) -> tuple[Profile, ...]:
        return tuple(self._builtins.values())

    def custom(self) -> tuple[Profile, ...]:
        return tuple(self._custom.values())

    def get(self, profile_id: str) -> Profile:
        if profile_id in self._custom:
            return self._custom[profile_id]
        try:
            return self._builtins[profile_id]
        except KeyError as exc:
            raise KeyError(f"unknown profile: {profile_id}") from exc

    def has(self, profile_id: str) -> bool:
        return profile_id in self._custom or profile_id in self._builtins

    def add_custom(
        self,
        profile: Profile,
        *,
        replace_existing: bool = False,
    ) -> Profile:
        profile, _warnings = profile.validated()
        if profile.id in self._builtins:
            raise ModelError(f"profile id {profile.id!r} collides with a built-in profile")
        if profile.id in self._custom and not replace_existing:
            raise ModelError(f"profile id {profile.id!r} already exists")
        profile = replace(profile, builtin=False)
        self._custom[profile.id] = profile
        return profile

    def remove_custom(self, profile_id: str) -> None:
        if profile_id in self._builtins:
            raise ModelError("built-in profiles cannot be deleted")
        try:
            del self._custom[profile_id]
        except KeyError as exc:
            raise KeyError(f"unknown custom profile: {profile_id}") from exc

    def find_by_executable(
        self,
        executables: Iterable[str],
        *,
        priority_ids: Iterable[str] = (),
    ) -> tuple[Profile, str] | None:
        names = {Path(exe).name.lower() for exe in executables if exe}
        if not names:
            return None
        candidates = list(self._custom.values()) + list(self._builtins.values())
        priority = {profile_id: index for index, profile_id in enumerate(priority_ids)}
        candidates.sort(key=lambda p: priority.get(p.id, 10_000))
        for profile in candidates:
            for exe in profile.exe_names:
                if Path(exe).name.lower() in names:
                    return profile, exe
        return None

    def make_custom(
        self,
        name: str,
        settings: WheelSettings,
        *,
        game: str = "",
        exe_names: Iterable[str] = (),
        description: str = "",
        notes: Iterable[str] = (),
    ) -> Profile:
        clean = name.strip() or "Custom profile"
        slug = slugify(clean) or "profile"
        base_id = f"custom-{slug}"[:56]
        profile_id = base_id
        while profile_id in self._builtins or profile_id in self._custom:
            profile_id = f"{base_id}-{uuid.uuid4().hex[:4]}"
        profile = Profile(
            id=profile_id,
            name=clean,
            game=game.strip(),
            exe_names=tuple(exe_names),
            description=description.strip(),
            notes=tuple(notes),
            settings=settings.validated()[0],
            builtin=False,
        )
        return self.add_custom(profile)


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-._")


def export_profile(profile: Profile, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    profile, _ = profile.validated()
    payload = json.dumps(profile.to_dict(), indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix="profile-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass


def import_profile(path: Path) -> Profile:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        if not data:
            raise ModelError("profile file contains an empty list")
        data = data[0]
    profile = Profile.from_dict(data)
    return replace(profile, builtin=False)
