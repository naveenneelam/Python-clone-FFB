# Contributing

PyFFB Studio is a safety-adjacent desktop application. Contributions are welcome when they keep
the force path, licensing and failure behavior honest.

## Ground rules

- **No proprietary reverse engineering.** Do not submit decompiled code, extracted private
  protocols, license bypasses or copied vendor assets. EMC support requires vendor documentation
  and permission.
- **No unsafe motor writes.** The canonical model intentionally excludes current limits, encoder
  alignment, driver/PID, voltage/regeneration and brake-resistor settings. Do not route them
  through a "convenience" backend method.
- **No game injection.** PyFFB uses standard HID; hooks, memory reads and anti-cheat changes are
  out of scope.
- **Safety first.** A new profile, backend or UI path that can increase torque needs a documented
  validation and rollback story.
- Be civil and specific in reviews.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check pyffb tests
```

Run the GUI against the simulator:

```bash
python -m pyffb gui --simulate
```

Optional GUI test:

```bash
PYFFB_GUI_TEST=1 python -m pytest tests/test_gui.py -q
```

## Code style

- Python 3.10+, type hints for public APIs.
- Standard library first; Tkinter for UI; pyserial for hardware.
- Keep backend I/O synchronous and serialized; don't block the Tk main thread with device calls.
- Validate at the model boundary and again at the adapter boundary.
- Prefer explicit errors over silent fallback for writes.
- Use `ApplyReport` for apply results; don't raise from GUI callbacks.
- Update docs and tests with behavior changes.

## Adding a firmware backend

1. Implement `WheelBackend` in `pyffb/backends/`.
2. Register it in `BACKENDS`.
3. Add a fake transport test.
4. Document exact command semantics, firmware versions and safety exclusions.
5. Do not add hardware configuration features without a separate safety review.

## Adding or changing a game profile

- Use a stable lowercase ID and exact executable basenames.
- Keep stock effects conservative; remember OpenFFBoard gains are multipliers.
- Include in-game setup notes and a range recommendation.
- Do not claim hardware testing you did not perform.
- Add/adjust the profile test if required.
- Profile submissions without a rationale for unusual values may be asked to justify them.

## Documentation

- Update the relevant file under `docs/`.
- Keep examples runnable.
- State limitations and failure modes explicitly.
- Avoid promising universal game compatibility.
- Keep safety language strong and unambiguous.

## Pull requests

A useful PR includes:

- problem and scope;
- safety impact;
- test evidence (`pytest`, optional hardware checks);
- docs changes;
- screenshots/GIFs for visible UI changes.

For hardware-affecting changes, state the exact board/firmware/motor/PSU and torque/current limits
used. Never test high torque without a hardware E-stop.

## Commit messages

Short imperative summaries are preferred, for example:

```text
Add open firmware backend probe timeout
Fix rollback after flash-save failure
Document ACC low-torque setup
```

## License

By contributing, you agree that your contribution is licensed under the MIT License of this
repository and that you have the right to submit it.
