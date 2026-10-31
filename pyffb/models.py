"""Typed configuration, profile, device and telemetry models.

All user-editable force values are stored as percentages.  Adapters translate
them to firmware-native scales (for example OpenFFBoard's 0..32767 axis power).
Keeping one canonical model makes profiles portable between backends.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, replace
from typing import Any, Mapping

from .version import PROFILE_SCHEMA_VERSION

# Physical and UI limits.  These are intentionally conservative; motor current
# limits belong to the firmware and are never written by this application.
POWER_MIN, POWER_MAX = 0, 100
ROTATION_MIN, ROTATION_MAX = 90, 2520
PERCENT_MIN, PERCENT_MAX = 0, 100
MAX_SPEED_MIN, MAX_SPEED_MAX = 0, 3600
TORQUE_RATE_MIN, TORQUE_RATE_MAX = 0, 32767
EXPO_MIN, EXPO_MAX = -127, 127
FILTER_FREQ_MIN, FILTER_FREQ_MAX = 1, 500
FILTER_Q_MIN, FILTER_Q_MAX = 1, 127
PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")


class ModelError(ValueError):
    """Raised when a configuration document cannot be interpreted."""


def clamp_int(
    value: Any,
    default: int,
    low: int,
    high: int,
    field_name: str,
    warnings: list[str] | None = None,
) -> int:
    """Coerce *value* to an int inside [low, high], recording a warning."""

    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        if warnings is not None:
            warnings.append(f"{field_name}: invalid value {value!r}; using {default}")
        return default
    if ivalue < low or ivalue > high:
        clamped = max(low, min(high, ivalue))
        if warnings is not None:
            warnings.append(
                f"{field_name}: {ivalue} outside {low}..{high}; clamped to {clamped}"
            )
        return clamped
    return ivalue


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


@dataclass(frozen=True)
class WheelSettings:
    """Canonical wheel tuning model.

    Percent fields map to backend-specific raw values.  Effect gains are
    multiplicative firmware gains, not normalised user output; their defaults
    intentionally mirror OpenFFBoard's stock values.
    """

    power_pct: int = 70
    rotation_deg: int = 900
    invert: bool = False
    endstop_pct: int = 25
    idle_spring_pct: int = 8
    global_damper_pct: int = 8
    global_friction_pct: int = 4
    global_inertia_pct: int = 0
    game_effect_ratio_pct: int = 100
    max_speed_dps: int = 1500
    torque_rate: int = 0
    expo: int = 0

    # Firmware effect multipliers (OpenFFBoard defaults: 64/64/254/127).
    spring_gain_pct: int = 25
    damper_gain_pct: int = 25
    friction_gain_pct: int = 100
    inertia_gain_pct: int = 50
    friction_ramp_pct: int = 25

    # Constant force low-pass filter.  freq=0 means Nyquist in the firmware.
    constant_filter_hz: int = 500
    constant_filter_q: int = 70

    # Optional custom biquads for conditional effects.  When disabled the
    # firmware's built-in filter profile remains active.
    condition_filters_enabled: bool = False
    condition_friction_hz: int = 50
    condition_friction_q: int = 20
    condition_damper_hz: int = 30
    condition_damper_q: int = 40
    condition_inertia_hz: int = 15
    condition_inertia_q: int = 20

    def validated(self) -> tuple[WheelSettings, list[str]]:
        """Return a clamped copy plus human-readable warnings."""

        warnings: list[str] = []
        data: dict[str, Any] = {}
        int_ranges: dict[str, tuple[int, int]] = {
            "power_pct": (POWER_MIN, POWER_MAX),
            "rotation_deg": (ROTATION_MIN, ROTATION_MAX),
            "endstop_pct": (PERCENT_MIN, PERCENT_MAX),
            "idle_spring_pct": (PERCENT_MIN, PERCENT_MAX),
            "global_damper_pct": (PERCENT_MIN, PERCENT_MAX),
            "global_friction_pct": (PERCENT_MIN, PERCENT_MAX),
            "global_inertia_pct": (PERCENT_MIN, PERCENT_MAX),
            "game_effect_ratio_pct": (PERCENT_MIN, PERCENT_MAX),
            "max_speed_dps": (MAX_SPEED_MIN, MAX_SPEED_MAX),
            "torque_rate": (TORQUE_RATE_MIN, TORQUE_RATE_MAX),
            "expo": (EXPO_MIN, EXPO_MAX),
            "spring_gain_pct": (PERCENT_MIN, PERCENT_MAX),
            "damper_gain_pct": (PERCENT_MIN, PERCENT_MAX),
            "friction_gain_pct": (PERCENT_MIN, PERCENT_MAX),
            "inertia_gain_pct": (PERCENT_MIN, PERCENT_MAX),
            "friction_ramp_pct": (PERCENT_MIN, PERCENT_MAX),
            "constant_filter_hz": (FILTER_FREQ_MIN, FILTER_FREQ_MAX),
            "constant_filter_q": (FILTER_Q_MIN, FILTER_Q_MAX),
            "condition_friction_hz": (FILTER_FREQ_MIN, FILTER_FREQ_MAX),
            "condition_friction_q": (FILTER_Q_MIN, FILTER_Q_MAX),
            "condition_damper_hz": (FILTER_FREQ_MIN, FILTER_FREQ_MAX),
            "condition_damper_q": (FILTER_Q_MIN, FILTER_Q_MAX),
            "condition_inertia_hz": (FILTER_FREQ_MIN, FILTER_FREQ_MAX),
            "condition_inertia_q": (FILTER_Q_MIN, FILTER_Q_MAX),
        }
        for name, (low, high) in int_ranges.items():
            current = getattr(self, name)
            data[name] = clamp_int(current, getattr(WheelSettings, name, current), low, high, name, warnings)
        data["invert"] = bool(self.invert)
        data["condition_filters_enabled"] = bool(self.condition_filters_enabled)
        return WheelSettings(**data), warnings

    def merged(self, **changes: Any) -> WheelSettings:
        """Return a validated copy with selected fields changed."""

        candidate = replace(self, **changes)
        return candidate.validated()[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "power_pct": self.power_pct,
            "rotation_deg": self.rotation_deg,
            "invert": self.invert,
            "endstop_pct": self.endstop_pct,
            "idle_spring_pct": self.idle_spring_pct,
            "global_damper_pct": self.global_damper_pct,
            "global_friction_pct": self.global_friction_pct,
            "global_inertia_pct": self.global_inertia_pct,
            "game_effect_ratio_pct": self.game_effect_ratio_pct,
            "max_speed_dps": self.max_speed_dps,
            "torque_rate": self.torque_rate,
            "expo": self.expo,
            "spring_gain_pct": self.spring_gain_pct,
            "damper_gain_pct": self.damper_gain_pct,
            "friction_gain_pct": self.friction_gain_pct,
            "inertia_gain_pct": self.inertia_gain_pct,
            "friction_ramp_pct": self.friction_ramp_pct,
            "constant_filter_hz": self.constant_filter_hz,
            "constant_filter_q": self.constant_filter_q,
            "condition_filters_enabled": self.condition_filters_enabled,
            "condition_friction_hz": self.condition_friction_hz,
            "condition_friction_q": self.condition_friction_q,
            "condition_damper_hz": self.condition_damper_hz,
            "condition_damper_q": self.condition_damper_q,
            "condition_inertia_hz": self.condition_inertia_hz,
            "condition_inertia_q": self.condition_inertia_q,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> WheelSettings:
        if data is None:
            return cls()
        if not isinstance(data, Mapping):
            raise ModelError("settings must be a JSON object")
        base = cls()
        known = base.to_dict()
        values: dict[str, Any] = {}
        for key, default in known.items():
            if key not in data:
                values[key] = default
            elif isinstance(default, bool):
                values[key] = _coerce_bool(data[key], default)
            else:
                values[key] = data[key]
        candidate = cls(**values)
        return candidate.validated()[0]


@dataclass(frozen=True)
class Profile:
    """A named wheel configuration, optionally bound to game executables."""

    id: str
    name: str
    game: str = ""
    exe_names: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)
    settings: WheelSettings = field(default_factory=WheelSettings)
    builtin: bool = False
    schema_version: int = PROFILE_SCHEMA_VERSION

    def validated(self) -> tuple[Profile, list[str]]:
        warnings: list[str] = []
        if not PROFILE_ID_RE.match(self.id):
            raise ModelError(
                f"invalid profile id {self.id!r}; use lowercase letters, digits, '.', '_' or '-'"
            )
        settings, setting_warnings = self.settings.validated()
        warnings.extend(setting_warnings)
        exes = tuple(
            dict.fromkeys(
                name.strip().lower()
                for name in self.exe_names
                if isinstance(name, str) and name.strip()
            )
        )
        if not self.name.strip():
            warnings.append("profile name is empty")
        return (
            replace(
                self,
                name=self.name.strip() or self.id,
                game=self.game.strip(),
                exe_names=exes,
                notes=tuple(str(n) for n in self.notes),
                settings=settings,
            ),
            warnings,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PROFILE_SCHEMA_VERSION,
            "id": self.id,
            "name": self.name,
            "game": self.game,
            "exe_names": list(self.exe_names),
            "description": self.description,
            "notes": list(self.notes),
            "settings": self.settings.to_dict(),
            "builtin": self.builtin,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Profile:
        if not isinstance(data, Mapping):
            raise ModelError("profile must be a JSON object")
        try:
            profile_id = str(data["id"])
            name = str(data["name"])
        except KeyError as exc:
            raise ModelError(f"profile missing required key: {exc.args[0]}") from exc
        raw_exes = data.get("exe_names", [])
        if isinstance(raw_exes, str):
            raw_exes = [raw_exes]
        if not isinstance(raw_exes, (list, tuple)):
            raise ModelError("exe_names must be a list of strings")
        raw_notes = data.get("notes", [])
        if isinstance(raw_notes, str):
            raw_notes = [raw_notes]
        if not isinstance(raw_notes, (list, tuple)):
            raise ModelError("notes must be a list of strings")
        profile = cls(
            id=profile_id,
            name=name,
            game=str(data.get("game", "")),
            exe_names=tuple(str(exe) for exe in raw_exes),
            description=str(data.get("description", "")),
            notes=tuple(str(note) for note in raw_notes),
            settings=WheelSettings.from_dict(data.get("settings")),
            builtin=bool(data.get("builtin", False)),
            schema_version=int(data.get("schema_version", PROFILE_SCHEMA_VERSION)),
        )
        return profile.validated()[0]

    def with_settings(self, settings: WheelSettings) -> Profile:
        return replace(self, settings=settings)


@dataclass(frozen=True)
class SettingsRead:
    """A device settings snapshot and details about fields that were not read."""

    settings: WheelSettings
    raw: Mapping[str, int] = field(default_factory=dict)
    missing: tuple[str, ...] = field(default_factory=tuple)

    @property
    def complete(self) -> bool:
        return not self.missing


@dataclass(frozen=True)
class DeviceInfo:
    backend_key: str
    display_name: str
    port: str
    firmware: str = ""
    hardware: str = ""
    serial_number: str = ""
    extra: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BackendDescriptor:
    key: str
    display_name: str
    port: str
    description: str = ""
    hwid: str = ""
    simulated: bool = False


@dataclass(frozen=True)
class Telemetry:
    """Point-in-time telemetry normalised for presentation."""

    timestamp: float = field(default_factory=time.time)
    position_deg: float | None = None
    position_pct: float | None = None
    torque_pct: float | None = None
    speed_dps: float | None = None
    ffb_active: bool | None = None
    supply_voltage: float | None = None
    temperature_c: float | None = None

    @property
    def age_s(self) -> float:
        return max(0.0, time.time() - self.timestamp)

    @property
    def clipping(self) -> bool:
        return self.torque_pct is not None and abs(self.torque_pct) >= 99.5


@dataclass(frozen=True)
class ApplyReport:
    fields: tuple[str, ...] = field(default_factory=tuple)
    skipped: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    persisted: bool = False
    rolled_back: bool = False

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class ProfileChange:
    profile_id: str
    reason: str
    exe: str = ""
    game: str = ""


FIELD_LABELS: dict[str, str] = {
    "power_pct": "Strength",
    "rotation_deg": "Wheel range",
    "invert": "Invert axis",
    "endstop_pct": "Endstop",
    "idle_spring_pct": "Idle spring",
    "global_damper_pct": "Global damper",
    "global_friction_pct": "Global friction",
    "global_inertia_pct": "Global inertia",
    "game_effect_ratio_pct": "Game effect ratio",
    "max_speed_dps": "Speed limit",
    "torque_rate": "Torque rate limit",
    "expo": "Response curve",
    "spring_gain_pct": "Spring gain",
    "damper_gain_pct": "Damper gain",
    "friction_gain_pct": "Friction gain",
    "inertia_gain_pct": "Inertia gain",
    "friction_ramp_pct": "Friction ramp-up",
    "constant_filter_hz": "Constant filter frequency",
    "constant_filter_q": "Constant filter Q",
    "condition_filters_enabled": "Custom condition filters",
    "condition_friction_hz": "Friction filter frequency",
    "condition_friction_q": "Friction filter Q",
    "condition_damper_hz": "Damper filter frequency",
    "condition_damper_q": "Damper filter Q",
    "condition_inertia_hz": "Inertia filter frequency",
    "condition_inertia_q": "Inertia filter Q",
}


def profile_diff(before: WheelSettings, after: WheelSettings) -> list[str]:
    """Return changed field names in canonical model order."""

    changed: list[str] = []
    for name in before.to_dict():
        if getattr(before, name) != getattr(after, name):
            changed.append(name)
    return changed


def format_field(field_name: str, value: Any) -> str:
    label = FIELD_LABELS.get(field_name, field_name)
    if isinstance(value, bool):
        return f"{label}: {'on' if value else 'off'}"
    if field_name.endswith("_pct"):
        return f"{label}: {value}%"
    if field_name == "rotation_deg":
        return f"{label}: {value} deg"
    if field_name == "max_speed_dps":
        return f"{label}: {value} deg/s"
    return f"{label}: {value}"
