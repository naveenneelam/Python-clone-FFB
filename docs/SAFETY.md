# Safety

> This application controls a motor. A force-feedback wheel can cause serious injury, burns,
> fractures, entanglement, or property damage. You are responsible for the physical build and its
> safety systems.

## Non-negotiable requirements

1. **Physical emergency stop.** A latching switch must remove motor power or drop a contactor,
   independent of USB, the PC, PyFFB and firmware logic. Test it before every session where high
   torque is possible.
2. **Current limit configured in firmware.** Set it conservatively using OpenFFBoard's own tools.
   PyFFB does not configure motor current.
3. **Secure mounting.** The motor and steering shaft must not rotate loose, tip over or pull
   cables. Use bearings and a proper wheel mount.
4. **No hands in pinch points.** Keep fingers, hair, jewellery and loose clothing away from the
   shaft, belts, couplers and spokes.
5. **Fusing and wiring.** Use an appropriate DC fuse, wire gauge, insulation, strain relief and
   grounding. Protect against regeneration over-voltage.
6. **Unattended wheel.** Power down the motor when leaving. Never leave a high-torque wheel
   energised with a child or pet nearby.
7. **Competence.** If you cannot assess electrical, mechanical and thermal risks, get qualified
   help. This is a DIY experimental project, not a certified consumer product.

## What PyFFB's safety cap does

`SafetyPolicy.max_power_pct` (default 90%) clamps the profile/strength value the app writes.
It is useful for preventing accidental 100% profile application. It is **not**:

- a torque guarantee;
- a motor current limit;
- a thermal model;
- a speed limit;
- an emergency stop;
- protection against a bug, wrong firmware mapping or hardware fault.

Changing the cap, using the low-level Python backend, or writing firmware settings can bypass it.
Do not treat the cap as a machine-safety function.

## Software E-stop limitations

The red E-STOP button attempts:

1. `axis.0.power=0`;
2. `main.0.estop=1`.

It then disconnects and asks you to power-cycle. Failure modes include:

- USB unplugged, EMI, driver crash or OS freeze;
- firmware hung or in a bootloader;
- a serial command lost after the physical write;
- the motor driver failing short;
- torque from stored mechanical energy.

If the software stop fails, **use the hardware switch immediately**. The app deliberately shows a
blocking error instead of pretending success.

## Safe first-run protocol

Use a low-current bench setup first.

1. Motor disconnected from the wheel or wheel removed; verify direction and sensors.
2. Current limit set low, ideally enough to overcome friction only.
3. Hardware E-stop tested.
4. Wheel mounted, hands clear, USB cable secured.
5. Run PyFFB's simulator and confirm the UI before connecting hardware.
6. Connect at 0% strength, verify telemetry and centre.
7. Apply 10–20% strength, test endstops at low speed.
8. Test the software E-stop.
9. Test in a game with in-game FFB gain low.
10. Increase torque gradually while checking motor, driver and connector temperatures.

If anything is unpredictable, stop. Do not "tune around" a hardware fault.

## High-torque wheels

Direct-drive wheels can produce enough torque to injure wrists and hands. Specific risks:

- sudden full torque in the wrong direction from an encoder/phase fault;
- an endstop that drives instead of stopping;
- oscillation that grows until the wheel slams lock-to-lock;
- belt/gear trains crushing fingers;
- a quick-release wheel detaching under torque;
- USB/encoder cable wrap around the shaft.

Mitigations include a slip clutch or torque-limiting coupling, mechanical stops with compliance,
guards, an easily reachable power contactor, and a low firmware current limit. None of these are
provided by PyFFB.

## Thermal and electrical risks

- Stall current can overheat a motor or driver in seconds.
- A PSU that cannot absorb regeneration can raise the DC bus until capacitors fail.
- A brake resistor may become extremely hot; mount it away from flammable material.
- Motor phase connectors can arc if disconnected under load.
- Ground loops through USB and PSU wiring can cause resets or false encoder readings.
- A common-ground fault can put dangerous voltage on the USB shield or chassis.

Power down and wait for capacitors to discharge before rewiring. Use a meter, not your fingers.

## Profile and tuning risks

The built-in profiles prioritize moderate settings, but they cannot know your motor, encoder, PSU
or mechanics. The four `fx` gains are multiplicative: raising all of them can produce far more
torque than expected. Always change one field at a time and keep a hand near the hardware stop.

Do not:

- set strength to 100% before verifying the current limit;
- enable automatic range/invert changes while a game is running unless it is expected;
- use `Apply & save` on an untested setup;
- leave auto-persist on for every game start;
- use profiles copied from another wheel without revalidating torque limits.

## Emergency procedure

If the wheel runs away, oscillates violently, overheats or will not respond:

1. Hit the hardware E-stop / motor contactor.
2. Disconnect the motor PSU if the E-stop fails.
3. Keep hands and cables clear of the shaft.
4. Do not touch a hot motor, driver or resistor.
5. Let capacitors discharge.
6. Record the conditions and inspect wiring/encoder before another test.
7. Do not reapply force until the cause is understood.

## Reporting safety defects

If PyFFB contributes to a dangerous condition, open a private security/safety report as described
in [../SECURITY.md](../SECURITY.md). Do not publish exploit or unsafe hardware details before the
maintainers can respond.

## Disclaimer

This documentation is not engineering certification, medical advice or legal advice. The software
is provided "as is", without warranty. Build and operate at your own risk.
