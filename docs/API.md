# Python API

PyFFB is usable as a library. The simulator is the safest place to start.

## Apply a profile to the simulator

```python
from pyffb.backends import make_backend
from pyffb.config import ProfileLibrary
from pyffb.controller import SafetyPolicy, WheelController

library = ProfileLibrary()
profile = library.get("acc")

backend = make_backend("simulator")
controller = WheelController(backend, SafetyPolicy(max_power_pct=80))
info = controller.connect("simulator")
print(info.firmware)

report = controller.apply_profile(profile, include_geometry=True, persist=False)
print(report.ok, report.fields)

telemetry = controller.read_telemetry(profile.settings.rotation_deg)
print(telemetry.position_deg, telemetry.torque_pct, telemetry.ffb_active)

controller.disconnect()
```

## Connect to OpenFFBoard

```python
from pyffb.backends import make_backend
from pyffb.controller import SafetyPolicy, WheelController

backend = make_backend("openffboard")      # requires pyserial
controller = WheelController(backend, SafetyPolicy(max_power_pct=70))
try:
    info = controller.connect("COM5")
    read = controller.read_settings()
    print(info.display_name, info.firmware)
    print(read.settings.power_pct, read.settings.rotation_deg)
    print("missing:", read.missing)
finally:
    controller.disconnect()
```

`connect()` probes `sys.swver?`. It raises `BackendError`/`BackendTimeout` and closes the port if
the selected device does not identify as OpenFFBoard.

## Models

### `WheelSettings`

Immutable, validated canonical tune.

```python
from pyffb.models import WheelSettings

settings = WheelSettings(power_pct=65, rotation_deg=540)
settings, warnings = settings.validated()
changed = settings.merged(endstop_pct=35)
data = settings.to_dict()
restored = WheelSettings.from_dict(data)
```

Fields are documented in [USER_GUIDE.md](USER_GUIDE.md#6-tuning) and mapped in
[PROTOCOL.md](PROTOCOL.md).

### `Profile`

```python
from pyffb.models import Profile, WheelSettings

profile = Profile(
    id="custom-my-game",
    name="My game",
    game="My Game",
    exe_names=("mygame.exe",),
    description="Road-car baseline",
    notes=("Use 900 degree range.",),
    settings=WheelSettings(power_pct=65),
)
profile, warnings = profile.validated()
```

IDs must match `^[a-z0-9][a-z0-9._-]{1,63}$`. Executable names are normalized to lower-case
basenames.

### `Telemetry`

All optional values are `None` when unavailable.

```python
Telemetry(
    position_deg=12.5,
    position_pct=2.8,
    torque_pct=-14.2,
    speed_dps=40.0,
    ffb_active=True,
    supply_voltage=48.0,
    temperature_c=41.0,
)
```

### `ApplyReport`

```python
report.ok
report.fields       # changed canonical field names
report.skipped      # e.g. geometry excluded in auto mode
report.errors
report.warnings
report.persisted
report.rolled_back
```

## `WheelController`

| Method | Purpose |
|---|---|
| `connect(port)` | Open backend and probe identity |
| `disconnect()` | Close transport |
| `read_settings()` | Read canonical fields, with `missing` list |
| `read_telemetry(rotation_deg=900)` | Query live telemetry |
| `apply_settings(settings, include_geometry=True, persist=False, fields=None)` | Diff, write, rollback on failure |
| `apply_profile(profile, include_geometry=True, persist=False)` | Profile wrapper |
| `save()` | `sys.save` |
| `center_axis()` | Set current position as 0° |
| `emergency_stop()` | Best-effort `axis.0.power=0` + `main.0.estop=1` |
| `raw_command(query)` | Read-only diagnostic query; writes blocked |

### Apply semantics

- `include_geometry=False` strips `rotation_deg` and `invert` from the write set.
- `persist=True` writes flash; this can wear it if called repeatedly.
- If the target condition filters are disabled, their fields are skipped.
- A write failure triggers a best-effort rollback to the pre-read settings.
- The app's power cap clamps the target before writing.

### Threading

`WheelController` and backend transports are synchronous. The GUI serializes device work through
one worker. Do not call the same controller concurrently from multiple threads without external
locking; the OpenFFBoard backend does protect individual serial exchanges, but a whole profile
apply is not atomic at the transport level.

### Raw commands

`WheelController.raw_command()` accepts read queries ending in `?` and rejects writes/executes.
The exception is `axis.0.zeroenc`, which is a side-effecting GET; use `center_axis()`.

A low-level backend's `raw_command()` can write. It is an escape hatch for trusted scripts, not
the app UI, and bypasses the safety cap and validation. If you use it, you own the consequences.

## Creating/importing profiles

```python
from pathlib import Path

from pyffb.config import ProfileLibrary, export_profile, import_profile
from pyffb.models import WheelSettings

library = ProfileLibrary()
profile = library.make_custom(
    "My ACC",
    WheelSettings(power_pct=60),
    game="Assetto Corsa Competizione",
    exe_names=("AC2-Win64-Shipping.exe",),
    notes=("Low-grip baseline.",),
)

export_profile(profile, Path("my-acc.json"))
loaded = import_profile(Path("my-acc.json"))
library.add_custom(loaded)
```

Custom profiles can be persisted by writing them into `AppConfig.custom_profiles` and saving via
`ConfigStore`; the GUI does this automatically.

## Backend extension

Subclass `pyffb.backends.base.WheelBackend` and implement every abstract method. Register the
class in `pyffb/backends/__init__.py`.

Guidelines:

- validate command replies; do not assume a write succeeded;
- never expose motor/current configuration through the canonical model without a separate safety
  design;
- keep the read path tolerant of missing telemetry;
- raise `BackendError` subclasses for transport/protocol failures;
- keep I/O synchronous for one operation; the controller/GUI provides serialization;
- document firmware versions and command semantics.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the layering and transaction model.
