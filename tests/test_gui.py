from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest


def _gui_available() -> bool:
    if os.environ.get("PYFFB_GUI_TEST") != "1":
        return False
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        return False
    try:
        import tkinter

        root = tkinter.Tk()
        root.destroy()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _gui_available(), reason="set PYFFB_GUI_TEST=1 to run the Tk smoke test")
def test_gui_simulator_flow():
    from pyffb.config import AppConfig, ConfigStore, ProfileLibrary
    from pyffb.gui.app import PyFFBApp

    base = Path(tempfile.mkdtemp())
    store = ConfigStore(base)
    config = AppConfig.from_dict(
        {
            **AppConfig().to_dict(),
            "backend_key": "simulator",
            "port": "simulator",
        }
    )
    app = PyFFBApp(store=store, config=config, library=ProfileLibrary())
    try:
        app.withdraw()
        app.connect_device()
        for _ in range(80):
            app.update()
            if app.connected:
                break
            app.after(25)
        assert app.connected
        app.apply_profile("acc")
        for _ in range(80):
            app.update()
            if app.current_profile_id == "acc":
                break
            app.after(25)
        assert app.current_profile_id == "acc"
        for view in ("tuning", "profiles", "games", "diagnostics", "about", "dashboard"):
            app.show_view(view)
            app.update()
    finally:
        app.on_close()
