"""High-level device session, safety enforcement and transactional apply logic."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace

from .backends.base import BackendError, WheelBackend
from .models import (
    ApplyReport,
    DeviceInfo,
    Profile,
    SettingsRead,
    Telemetry,
    WheelSettings,
    profile_diff,
)
from .protocol import Reply

log = logging.getLogger(__name__)

CONDITION_FIELDS = {
    "condition_friction_hz",
    "condition_friction_q",
    "condition_damper_hz",
    "condition_damper_q",
    "condition_inertia_hz",
    "condition_inertia_q",
}

GEOMETRY_FIELDS = {"rotation_deg", "invert"}
# Refuse a blind apply if a core safety-relevant field could not be read.
REQUIRED_READ_FIELDS = {"power_pct", "rotation_deg", "invert", "endstop_pct"}


@dataclass(frozen=True)
class SafetyPolicy:
    """Application-side guard rails, independent of firmware limits.

    This is not a replacement for a hardware emergency stop or the firmware's
    motor-current limits.  It only caps what the GUI/CLI can command.
    """

    max_power_pct: int = 90

    def enforce(self, settings: WheelSettings) -> tuple[WheelSettings, list[str]]:
        settings, warnings = settings.validated()
        cap = max(0, min(100, int(self.max_power_pct)))
        if settings.power_pct > cap:
            warnings.append(
                f"strength {settings.power_pct}% exceeds the app safety cap; reduced to {cap}%"
            )
            settings = replace(settings, power_pct=cap)
        return settings, warnings


class WheelController:
    """Own one backend session and apply profiles safely.

    A write failure triggers a best-effort rollback to the previously read
    settings.  The firmware's non-volatile state is only changed explicitly via
    ``persist=True``; automatic game switching never touches flash by default.
    """

    def __init__(self, backend: WheelBackend, policy: SafetyPolicy | None = None) -> None:
        self.backend = backend
        self.policy = policy or SafetyPolicy()

    @property
    def connected(self) -> bool:
        return self.backend.connected

    @property
    def info(self) -> DeviceInfo | None:
        return self.backend.info

    def connect(self, port: str = "") -> DeviceInfo:
        return self.backend.connect(port)

    def disconnect(self) -> None:
        self.backend.disconnect()

    def read_settings(self) -> SettingsRead:
        return self.backend.read_settings()

    def read_telemetry(self, rotation_deg: int = 900) -> Telemetry:
        return self.backend.read_telemetry(max(90, int(rotation_deg)))

    def save(self) -> None:
        self.backend.save()

    def center_axis(self) -> None:
        """Set the current physical wheel position as centre.

        Hold the wheel at the desired centre first; this only changes the
        coordinate origin and does not move the motor.
        """

        self.backend.center_axis()

    def emergency_stop(self) -> None:
        self.backend.emergency_stop()

    def raw_command(self, command: str) -> Reply:
        """Send a read-only diagnostic query.

        The desktop app must not provide a second, unguarded path around the
        safety cap and field validation.  Low-level backend objects still expose
        ``raw_command`` for custom integrations, but the GUI/controller use this
        restricted method.
        """

        text = command.strip()
        if not text.endswith("?"):
            raise BackendError(
                "the raw console is read-only; use Tuning to write wheel settings"
            )
        path = text[:-1].split("?", 1)[0].strip().lower()
        blocked = {
            "axis.0.zeroenc",
            "sys.reboot",
            "sys.dfu",
            "sys.format",
            "sys.errorsclr",
            "sys.flashdump",
            "sys.flashraw",
            "sys.otp",
        }
        if path in blocked:
            if path == "axis.0.zeroenc":
                raise BackendError(
                    "use the dedicated Center axis action instead of raw zeroenc"
                )
            raise BackendError(f"raw query blocked because it has side effects: {path}")
        return self.backend.raw_command(command)

    def apply_profile(
        self,
        profile: Profile,
        *,
        include_geometry: bool = True,
        persist: bool = False,
    ) -> ApplyReport:
        profile, warnings = profile.validated()
        report = self.apply_settings(
            profile.settings,
            include_geometry=include_geometry,
            persist=persist,
        )
        if warnings:
            return replace(report, warnings=tuple(warnings) + report.warnings)
        return report

    def apply_settings(
        self,
        target: WheelSettings,
        *,
        include_geometry: bool = True,
        persist: bool = False,
        fields: set[str] | None = None,
    ) -> ApplyReport:
        if not self.connected:
            return ApplyReport(errors=("device is not connected",))
        target, warnings = self.policy.enforce(target)
        try:
            current_read = self.backend.read_settings()
        except BackendError as exc:
            return ApplyReport(errors=(f"could not read current settings: {exc}",))
        current = current_read.settings
        missing_critical = REQUIRED_READ_FIELDS.intersection(current_read.missing)
        if missing_critical:
            return ApplyReport(
                errors=(
                    "refusing to apply because core fields could not be read: "
                    + ", ".join(sorted(missing_critical)),
                ),
                warnings=tuple(warnings),
            )
        if current_read.missing:
            warnings.append(
                "some fields could not be read: " + ", ".join(current_read.missing)
            )

        if fields is None:
            changed = profile_diff(current, target)
        else:
            changed = [
                name
                for name in current.to_dict()
                if name in fields and getattr(current, name) != getattr(target, name)
            ]
        skipped: list[str] = []
        if not include_geometry:
            skipped.extend(name for name in changed if name in GEOMETRY_FIELDS)
            changed = [name for name in changed if name not in GEOMETRY_FIELDS]
        if not target.condition_filters_enabled:
            skipped.extend(name for name in changed if name in CONDITION_FIELDS)
            changed = [name for name in changed if name not in CONDITION_FIELDS]
        if "condition_filters_enabled" in changed and target.condition_filters_enabled:
            # Ensure a switch to the custom profile also carries known values.
            for name in CONDITION_FIELDS:
                if name not in changed and getattr(current, name) != getattr(target, name):
                    changed.append(name)

        if not changed:
            if persist and self.backend.supports_save:
                try:
                    self.backend.save()
                except BackendError as exc:
                    return ApplyReport(
                        warnings=tuple(warnings),
                        errors=(f"save failed: {exc}",),
                    )
                return ApplyReport(
                    skipped=tuple(dict.fromkeys(skipped)),
                    warnings=tuple(warnings),
                    persisted=True,
                )
            return ApplyReport(
                skipped=tuple(dict.fromkeys(skipped)),
                warnings=tuple(warnings),
            )

        log.info("Applying %d field(s): %s", len(changed), ", ".join(changed))
        try:
            self.backend.write_settings(
                target,
                changed,
                previous=current,
                persist=persist,
            )
        except BackendError as exc:
            rollback_ok = False
            try:
                self.backend.write_settings(
                    current,
                    changed,
                    previous=target,
                    persist=False,
                )
                rollback_ok = True
            except BackendError as rollback_exc:
                log.exception("Rollback failed: %s", rollback_exc)
                message = (
                    f"apply failed: {exc}; rollback also failed: {rollback_exc}. "
                    "Power-cycle the wheel before continuing."
                )
                return ApplyReport(
                    fields=tuple(changed),
                    skipped=tuple(dict.fromkeys(skipped)),
                    errors=(message,),
                    warnings=tuple(warnings),
                )
            return ApplyReport(
                fields=tuple(changed),
                skipped=tuple(dict.fromkeys(skipped)),
                errors=(f"apply failed and was rolled back: {exc}",),
                warnings=tuple(warnings),
                rolled_back=rollback_ok,
            )
        return ApplyReport(
            fields=tuple(changed),
            skipped=tuple(dict.fromkeys(skipped)),
            warnings=tuple(warnings),
            persisted=persist,
        )
