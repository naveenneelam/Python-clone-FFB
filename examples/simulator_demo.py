"""Small API example: apply a built-in profile to the simulator.

Run from the repository root:

    python examples/simulator_demo.py
"""

from __future__ import annotations

import time

from pyffb.backends import make_backend
from pyffb.config import ProfileLibrary
from pyffb.controller import SafetyPolicy, WheelController


def main() -> None:
    library = ProfileLibrary()
    profile = library.get("acc")

    backend = make_backend("simulator")
    controller = WheelController(backend, SafetyPolicy(max_power_pct=80))
    controller.connect("simulator")
    try:
        report = controller.apply_profile(profile, include_geometry=True, persist=False)
        print("apply:", "ok" if report.ok else report.errors)
        for _ in range(5):
            telemetry = controller.read_telemetry(profile.settings.rotation_deg)
            print(
                f"position={telemetry.position_deg:+.1f}deg "
                f"torque={telemetry.torque_pct:+.1f}% "
                f"ffb={telemetry.ffb_active}"
            )
            time.sleep(0.25)
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
