# Testing and acceptance

## Automated tests

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check pyffb tests
```

Windows PowerShell:

```powershell
python -m pytest -q
python -m ruff check pyffb tests
```

### Coverage by area

| Test file | Covers |
|---|---|
| `test_protocol.py` | command grammar, replies, noise tolerance, scaling, injection rejection |
| `test_models.py` | validation/clamping, bool parsing, profile round-trip, diffs |
| `test_simulator.py` | field-level apply, geometry skip, safety cap, rollback, E-stop, telemetry |
| `test_openffboard_backend.py` | fake serial transport, identity probe, reads, writes, raw queries |
| `test_config.py` | atomic config, corruption backup, custom profiles, export/import |
| `test_gamewatch.py` | executable matching, priority, start/switch/exit state machine |
| `test_profiles.py` | unique IDs, ranges, conservative values, mappings |
| `test_cli.py` | version, JSON listings, dry-run, info, simulator output |
| `test_gui.py` | optional Tk smoke test |

The OpenFFBoard test uses an in-memory serial stand-in. It validates framing, parser behavior and
settings mapping without a motor.

### GUI smoke test

Linux CI needs a display. On Windows:

```powershell
$env:PYFFB_GUI_TEST = "1"
python -m pytest tests/test_gui.py -q
```

The test creates the app withdrawn, connects to the simulator, applies a profile, visits every
view and closes the window.

## What automated tests do not prove

- Motor direction, encoder CPR, current limits or thermal behavior.
- USB CDC reliability under EMI.
- Game compatibility or FFB feel.
- OpenFFBoard firmware revisions newer than the documented command set.
- Safety of a physical build.

Hardware and game testing must be done manually.

## Hardware acceptance test

Prerequisites:

- hardware E-stop tested;
- firmware current limit low;
- wheel secured; hands/clothing clear;
- motor and driver temperatures observable;
- serial log open;
- no game running for the initial checks.

### Stage 1 — identity and telemetry

```bash
pyffb info --port COM5
pyffb doctor
```

Expected:

- plausible firmware/hardware identity;
- no missing critical settings (some optional filters may be missing on older firmware);
- position changes when you move the wheel slowly;
- speed changes sign with direction;
- voltage close to a multimeter reading;
- FFB state changes when a game/test effect is active.

### Stage 2 — zero torque

- Connect.
- Apply a profile with `power_pct=0` through the API or set strength to 0 in Tuning.
- Verify the wheel is free and telemetry still updates.
- Confirm the software E-stop sends commands and requires power-cycle.

### Stage 3 — low torque

- Set firmware current limit to a safe low value.
- Apply generic profile at 10–20% strength.
- Turn slowly lock-to-lock.
- Verify endstop direction, no runaway, no mechanical binding.
- Check torque telemetry sign against actual resistance.

### Stage 4 — game smoke test

For each game in the target list:

1. Start the game without PyFFB and confirm standard wheel detection.
2. Start PyFFB, connect, apply the profile at low strength.
3. Drive one lap at low in-game gain.
4. Record:
   - game build;
   - profile id;
   - in-game gain/range;
   - firmware version;
   - wheel hardware;
   - issues: clipping, oscillation, dead zones, reversed direction, range mismatch.

Stop for any uncontrolled behavior. Do not continue testing while a fault is unresolved.

### Stage 5 — automatic switching

- Enable auto-switching (geometry off).
- Start a mapped game and confirm exactly one apply.
- Alt-tab and wait; confirm no repeated apply.
- Exit and confirm desktop profile applies.
- Rename/duplicate executable mapping in a custom profile and confirm no false matches.

### Stage 6 — persistence

- Apply & save.
- Power-cycle the wheel.
- Reconnect and verify the values persisted.
- Count expected flash writes; avoid auto-persist in daily use.

## Manual game matrix template

| Date | Game/build | Wheel/firmware | Profile | Range | In-game gain | Result | Notes |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

Useful fields to log: strength, endstop, global damper/friction, effect gains, filter settings,
temperature after 10 minutes, and any USB resets.

## Regression testing after firmware changes

1. Run the fake-serial suite (should always pass).
2. Connect and run `pyffb info`.
3. Check every mapped command in the diagnostic console.
4. Compare OpenFFBoard command names/semantics with the firmware revision.
5. Repeat low-torque acceptance before normal use.
6. Update [PROTOCOL.md](PROTOCOL.md) and this document if behavior changed.

## Failure injection

The simulator supports:

```python
backend.fail_next_write = True
backend.fail_save = True
```

Use these to test rollback/error UI. Never inject failures on live hardware.
