"""Base class for main navigation views."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from ..theme import COLORS


class BaseView(tk.Frame):
    page_title = "PyFFB"
    page_subtitle = ""

    def __init__(self, parent: tk.Misc, app: Any) -> None:
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        self.build()

    def build(self) -> None:
        raise NotImplementedError

    def on_show(self) -> None:
        pass

    def on_telemetry(self, telemetry) -> None:
        pass

    def on_connection_changed(self) -> None:
        pass

    def on_settings_changed(self) -> None:
        pass

    def on_profiles_changed(self) -> None:
        pass

    def on_game_changed(self, detected) -> None:
        pass
