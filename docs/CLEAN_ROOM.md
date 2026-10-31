# Clean-room provenance, scope and legal notes

## Why this document exists

The original request was to reverse engineer the EMC Pro application and rebuild it in Python.
This project takes the functional intent — a practical FFB wheel manager for racing games — but
does not reverse engineer, decompile, patch, redistribute or bypass any EMC product.

This is a deliberate technical and legal boundary, not an omission.

## What "EMC Pro" is

Public material describes EMC Pro/EMCFFBV2 as firmware plus a configuration utility for DIY
force-feedback wheels. The firmware runs on microcontrollers such as STM32/ESP32, presents a USB
HID force-feedback device, and performs the real-time motor control loop. The PC utility configures
effects, axes, motor parameters, buttons, profiles and firmware.

The public EMCFFBV2 repository contains compiled firmware and utility software only. Its public
README states, among other terms:

- binary-only distribution;
- reverse engineering expressly prohibited;
- redistribution not allowed;
- FFB activation is licensed per device and attempts to bypass it are described as illegal.

Those terms are incompatible with decompiling the utility, extracting its private protocol or
reimplementing its licensed FFB activation. PyFFB does none of that.

## What was used

Only public interoperability information:

- USB HID PID (Physical Interface Device) force-feedback concepts and the standard effect model.
- Public EMC feature documentation, used to understand the *category* of functionality a wheel
  manager needs: global strength, spring/damper/endstop, effect gains, wheel range, profiles and
  telemetry.
- OpenFFBoard's MIT-licensed firmware and public command documentation for the actual hardware
  backend.
- Python, Tkinter, pyserial and general Windows process/serial documentation.

No EMC binary was downloaded, disassembled, instrumented or copied for this project. No EMC wire
protocol is implemented. No activation or licensing check is touched.

## Feature mapping

| EMC utility concept | PyFFB equivalent | Status |
|---|---|---|
| Overall FFB strength | `power_pct` → `axis.0.power` | Implemented |
| Desktop/idle spring | `idle_spring_pct` → `axis.0.idlespring` | Implemented |
| Global damper | `global_damper_pct` → `axis.0.axisdamper` | Implemented |
| Endstop | `endstop_pct` → `axis.0.esgain` | Implemented |
| Torque plot / live status | Dashboard + telemetry poll | Implemented |
| Effect filter / gains | Constant filter, optional condition filters, four gain scalers | Implemented |
| Steering angle | `rotation_deg` → `axis.0.degrees` | Implemented |
| Invert steering | `invert` → `axis.0.invert` | Implemented |
| Center steering | `axis.0.zeroenc` command | Implemented |
| Save/load profile | JSON profiles, import/export, built-ins, custom profiles | Implemented |
| Axis input monitor | Position/torque/speed/FFB telemetry | Implemented, read-only |
| Motor telemetry | Voltage, temperature, torque | Partial, read-only |
| Motor current/PID/FOC configuration | Not exposed | Deliberately out of scope |
| Encoder wiring/pole pairs/current limits | Use OpenFFBoard configurator | Deliberately out of scope |
| Firmware flashing | Use OpenFFBoard/DFU tooling | Not implemented |
| Button/LED/shifter/ESP-NOW configuration | Use OpenFFBoard configurator | Not implemented |
| EMC license activation | None | Not applicable; no EMC code or protocol |

Per-game profiles, executable detection, transactional rollback, import/export and a no-hardware
simulator go beyond the basic EMC utility concept.

## Why motor commissioning is excluded

A wrong motor pole count, encoder offset, current limit or voltage limit can destroy a driver,
overheat a motor, or produce an uncontrolled high-torque rotation. Those settings require
hardware-specific commissioning and a physical safety setup. PyFFB intentionally exposes only
the force-feel layer and read-only telemetry.

OpenFFBoard's own configurator remains the correct tool for:

- motor driver selection and PWM/FOC parameters;
- encoder selection, CPR, direction and alignment;
- current, voltage, regeneration and brake-resistor limits;
- button, analog, shifter and LED configuration;
- firmware flashing and bootloader recovery.

## "Compatible with all racing games"

No honest clean-room implementation can guarantee every racing game. The realistic compatibility
contract is:

> If a game supports a standard DirectInput force-feedback wheel, and the firmware presents a
> working HID PID wheel with the needed axes/buttons, the game can send FFB to it. PyFFB can then
> select per-game tuning. Games that whitelist specific commercial wheel IDs, require proprietary
> drivers, or only support gamepad rumble may not work.

PyFFB never hooks or injects into games, so it neither adds nor removes anti-cheat compatibility.
Compatibility is at the OS HID layer. Details and the current profile list are in
[GAMES.md](GAMES.md).

## Trade names

EMC, EMC Pro, EMCFFBV2, OpenFFBoard, Assetto Corsa, iRacing and other names are trademarks of
their respective owners. They are used here only for identification and interoperability
discussion. This project is not affiliated with, sponsored by or endorsed by any of them.

## If EMC hardware support is required

A lawful adapter would require one of:

- public vendor documentation for the PC↔device protocol and permission to implement it; or
- an explicit license/exception from the vendor; or
- an independently published open protocol implementation under compatible terms.

Without that, adding an EMC backend by guessing or decompiling would conflict with the product's
public terms and is out of scope. PyFFB's backend interface is documented so a permitted adapter
can be added later.

## License of this project

PyFFB Studio is MIT-licensed. That license covers the original Python code and documentation in
this repository, not OpenFFBoard firmware, EMC products or game assets.
