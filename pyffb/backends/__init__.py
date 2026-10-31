"""Available hardware backends."""

from __future__ import annotations

from .base import (
    BackendCommandError,
    BackendError,
    BackendTimeout,
    BackendUnavailable,
    WheelBackend,
)
from .openffboard import OpenFFBoardBackend
from .simulator import SimulatedBackend

BACKENDS: dict[str, type[WheelBackend]] = {
    OpenFFBoardBackend.key: OpenFFBoardBackend,
    SimulatedBackend.key: SimulatedBackend,
}


def make_backend(key: str) -> WheelBackend:
    try:
        factory = BACKENDS[key]
    except KeyError as exc:
        raise BackendError(f"unknown backend: {key!r}") from exc
    return factory()


__all__ = [
    "BACKENDS",
    "BackendCommandError",
    "BackendError",
    "BackendTimeout",
    "BackendUnavailable",
    "OpenFFBoardBackend",
    "SimulatedBackend",
    "WheelBackend",
    "make_backend",
]
