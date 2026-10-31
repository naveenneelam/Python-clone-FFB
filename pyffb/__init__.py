"""PyFFB Studio - a clean-room force-feedback wheel manager.

The package intentionally keeps the real-time FFB path out of Python. Games send
HID PID effects to the wheel firmware; this application configures that firmware,
manages per-game profiles and displays telemetry.
"""

from .version import APP_NAME, __version__

__all__ = ["APP_NAME", "__version__"]
