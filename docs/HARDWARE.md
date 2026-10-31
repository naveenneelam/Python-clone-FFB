# Hardware and firmware setup

> **Read [SAFETY.md](SAFETY.md) first.** A direct-drive wheel can injure you even at moderate
> current. A software configuration guide is not a substitute for an electrical safety review.

## Supported hardware path

PyFFB's only real backend targets **OpenFFBoard** firmware over USB CDC. OpenFFBoard is MIT
licensed and supports several motor-driver families, including:

- TMC4671-based three-phase FOC boards;
- ODrive (CAN);
- VESC (CAN);
- PWM drivers;
- selected integrated servo drives.

Supported MCU/hardware revisions and wiring are defined by OpenFFBoard, not PyFFB. Use the
official OpenFFBoard wiki and hardware repository for the current list:

- <https://github.com/Ultrawipf/OpenFFBoard>
- <https://github.com/Ultrawipf/OpenFFBoard/wiki>
- <https://github.com/Ultrawipf/OpenFFBoard-hardware>
- <https://github.com/Ultrawipf/OpenFFBoard-configurator>

PyFFB has been developed and unit-tested against the public 1.16.x command set and a serial
simulator. It has not been validated on every OpenFFBoard board/revision. Treat first hardware
operation as an acceptance test.

### What about an EMC board?

An EMC board running EMC firmware is **not** a supported PyFFB backend. The EMC firmware/utility
is binary-only and its public terms prohibit reverse engineering. Do not point PyFFB at an EMC
port and expect configuration to work. See [CLEAN_ROOM.md](CLEAN_ROOM.md).

## Reference build categories

You need a complete, mechanically sound FFB wheel, not just a controller board.

| Category | Requirement |
|---|---|
| Controller | A board supported by current OpenFFBoard firmware, with native USB |
| Motor driver | Matched to motor type, voltage and phase current; integrated protection preferred |
| Motor | BLDC/PMSM or brushed DC with suitable torque, Kv and thermal rating |
| Position sensor | Incremental/absolute encoder or supported integrated encoder |
| Power supply | DC PSU with margin, fuse, inrush/regeneration plan |
| Brake resistor | If regeneration can raise the DC bus above safe limits |
| Emergency stop | Physically disconnects motor power / drops contactor, independent of USB/Python |
| Mechanical | Bearing-supported steering shaft, secure wheel mount, finger/pinch guards |
| Wiring | Correct gauge, ferrules, strain relief, shielding for encoder, star grounding |
| Cooling | Motor/driver airflow; thermal protection where possible |

Do not undersize the PSU, fuse, contactor or wiring. Do not use a driver whose H-bridge can be
destroyed by stall current without protection. Do not rely on a software stop for emergency
protection.

## Firmware commissioning (outside PyFFB)

PyFFB intentionally cannot configure the dangerous electrical layer. Use OpenFFBoard's own
configurator for the following.

1. **Flash the correct firmware** for the exact MCU/board revision. Keep a recovery path (DFU
   jumper/button) documented.
2. **Select the FFB Wheel (1 Axis) main class**.
3. **Select the motor driver** and configure PWM/current-loop parameters according to the
   hardware documentation.
4. **Select and calibrate the encoder**: type, CPR, direction, offset/alignment.
5. **Set conservative current limits**, DC voltage limits and regeneration/brake-resistor
   protection before connecting the wheel to a game.
6. **Set a low maximum torque** and verify direction/endstops.
7. **Map buttons/axes/shifter** if needed. PyFFB does not configure HID buttons.
8. **Test the hardware E-stop** while the motor is energised at low torque. It must remove torque
   without relying on USB.
9. **Reboot and verify settings persisted** in the firmware.

Then connect the wheel to PyFFB.

### Power sequencing

Follow the OpenFFBoard hardware guidance for your board. A common sequence is:

- power the motor supply first, then the MCU/control electronics;
- power down in the reverse order, after torque is disabled.

Never hot-plug motor phases. Never connect/disconnect the encoder while the drive is enabled.
Never flash firmware with the motor powered.

## USB and serial connection

On Windows 10/11, OpenFFBoard's USB CDC normally appears as a COM port without a vendor driver.
On Linux it appears as `/dev/ttyACM*`; ensure your user has access:

```bash
sudo usermod -aG dialout "$USER"
# log out and back in
```

Close OpenFFBoard's configurator before connecting PyFFB; two programs cannot reliably own the
same serial port. If the port disappears after flashing, check the bootloader/main-class mode and
the USB cable (data, not charge-only).

## First hardware acceptance test

Do this with the wheel securely mounted, the motor current limit low, and the hardware E-stop
within reach. Remove the steering wheel rim if that makes the test safer.

1. Verify the hardware E-stop stops torque.
2. Start PyFFB, connect, and confirm firmware identity and telemetry.
3. Apply **Desktop / idle** and verify no unexpected motion.
4. Apply **Generic racing wheel** with strength reduced, e.g. 20–30%. If the app cap is 90%,
   reduce the profile value in Tuning before applying.
5. Turn the wheel slowly through its range:
   - no runaway;
   - no grinding or violent endstop;
   - encoder direction matches the game;
   - position returns near centre.
6. Test the software **E-STOP** button at zero/low torque. Then power-cycle and verify recovery.
7. Test a known game at low in-game FFB gain.
8. Increase torque only in small steps while monitoring motor/driver temperature and current.

Stop immediately for:

- uncontrolled rotation or torque;
- a hot motor/driver/connector;
- burning smell;
- encoder skipping or direction reversal;
- a wheel that fights the endstop;
- USB disconnects under load.

## Emergency stop design

A compliant machine design can be complex; this project is not a certified safety system. At a
minimum, provide a clearly labelled, latching mushroom-head switch that physically removes motor
power or drops a contactor. It must work with:

- PyFFB closed;
- USB unplugged;
- the PC frozen;
- firmware hung.

Do not wire an E-stop solely into a microcontroller GPIO. Do not rely on a browser/app/software
button. If you are unsure, have a qualified electrical person review the design.

## Encoder and mechanical notes

- A slipping encoder coupler can cause violent oscillation.
- Verify CPR and gear ratio. A ratio error scales both position and endstop.
- Keep encoder wiring away from motor phase cables; use shielded twisted pairs and a proper
  shield termination.
- Check that the wheel's mechanical range cannot crush fingers or tear the USB cable.
- Use a slip clutch or torque fuse where appropriate.
- Do not use a wheel rim that concentrates impact force on your wrists.

## Updating firmware or PyFFB

- Firmware updates can rename commands or change value semantics. Re-run the acceptance test.
- PyFFB profiles are independent of firmware flashing; they are not stored in the MCU unless you
  choose save.
- Back up profiles with **Profiles → Export** and the config folder.

## Hardware troubleshooting quick table

| Symptom | Check |
|---|---|
| No COM port | USB data cable, bootloader/main mode, driver, another tool holding port |
| Connect probe times out | Wrong firmware/main class, port busy, CDC disabled |
| Wheel input appears but no FFB | HID FFB main class, game sees standard wheel, fuse/PSU, firmware FFB active |
| FFB pulls one direction only | Encoder/phase wiring, driver direction, axis invert, PID sign |
| Weak FFB | firmware current limit, PSU sag, app strength, in-game gain, effect gains |
| Violent oscillation | lower strength/gains, verify encoder, add damper, check mechanical play |
| Motor hot at idle | idle spring/global damper too high, current limit too high, cooling |
| Over-voltage after hard steering | brake resistor/regeneration settings, PSU absorption |
| App disconnects under load | USB cable/grounding, EMI, PSU brownout, hub quality |

Keep a log of firmware version, board revision, motor, encoder, PSU and app version when asking
for help.
