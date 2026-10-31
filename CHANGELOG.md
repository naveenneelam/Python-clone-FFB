# Changelog

All notable changes are recorded here. This project follows semantic versioning once it reaches
1.0.

## [0.1.0] - 2026-10-25

### Added

- Clean-room Python FFB wheel manager, project name PyFFB Studio.
- OpenFFBoard USB CDC backend:
  - identity probe using `sys.swver?`;
  - line-based command transport with tolerant reply parser;
  - field-level settings read/write;
  - safe power ordering, explicit save and read-only raw queries;
  - best-effort software emergency stop;
  - axis centering via `zeroenc`;
  - live position, torque, speed, FFB, voltage and temperature telemetry.
- Deterministic no-hardware simulator with write/flash failure injection.
- Transactional apply with old-settings rollback and application power cap.
- 27 conservative built-in profiles for popular sim-racing titles.
- Custom profiles, duplication, metadata editing, JSON import/export and desktop profile.
- Automatic game detection by executable with debounced start/switch/exit state machine.
- Tkinter desktop UI:
  - Dashboard with vector gauge, metrics and quick feel controls;
  - full Tuning editor with constant/custom filters and Center axis;
  - Profiles library and editor;
  - Game Sync automation and executable mapping table;
  - read-only Diagnostics console, self-test, copyable report and log;
  - About/safety/clean-room view.
- CLI: GUI, devices, info, apply, profiles, watch, simulate, doctor and config.
- Atomic config storage with timestamped corruption backup and rotating logs.
- 27 built-in profiles; 48+ automated tests including fake serial transport and optional GUI smoke.
- Documentation: user guide, games, hardware, safety, architecture, protocol, clean-room notes,
  API, testing and roadmap.
- Windows install/run helper scripts, example profile and simulator API example.

### Safety / scope

- No motor current, encoder, driver, voltage/regeneration, brake-resistor or bootloader writes.
- No EMC firmware/utility reverse engineering, private protocol, redistribution or activation
  bypass.
- No game injection or virtual HID kernel driver.

### Known limitations

- Hardware validated only against the public OpenFFBoard 1.16.x command set and simulator; physical
  acceptance testing is required.
- No claim of universal game compatibility; see `docs/GAMES.md`.
- Firmware flashing and button/LED/shifter configuration remain in OpenFFBoard tooling.

## Unreleased

- Nothing yet.
