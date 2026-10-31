"""Backend contract for wheel firmware.

A backend performs only transport operations.  Profile validation, safety
limits and transaction/rollback semantics live in :class:`pyffb.controller.WheelController`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from ..models import (
    BackendDescriptor,
    DeviceInfo,
    SettingsRead,
    Telemetry,
    WheelSettings,
)
from ..protocol import Reply


class BackendError(RuntimeError):
    """Generic device or transport failure."""


class BackendUnavailable(BackendError):
    """The optional dependency or operating-system facility is missing."""


class BackendTimeout(BackendError):
    """The firmware did not answer in time."""


class BackendCommandError(BackendError):
    """The firmware explicitly rejected a command."""


class WheelBackend(ABC):
    key: str = "base"
    display_name: str = "Wheel backend"
    supports_save: bool = True

    @classmethod
    @abstractmethod
    def list_devices(cls) -> list[BackendDescriptor]:
        """List candidate ports without modifying device state."""

    @abstractmethod
    def connect(self, port: str = "") -> DeviceInfo:
        """Open the transport and verify the firmware identity."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the transport and stop background workers."""

    @property
    @abstractmethod
    def connected(self) -> bool:
        ...

    @property
    @abstractmethod
    def info(self) -> DeviceInfo | None:
        ...

    @abstractmethod
    def read_settings(self) -> SettingsRead:
        ...

    @abstractmethod
    def write_settings(
        self,
        target: WheelSettings,
        fields: Iterable[str],
        previous: WheelSettings,
        persist: bool = False,
    ) -> None:
        """Write selected canonical fields.

        Implementations must raise :class:`BackendError` on any rejected write.
        ``previous`` lets the backend order power changes safely.
        """

    @abstractmethod
    def read_telemetry(self, rotation_deg: int) -> Telemetry:
        ...

    @abstractmethod
    def save(self) -> None:
        """Persist current settings to non-volatile storage when supported."""

    @abstractmethod
    def center_axis(self) -> None:
        """Set the current physical position as the axis centre."""

    @abstractmethod
    def emergency_stop(self) -> None:
        """Immediately command zero torque through the strongest path available."""

    @abstractmethod
    def raw_command(self, command: str) -> Reply:
        """Send an advanced/diagnostic command and return its reply."""

    def __enter__(self) -> WheelBackend:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.disconnect()
