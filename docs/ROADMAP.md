# Roadmap

## Current (0.1.x)

- OpenFFBoard CDC backend with identity probe, field mapping, rollback and save.
- Simulator backend and GUI test.
- 27 built-in profiles, custom profiles, import/export.
- Game detection and opt-in automatic switching.
- Read-only raw diagnostics, self-test, logs and CLI.
- Documentation and hardware acceptance checklist.

## Near term

- Package standalone Windows builds with PyInstaller (unsigned dev builds first).
- Improve firmware detection/version display and command compatibility warnings.
- Add a formal profile schema JSON file for editors.
- Add an optional first-run wizard for wheel range and low-torque test.
- Add more granular game executable aliases when launchers rename binaries.
- Add per-profile "device match" confirmation before applying.
- Add unit tests for raw-console blocking and centre command.

## Medium term

- Linux udev/serial permission guidance and packaging.
- Additional open firmware backends, if their protocols are documented and permissively
  licensed.
- Optional user-defined backend plugin discovery (entry points), still excluding unsafe writes.
- Better telemetry plots and export (CSV) for hardware diagnosis.
- Accessibility pass: keyboard navigation, high-contrast theme, screen-reader labels.
- i18n scaffolding.

## Explicitly not planned

- Decompiling, patching or reimplementing EMC firmware/utility without permission.
- Bypassing license activation or device locks.
- Injecting into games, reading game memory or modifying anti-cheat.
- A virtual HID FFB kernel driver in Python.
- Writing motor current, encoder alignment, voltage/regeneration or brake-resistor parameters from
  PyFFB.
- Claiming universal game compatibility without a tested matrix.

## If EMC support is requested

A lawful EMC adapter requires vendor protocol documentation and permission. A clean-room
implementation can then use the existing `WheelBackend` interface. Pull requests that include
decompiled code, private protocol guesses or license bypasses will be rejected.

## Contribution priorities

1. Safety and rollback correctness.
2. Reproducible hardware compatibility notes.
3. Tests using the simulator/fake transport.
4. Documentation of real limitations.
5. UI polish that does not hide safety state.
