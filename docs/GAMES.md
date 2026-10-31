# Racing game profiles and compatibility

## The compatibility model

PyFFB does not patch games. A game sends standard HID force-feedback effects to the wheel
firmware. The firmware handles the real-time loop. PyFFB selects a set of tuning values before or
while the game runs.

That means:

- **Good:** games that support a DirectInput wheel and standard PID effects can use the firmware
  directly, with or without PyFFB running.
- **Profiles:** PyFFB can tune how that same wheel feels per title.
- **Automation:** PyFFB can watch for a known executable and apply the matching profile.
- **Limits:** games that only accept specific commercial wheel IDs, use proprietary drivers, or
  offer only gamepad rumble may not work. Console-only titles do not use this path.
- **No guarantee:** "all racing games" is not an achievable promise across firmware versions,
  storefronts, anti-cheat builds, mods and wheel hardware. This project documents its supported
  path instead of pretending otherwise.

PyFFB never hooks a game process, reads game memory, modifies anti-cheat or emulates a commercial
wheel. It does not change a game's online/offline or anti-cheat status.

## Built-in profiles

The numbers below are **starting points**, not validated per-car setups. Strength values are
conservative relative to a typical direct-drive wheel; high-torque builds must set the firmware
current limit first.

| Profile id | Game | Default range | Detected executable(s) |
|---|---|---:|---|
| `desktop` | Desktop / idle | 900° | — |
| `generic` | Generic racing wheel | 900° | — |
| `acc` | Assetto Corsa Competizione | 900° | `AC2-Win64-Shipping.exe` |
| `assetto-corsa` | Assetto Corsa | 900° | `acs.exe` |
| `iracing` | iRacing | 900° | `iRacingSim64DX11.exe`, `iRacingSim64.exe` |
| `rf2` | rFactor 2 | 900° | `rFactor2.exe` |
| `le-mans-ultimate` | Le Mans Ultimate | 900° | `Le Mans Ultimate.exe` |
| `ams2` | Automobilista 2 | 900° | `AMS2.exe` |
| `raceroom` | RaceRoom Racing Experience | 900° | `RRRE64.exe` |
| `f1` | EA Sports F1 23/24/25/26 | 360° | `F1_23.exe`, `F1_24.exe`, `F1_25.exe`, `F1_26.exe` |
| `ea-wrc` | EA Sports WRC | 540° | `WRC.exe` |
| `dirt-rally-2` | DiRT Rally 2.0 | 540° | `dirtrally2.exe` |
| `richard-burns-rally` | Richard Burns Rally / RSF | 540° | `RichardBurnsRally_SSE.exe`, `RichardBurnsRally.exe` |
| `beamng` | BeamNG.drive | 900° | `BeamNG.drive.exe` |
| `forza-horizon-5` | Forza Horizon 5 | 900° | `ForzaHorizon5.exe` |
| `forza-motorsport` | Forza Motorsport (2023) | 900° | `ForzaMotorsport.exe` |
| `project-cars-2` | Project CARS 2 | 900° | `pCARS2AVX.exe`, `pCARS2.exe` |
| `project-cars-3` | Project CARS 3 | 900° | `pCars3.exe` |
| `euro-truck-simulator-2` | Euro Truck Simulator 2 | 900° | `eurotrucks2.exe` |
| `american-truck-simulator` | American Truck Simulator | 900° | `amtrucks.exe` |
| `wreckfest` | Wreckfest | 540° | `Wreckfest.exe`, `Wreckfest_x64.exe` |
| `automobilista` | Automobilista | 900° | `Automobilista.exe` |
| `gtr2` | GTR2 | 900° | `GTR2.exe` |
| `race-07` | Race 07 | 900° | `Race_07.exe`, `Race07.exe` |
| `nr2003` | NASCAR Racing 2003 Season | 900° | `NASCAR Racing 2003 Season.exe` |
| `dakar-desert-rally` | Dakar Desert Rally | 540° | `DakarDesertRally.exe` |
| `snowrunner` | SnowRunner | 900° | `SnowRunner.exe` |

Storefront/launcher executables are not used for matching; the simulation executable is. If a
game update renames an executable, automatic switching stops for that title but manual profile
application still works.

## Per-title starting notes

These are in-game and app-level suggestions. Change one variable at a time.

### Assetto Corsa Competizione

- Set in-game FFB gain around 75–85%. Avoid stacking a high PyFFB strength with a high in-game
  gain.
- Let the game set wheel range per car if it supports it.
- Keep global damper modest; ACC's tyre model already produces self-damping.
- If the wheel oscillates in a straight line, reduce PyFFB spring/damper gains before lowering
  in-game gain.

### Assetto Corsa

- Use Content Manager to set wheel range per car and verify the Python wheel axes.
- FFB gain near 80%, minimum force 0–2%.
- Cars with high downforce may feel over-sprung; reduce `spring_gain_pct` or strength.

### iRacing

- Run the game's wheel calibration and force-meter setup after the firmware is flashed.
- PyFFB's idle spring is deliberately 0; iRacing supplies steering feel.
- Use iRacing's strength slider as the primary gain control. The app's strength is a secondary
  torque cap.
- Recalibrate if the firmware wheel range changes.

### rFactor 2 / Le Mans Ultimate

- Start with in-game FFB smoothing 1–2.
- Use a moderate hardware strength and tune per car.
- Lower PyFFB damper if low-speed corners feel syrupy.

### Automobilista 2

- Start with the game's default FFB profile; reduce app strength for high-downforce cars.
- If effects feel exaggerated, lower the condition-effect gains before the in-game gain.

### RaceRoom

- Set in-game FFB strength and steering lock first.
- If the title's automatic wheel range fights PyFFB geometry, disable automatic geometry or leave
  range management to the game.

### EA Sports F1

- Use 360° range and check in-game steering saturation/deadzone.
- F1 titles can feel over-damped; this profile keeps global damper low.
- Strength above the app cap would require changing the cap. Do not do that until the hardware
  current limit is verified.

### EA Sports WRC / DiRT Rally 2.0 / Richard Burns Rally

- 540° is the starting range; check each car's real steering lock.
- Rally FFB includes large loose-surface transients. Lower global friction before increasing
  overall strength.
- For RBR/RSF, run the community installer's wheel setup once, then apply the profile.

### BeamNG.drive

- Enable FFB in-game and reduce smoothing if the wheel feels laggy.
- Soft-body collisions can create sharp torque spikes. Keep the firmware current limit and the
  app strength conservative.

### Forza Horizon 5 / Forza Motorsport

- These games are pad-first. Set in-game FFB scale near 50% and lower vibration.
- Forza may override steering range. Use 900° as a default and verify in a test drive.
- If menus feel loose, raise the idle spring rather than the game FFB gain.

### Project CARS 2 / 3

- Run the game's wheel wizard once. It writes per-wheel settings that the app does not manage.
- Start at 75% in-game gain; tune per tyre/car.

### Truck simulators

- Match the game's steering range to 900° unless you deliberately run a larger range.
- Smoothness matters more than torque. Raise idle spring/damper instead of strength.
- If the wheel oscillates while parked, increase global damper gradually.

### Wreckfest, Dakar, SnowRunner

- Arcade/off-road titles benefit from lower strength and softer endstops.
- SnowRunner's FFB is subtle; do not compensate with abrupt friction changes.

### Legacy SimBin titles (GTR2, Race 07, Automobilista, NR2003)

- Run the game as administrator if it cannot see the controller.
- Verify the game is using the HID wheel, not a keyboard/gamepad fallback.
- Old titles may ignore modern wheel range APIs; set range manually.

## Universal setup checklist

1. Confirm the wheel appears in Windows **Set up USB game controllers** and responds to input.
2. Confirm force feedback works in the firmware's own test (if available) or a known game.
3. In PyFFB, connect and verify position, torque and FFB state.
4. Apply **Generic racing wheel** at low strength.
5. In the game, set wheel range and FFB gain first.
6. Apply the game-specific profile.
7. Tune only the app fields that address the problem:
   - too heavy → strength or in-game gain
   - too springy → spring gain / global damper
   - notchy → friction, speed/torque limits
   - oscillates → damper, lower strength, lower spring
   - endstop too hard → endstop %
8. Save only when the setup is stable and safe.

## Adding a game mapping

1. Duplicate an existing profile in **Profiles**.
2. Edit metadata and add the exact executable basename, for example `myracing.exe`.
3. Ensure **Game Sync → Enable automatic profile switching** is on.
4. Start the game and check **Game Sync**.

Alternatively edit a profile JSON and run:

```bash
pyffb profiles import my-profile.json
```

## What "all racing games" would require

A universal claim would need one or more of:

- a virtual, signed HID FFB device with per-game compatibility;
- vendor-specific wheel identity emulation;
- per-title telemetry adapters and effect synthesis for games that do not emit FFB;
- kernel drivers and platform-specific installers;
- testing every game version on every OS.

Those are outside a Python-only, clean-room manager and would create new safety, anti-cheat and
licensing risks. PyFFB instead maximizes compatibility through standard HID/PID and lets the game
and firmware own real-time force.

If a game does not support standard DirectInput FFB, no amount of profile tuning can add feedback
to it. That is a firmware/emulation/telemetry problem, not a profile problem.
