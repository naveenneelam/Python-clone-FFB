# Protocols

PyFFB uses two distinct protocols:

1. **Game ↔ firmware:** USB HID PID force feedback. This is not implemented by Python.
2. **PyFFB ↔ firmware:** OpenFFBoard's public ASCII command interface over USB CDC.

No EMC private protocol is used.

## 1. Game-to-firmware force feedback

The game enumerates a HID game controller with a force-feedback (PID) collection. Windows sends
effect reports such as constant force, periodic, spring, damper, friction and inertia. The
firmware's PID implementation maintains effect state, evaluates effects at its control rate, and
converts the result to motor torque.

PyFFB does not see those effect reports. This is intentional:

- latency is deterministic;
- games work when the GUI is closed;
- no kernel driver or virtual device is required;
- Python cannot stall the control loop.

Compatibility therefore depends on the firmware descriptor and PID implementation, not on
PyFFB. OpenFFBoard's FFB Wheel main class is the reference backend for this project.

## 2. PyFFB-to-OpenFFBoard command interface

Source of truth: the public OpenFFBoard wiki and source code (MIT). The interface is line-oriented
UTF-8/ASCII over USB CDC (115200 baud setting is ignored by CDC; it matters for optional UART).

### Request grammar

```text
cls.instance.command?              read
cls.instance.command?address       read with address
cls.instance.command=value         write
cls.instance.command=value?address write with address
cls.instance.command               execute
cls.instance.command!              info/list (not used by PyFFB)
```

PyFFB uses newline (`\r\n`) terminated commands.

### Reply grammar

```text
[cls.instance.command?|value]
[cls.instance.command=value|OK]
[cls.instance.command|OK]
[cls.instance.command?|ERR]
```

Boolean values are `0` or `1`. Integers are decimal; OpenFFBoard's parser also accepts `x`-prefixed
hex values on input. Multi-value replies use newlines or `value:address` and are not used by the
canonical setting model.

The backend parser tolerates boot banners and unknown lines rather than desynchronising on them.

### Probe sequence

On connect:

```text
→ sys.swver?
← [sys.swver?|1.16.5]
→ sys.hwtype?
← [sys.hwtype?|...]
```

If `sys.swver?` does not answer within 2.5 seconds, PyFFB closes the port and reports that the
selected device is not a responding OpenFFBoard firmware. This avoids writing settings to an
unrelated serial device.

### Fields and raw scaling

All canonical fields are validated in `pyffb/models.py`. Percentages are converted only at the
backend boundary.

| PyFFB field | OpenFFBoard command | Raw encoding | Notes |
|---|---|---|---|
| `power_pct` | `axis.0.power` | `round(pct/100 × 32767)` | absolute torque scaler |
| `rotation_deg` | `axis.0.degrees` | integer degrees | change may be applied at update |
| `invert` | `axis.0.invert` | 0/1 | direction |
| `endstop_pct` | `axis.0.esgain` | `pct → 0..255` | soft endstop |
| `idle_spring_pct` | `axis.0.idlespring` | `pct → 0..255` | active when game FFB idle |
| `global_damper_pct` | `axis.0.axisdamper` | `pct → 0..255` | always-on axis damper |
| `global_friction_pct` | `axis.0.axisfriction` | `pct → 0..255` | always-on friction |
| `global_inertia_pct` | `axis.0.axisinertia` | `pct → 0..255` | always-on inertia |
| `game_effect_ratio_pct` | `axis.0.fxratio` | `pct → 0..255` | scales game effects, not endstop |
| `max_speed_dps` | `axis.0.maxspeed` | integer °/s | 0 disables the limiter |
| `torque_rate` | `axis.0.maxtorquerate` | counts/ms | 0 disables slew limiting |
| `expo` | `axis.0.expo` | -127..127 | 0 = linear |
| `spring_gain_pct` | `fx.0.spring` | `pct → 0..255` | firmware gain |
| `damper_gain_pct` | `fx.0.damper` | `pct → 0..255` | firmware gain |
| `friction_gain_pct` | `fx.0.friction` | `pct → 0..255` | firmware gain |
| `inertia_gain_pct` | `fx.0.inertia` | `pct → 0..255` | firmware gain |
| `friction_ramp_pct` | `fx.0.frictionPctSpeedToRampup` | 0..100 | speed ramp zone |
| `constant_filter_hz` | `fx.0.filterCfFreq` | Hz | 1 kHz loop; max below Nyquist |
| `constant_filter_q` | `fx.0.filterCfQ` | Q × 100 | raw 70 = Q 0.70 |
| `condition_filters_enabled` | `fx.0.filterProfile_id` | 0 = stock, 1 = custom | |
| `condition_friction_hz/q` | `fx.0.friction_f/q` | Hz / Q×100 | only when custom profile active |
| `condition_damper_hz/q` | `fx.0.damper_f/q` | Hz / Q×100 | only when custom profile active |
| `condition_inertia_hz/q` | `fx.0.inertia_f/q` | Hz / Q×100 | only when custom profile active |

**Important:** the four `fx` gains are firmware multipliers, not normalised output percentages.
OpenFFBoard's stock defaults are approximately spring 25%, damper 25%, friction 100%, inertia 50%
(raw 64, 64, 254, 127). Setting all of them to 100% may feel dramatically stronger than stock.

### Reads

A full settings read queries every mapped field. Failures are returned as `missing` fields rather
than silently collapsing the entire read. The GUI shows incomplete reads as a warning.

Telemetry reads:

| Value | Command | Conversion |
|---|---|---|
| position | `axis.0.curpos?` | -32767..32767 → -100..100%, × range/2 → degrees |
| torque | `axis.0.curtorque?` | signed normalized torque → -100..100% |
| speed | `axis.0.curspd?` | firmware degrees/second |
| FFB active | `main.0.ffbactive?` | 0/1 |
| supply | `sys.vext?` | millivolts; divided by 1000 if > 2000 |
| temperature | `sys.temp?` | °C |

### Write ordering

For every apply, PyFFB sends only changed fields. Power is special:

1. If target power is lower than current, write power first to reduce torque immediately.
2. Write gains, conditioning, endstop, geometry, ratios, limits and filters.
3. If target power is higher, write power last.
4. If requested, execute `sys.save`.

If enabling a custom conditional-filter profile, the six filter coefficients are written before
`filterProfile_id=1`. If disabling, the profile ID is returned to 0.

### Centre command

```text
→ axis.0.zeroenc?
← [axis.0.zeroenc?|OK]
```

The firmware executes an origin reset on the GET. It does not move the motor. PyFFB exposes this
as **Center axis**, with a confirmation dialog and a textual warning.

### E-stop

PyFFB sends, independently of normal apply logic:

```text
→ axis.0.power=0
→ main.0.estop=1
```

The first command is an immediate software torque scaler; the second invokes the firmware's
emergency stop. Success is reported only if at least one is acknowledged. This is **best effort**.
A hardware power contactor / E-stop is mandatory.

### Save

```text
→ sys.save
← [sys.save|OK]
```

Save is only triggered by explicit **Apply & save** or by the opt-in auto-persist setting.
Auto-switching defaults to RAM writes to avoid flash wear.

### Raw console

The GUI diagnostic console is **read-only**. It allows normal commands ending in `?`, but blocks
writes, execute actions and side-effecting GET commands (`zeroenc`, reboot, DFU, flash, format,
error-clear, OTP). This prevents bypassing the application safety cap and field validation. Use
Tuning for writes and the dedicated Center axis button for `zeroenc`.

The Python backend API exposes a lower-level `raw_command` that can write. It is intended for
trusted integrations and requires the caller to take responsibility for safety.

## Example session

```text
→ sys.swver?
← [sys.swver?|1.16.5]
→ axis.0.power?
← [axis.0.power?|22937]
→ axis.0.power=13107
← [axis.0.power=13107|OK]
→ axis.0.degrees=540
← [axis.0.degrees=540|OK]
→ fx.0.spring=89
← [fx.0.spring=89|OK]
→ sys.save
← [sys.save|OK]
```

## Version sensitivity

Command names and behaviour come from OpenFFBoard 1.16.x public documentation/source. Firmware
can change. If a command fails:

1. Run `pyffb info` or use the diagnostic console to check firmware identity.
2. Compare the command list against the matching OpenFFBoard wiki/source revision.
3. Do not guess write semantics for motor/current commands. Use OpenFFBoard's own tooling.

PyFFB has no dependency on OpenFFBoard's HID command report format; it uses CDC text commands,
which are easier to inspect and test.

## Why not use EMC's protocol?

The EMCFFBV2 distribution is binary-only and prohibits reverse engineering. PyFFB does not
implement or infer its protocol. A permitted vendor adapter could implement `WheelBackend` if
public documentation and authorization exist. See [CLEAN_ROOM.md](CLEAN_ROOM.md).
