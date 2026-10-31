from __future__ import annotations

from pyffb.config import ProfileLibrary
from pyffb.gamewatch import GameSession, executable_basename, find_running_game
from pyffb.models import WheelSettings


def test_executable_basename():
    assert executable_basename(r"C:\Games\ACC\AC2-Win64-Shipping.exe") == "ac2-win64-shipping.exe"
    assert executable_basename('"dirtrally2.exe"') == "dirtrally2.exe"


def test_find_running_game_case_insensitive():
    library = ProfileLibrary()
    detected = find_running_game(library, ["chrome.exe", "AC2-WIN64-SHIPPING.EXE"])
    assert detected is not None
    assert detected.profile.id == "acc"
    assert detected.executable == "ac2-win64-shipping.exe"


def test_unknown_process():
    library = ProfileLibrary()
    assert find_running_game(library, ["explorer.exe", "notepad.exe"]) is None


def test_session_start_switch_exit():
    library = ProfileLibrary()
    session = GameSession(library, desktop_profile_id="desktop")
    change = session.update(["AC2-Win64-Shipping.exe"])
    assert change is not None
    assert change.profile_id == "acc"
    assert change.reason == "game_started"
    assert session.update(["AC2-Win64-Shipping.exe"]) is None
    change = session.update(["acs.exe"])
    assert change is not None
    assert change.profile_id == "assetto-corsa"
    assert change.reason == "game_switched"
    change = session.update([])
    assert change is not None
    assert change.profile_id == "desktop"
    assert change.reason == "game_exited"
    assert session.update([]) is None


def test_custom_profile_has_priority():
    library = ProfileLibrary()
    custom = library.make_custom(
        "Custom ACC",
        WheelSettings(power_pct=40),
        game="Assetto Corsa Competizione",
        exe_names=("AC2-Win64-Shipping.exe",),
    )
    detected = find_running_game(library, ["AC2-Win64-Shipping.exe"])
    assert detected is not None
    assert detected.profile.id == custom.id
