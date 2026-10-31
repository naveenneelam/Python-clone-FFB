# Architecture

## Goal

Build a reliable, testable Python manager for a standards-compliant FFB wheel:

- configure force feel without touching dangerous motor commissioning parameters;
- apply per-game profiles automatically;
- display useful telemetry;
- fail safely if a write or connection fails;
- remain portable enough to support another firmware backend later.

## Non-goals

- Real-time FFB calculation on the PC.
- A virtual USB HID wheel or kernel driver.
- Game process injection, memory reading, anti-cheat changes or DLL mods.
- Firmware flashing or motor current/encoder/brake-resistor configuration.
- Byte-for-byte reproduction of a commercial utility UI or private protocol.

## Real-time boundary

```text
Game process
  │  DirectInput / HID PID effect reports
  ▼
Operating-system HID stack
  │  USB interrupt transfers
  ▼
Wheel firmware (millisecond loop)
  │  current / torque command
  ▼
Motor driver → motor → hands

             ┌──────────────────────────────┐
             │ PyFFB Studio                  │
             │ profiles, tuning, game watch │
             └──────────────┬───────────────┘
                            │ USB CDC ASCII commands
                            ▼
                    Wheel firmware configuration
```

Force feedback must be deterministic and preemptive. USB, Python's GIL and desktop scheduling are
not appropriate places for the 1 kHz current loop. Putting Python between the game and the motor
would also require a virtual HID driver and would make every game dependent on Python running.
The firmware is therefore the FFB device, and PyFFB is a management client.

## Layers

```text
pyffb.cli / pyffb.gui
        │
        ▼
WheelController ── SafetyPolicy
        │              validation, power cap
        │              diff, transactional apply, rollback
        ▼
WheelBackend (abstract)
        ├── OpenFFBoardBackend  (USB CDC + reader thread)
        └── SimulatedBackend    (deterministic in-process model)
        │
        ▼
models.py   WheelSettings, Profile, Telemetry, ApplyReport, DeviceInfo
protocol.py command grammar, reply parser, percent↔raw scaling
config.py   atomic AppConfig store, ProfileLibrary
gamewatch.py process snapshot, executable matching, session state machine
presets.py  built-in profiles
```

### `models.py`

The canonical, backend-independent data model. Percentages are used for user-facing force
values. This keeps profiles portable and prevents firmware-specific integers leaking into the UI.

Key invariants:

- all settings are validated and clamped to documented ranges;
- profiles have stable lowercase IDs and lower-case executable names;
- telemetry uses `None` for unavailable values rather than inventing zeros;
- apply results are immutable and carry warnings, errors and rollback state.

### `protocol.py`

Implements the public OpenFFBoard ASCII grammar. It parses tolerant serial replies such as:

```text
[axis.0.power?|22937]
[axis.0.power=20000|OK]
[sys.save|OK]
```

It also provides round-trip percentage scalers for 8-bit gains and 15-bit axis power. The parser
tolerates boot noise and ignores non-protocol lines.

### `backends/`

`WheelBackend` defines the transport contract. No GUI code is imported here.

#### OpenFFBoardBackend

- Opens a pyserial CDC port at 115200 (CDC ignores baud, but UART fallback may use it).
- Starts a daemon reader thread.
- Serialises commands with a condition variable and command lock.
- Probes `sys.swver?` on connect to avoid talking to an unrelated serial device.
- Ensures a write only reports success when the firmware returns `OK`.
- Writes power down before other changes and up last.
- Optionally persists with `sys.save`.
- Implements best-effort E-stop by zeroing axis power and invoking `main.0.estop`.

#### SimulatedBackend

Maintains a thread-safe simulated wheel with smooth synthetic position, speed, torque, voltage and
temperature. It applies field-level writes just like real hardware, records write history, can
simulate write/flash failures, and supports E-stop. It is the basis of UI development and most
tests.

### `controller.py`

`WheelController` owns one connected backend. It is responsible for policy rather than transport.

#### Apply transaction

1. Validate the requested settings; clamp and collect warnings.
2. Enforce the application power cap.
3. Read the current device state.
4. Diff canonical fields.
5. Remove geometry fields if auto mode has geometry disabled.
6. Remove condition-filter fields while custom filters are disabled.
7. Send only the changed fields through the backend.
8. If any write fails, write the previous values back and mark the report rolled back.
9. Persist only when explicitly requested.

This means a failed game-profile switch does not intentionally leave the wheel in a half-applied
state. Rollback is best-effort; if it also fails, the report tells the user to power-cycle the
wheel.

### `gamewatch.py`

`process_snapshot` reads process names via psutil when available, otherwise `tasklist`/`ps`.
`find_running_game` matches normalized executable basenames against profile mappings. Custom
profiles win over built-ins.

`GameSession` is a small state machine that emits at most one change per start/switch/exit:

```text
idle ──game starts──▶ game profile ──game exits──▶ desktop profile
  ▲                         │
  └──── game switches ◀─────┘
```

The GUI calls this every two seconds. It never re-applies the same profile just because the game
is still running.

### GUI

Tkinter with a single-threaded Tk event loop. Device I/O uses one `ThreadPoolExecutor` worker:

- commands are serialized;
- telemetry polls skip while user I/O is active;
- results return to the Tk thread via a polling loop, never by touching widgets from a worker;
- E-stop uses its own thread because a safety action must not wait behind queued profile work;
  the backend command lock still serialises the actual serial transaction.

Views are isolated and receive lifecycle callbacks:

```python
on_show()
on_telemetry(telemetry)
on_connection_changed()
on_settings_changed()
on_profiles_changed()
on_game_changed(detected)
```

The GUI never computes force feedback and never writes motor parameters.

### Configuration

- Config and custom profiles: JSON, atomic replace, timestamped backup on corruption.
- Windows: `%APPDATA%\PyFFB\config.json`
- macOS: `~/Library/Application Support/PyFFB/config.json`
- Linux: `$XDG_CONFIG_HOME/pyffb/config.json` or `~/.config/pyffb/config.json`
- Override with `PYFFB_CONFIG_DIR` or `--config-dir`.
- Logs: `<config>/logs/pyffb.log`, rotating 1.5 MB × 3.

Profiles are not stored in wheel flash unless the user explicitly chooses **Apply & save**.
Automatic game switching defaults to RAM-only writes to avoid flash wear.

## Safety model

Two independent layers are expected:

1. **Hardware**: fuse, emergency stop, contactor, motor current limit in firmware. Mandatory.
2. **Application**: `SafetyPolicy` power cap and immutable validation. Convenience guard only.

PyFFB deliberately does not write:

- motor current limit;
- encoder type/CPR/direction/zero unless the user explicitly invokes the separate **Center axis**
  action (`zeroenc`), which changes coordinate origin only;
- motor driver, pole pairs, PID, filters at the motor-current layer;
- DC voltage, regeneration, brake resistor;
- flash bootloader or firmware.

## Extending to another firmware

Implement `WheelBackend`:

```python
class MyBackend(WheelBackend):
    key = "myfw"
    display_name = "My firmware"
    @classmethod
    def list_devices(cls): ...
    def connect(self, port=""): ...
    def disconnect(self): ...
    @property
    def connected(self): ...
    @property
    def info(self): ...
    def read_settings(self): ...
    def write_settings(self, target, fields, previous, persist=False): ...
    def read_telemetry(self, rotation_deg): ...
    def save(self): ...
    def center_axis(self): ...
    def emergency_stop(self): ...
    def raw_command(self, command): ...
```

Then register it in `pyffb/backends/__init__.py`. Keep dangerous commissioning commands out of
the canonical model unless there is a clear, tested safety design.

## Failure modes

| Failure | Behaviour |
|---|---|
| Wrong port | Connect times out probing `sys.swver?` and closes the port |
| USB unplug | Reader marks link down; telemetry fails; UI marks connection lost |
| Firmware rejects a field | Write raises; controller restores previous fields |
| Core fields cannot be read | Apply is refused rather than guessing defaults for power/range/invert/endstop |
| Flash save fails | Report error; RAM rollback is attempted |
| E-stop software command fails | UI insists on the hardware kill switch |
| Config JSON corrupted | Rename to timestamped backup, start with defaults |
| No pyserial | Clear dependency message; simulator remains available |
| Game executable renamed | No auto match; manual profile still works; edit custom mapping |

## Why not a virtual HID driver?

A Python virtual wheel would need a kernel-mode virtual HID/FFB device (or a signed driver plus
real-time effect handling). It would add installation friction, driver signing, anti-cheat
surface area and a hard dependency on a running desktop process. It would not improve force
quality compared with firmware that already implements PID effects. The chosen architecture is
simpler, more reliable and portable across games.
