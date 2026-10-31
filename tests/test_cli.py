from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, config_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, "-m", "pyffb", "--config-dir", str(config_dir), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_version():
    result = subprocess.run(
        [sys.executable, "-m", "pyffb", "--version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_profiles_json(tmp_path: Path):
    result = run_cli("profiles", "list", "--json", config_dir=tmp_path)
    assert result.returncode == 0, result.stderr
    profiles = json.loads(result.stdout)
    assert len(profiles) >= 20
    assert any(item["id"] == "acc" for item in profiles)


def test_apply_simulator_dry_run(tmp_path: Path):
    result = run_cli(
        "apply",
        "--backend",
        "simulator",
        "--profile",
        "acc",
        "--dry-run",
        config_dir=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert "Dry run" in result.stdout
    assert "Strength" in result.stdout


def test_info_simulator_json(tmp_path: Path):
    result = run_cli("info", "--backend", "simulator", "--json", config_dir=tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["device"]["backend"] == "simulator"
    assert payload["settings"]["power_pct"] >= 0
    assert "telemetry" in payload


def test_simulate_output(tmp_path: Path):
    result = run_cli("simulate", "--seconds", "0.15", "--interval", "0.1", config_dir=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "torque=" in result.stdout
