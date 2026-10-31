# Public-behavior analysis of the EMC Pro category

This document records the interoperability analysis that informed PyFFB. It is not a
decompilation report and contains no proprietary code or private protocol.

## Sources examined

Only public material was used:

- the public EMCFFBV2 repository README, which describes itself as a USB HID force-feedback
  firmware for ESP32/STM32 platforms and states that its source is not distributed;
- the public EMCFFBV2 wiki pages for the utility, axes, buttons and motor configuration;
- public product/demo descriptions of EMC Pro and DIY wheel builds;
- the USB HID PID force-feedback model;
- the MIT-licensed OpenFFBoard firmware, command wiki and configurator guide.

No EMC binary was decompiled, disassembled, debugged, extracted or redistributed. The EMCFFBV2
README's public terms expressly prohibit reverse engineering, which is why this project stops at
public behavior and builds an independent implementation on an open firmware instead.

## What the product category does

The public material supports a two-part architecture:

```text
PC racing game
   │  standard DirectInput / HID PID effects
   ▼
Microcontroller firmware (real-time)
   │  motor driver + encoder + FOC/PWM loop
   ▼
Physical FFB wheel

PC utility (configuration, telemetry, flashing)
   │  USB CDC / HID feature commands
   ▼
Microcontroller configuration state
```

Key consequences:

1. **The firmware, not the PC utility, is the HID FFB device.** The game talks to the MCU, not to
   the GUI. A Python program cannot replace this layer without a signed virtual HID driver.
2. **The utility's job is management.** It exposes force-feel settings, steering geometry,
   profiles, effect gains/filters, live values, and hardware-specific commissioning.
3. **“Compatible with all racing games” is a property of the HID device and the game's wheel
   support**, not of a configuration UI. Standard PID FFB is broadly supported; proprietary
   wheel whitelists and console-only titles are not.
4. **Motor commissioning is safety-critical.** Motor current, encoder alignment, pole pairs,
   voltage/regeneration limits and brake resistors cannot be treated as ordinary UI settings.

## Functional requirements derived from public behavior

| Requirement | Why it matters | PyFFB approach |
|---|---|---|
| Real-time HID FFB | Games expect a hardware wheel | OpenFFBoard firmware |
| Overall strength / effect gains | Primary feel control | Canonical percentages mapped to firmware |
| Spring, damper, friction, inertia | Road feel and stability | Both game-condition gains and always-on axis effects |
| Endstop and idle spring | Parking/menu feel and mechanical limits | Supported |
| Steering range and invert | Match car/game geometry | Supported; auto-application opt-in |
| Center/zero | Establish physical centre | Dedicated confirmed action |
| Live torque/position/speed | Validate wiring and tuning | Polling telemetry |
| Profiles and save/load | Repeatable setups | JSON profiles, built-ins, import/export |
| Per-game switching | Different titles need different feel | Executable detection state machine |
| Effect filtering | Reduce harsh/noisy FFB | Constant + optional condition filters |
| Safe writes | Bad values can hurt hardware | Validation, power cap, diff, rollback |
| No motor-current GUI | Risk of damage/injury | Deliberately excluded; use firmware tools |
| Firmware flashing | Fits utility category | **Not implemented**; use OpenFFBoard tools |
| Button/LED/shifter config | Hardware-specific | **Not implemented** |

## Why the Python application does not implement HID FFB itself

A Python “virtual wheel” would need one of:

- a signed kernel-mode HID/FFB driver;
- a USB gadget controller on a Linux device (not available on typical Windows gaming PCs);
- emulation of a commercial wheel with proprietary identity and behavior.

These approaches add installation friction, kernel/anti-cheat risk, and a real-time scheduling
problem without improving force quality. They also do not solve games that ignore standard
DirectInput FFB. The chosen clean-room solution uses a proven open firmware for the HID device and
keeps the Python layer focused on configuration, profiles and observability.

## What was intentionally not reproduced

- EMC private serial/HID command IDs and value semantics.
- EMC firmware motor-control, FOC/current-loop, encoder, PID or anti-cogging implementation.
- EMC activation/licensing checks.
- EMC button/LED/ESP-NOW features.
- EMC firmware flashing.
- Any visual assets, icons or strings copied from the utility.
- Any claim that an EMC board can be configured by PyFFB.

## Compatibility decision

PyFFB targets OpenFFBoard's public command interface because it is MIT-licensed, documented, and
already presents a standard HID FFB device. This gives games the best chance of working without
game-specific code. Per-title profiles are a convenience layer, not an emulation layer.

If an EMC-compatible adapter is required later, the correct route is a documented, permitted
protocol from the vendor (or a compatible open protocol). The existing `WheelBackend` interface
supports that without contaminating the rest of the app.

## Acceptance criteria used

The implementation was considered functionally complete for this scope when it could:

1. connect to an OpenFFBoard-compatible wheel and identify it;
2. read and write the force-feel settings without touching motor/current/encoder registers;
3. apply a game profile transactionally and roll back on failure;
4. save explicitly and never silently persist during auto-switching;
5. switch profiles from executable detection without repeated writes for the same game;
6. show live telemetry and a read-only diagnostic console;
7. run the whole flow against a simulator;
8. pass automated protocol/model/controller/CLI/backend tests and a GUI smoke test;
9. document game, hardware, safety and legal limits honestly.

Hardware acceptance remains a manual, physical safety test; see [TESTING.md](TESTING.md) and
[SAFETY.md](SAFETY.md).

## Bottom line

The publicly observable app category is reproducible in Python **as a manager of an open HID FFB
firmware**. Replacing the licensed firmware or promising every game would require a different,
driver-level project and would not be clean-room. PyFFB therefore implements the useful,
defensible layer: safe tuning, profiles, automation, telemetry and diagnostics.
