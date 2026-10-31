"""About, scope and safety notes."""

from __future__ import annotations

import tkinter as tk

from ... import __version__
from ..theme import COLORS, FONTS
from ..widgets import Card, ScrollableFrame, make_button, make_label
from .base import BaseView


class AboutView(BaseView):
    page_title = "About"
    page_subtitle = "Scope, safety and project provenance"

    def build(self) -> None:
        scroll = ScrollableFrame(self)
        scroll.pack(fill="both", expand=True)
        inner = scroll.inner
        inner.grid_columnconfigure(0, weight=1)

        hero = Card(inner, padx=24, pady=20, accent=COLORS["accent"])
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        make_label(
            hero.content,
            "PyFFB Studio",
            font=FONTS["display"],
            bg=COLORS["panel"],
        ).pack(anchor="w")
        make_label(
            hero.content,
            f"Version {__version__}  ·  clean-room Python force-feedback manager",
            fg=COLORS["accent"],
            bg=COLORS["panel"],
            font=FONTS["body_bold"],
        ).pack(anchor="w", pady=(2, 10))
        make_label(
            hero.content,
            "This application configures and monitors an open HID force-feedback wheel. "
            "Games talk directly to the wheel firmware over USB HID; Python is not in the "
            "real-time FFB loop. That separation is what keeps force delivery deterministic "
            "and avoids adding a kernel driver just to turn a wheel.",
            fg=COLORS["muted"],
            bg=COLORS["panel"],
            font=FONTS["body"],
            wraplength=850,
        ).pack(anchor="w")

        card = Card(inner, title="Scope and compatibility")
        card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        points = [
            "Any racing game that supports a standard DirectInput force-feedback wheel can drive the firmware directly.",
            "PyFFB adds conservative profiles, one-click tuning, game detection, executable mappings and diagnostics.",
            "Games that only accept a short list of commercial wheels, or console-only titles, are outside the guarantee. No compatibility claim can cover every title and every firmware version.",
            "The app never hooks game processes, injects code, bypasses anti-cheat or emulates a commercial wheel.",
        ]
        for point in points:
            make_label(
                card.content,
                "• " + point,
                fg=COLORS["muted"],
                bg=COLORS["panel"],
                font=FONTS["small"],
                wraplength=850,
            ).pack(anchor="w", pady=3)

        card = Card(inner, title="Clean-room and licenses")
        card.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        make_label(
            card.content,
            "PyFFB was built from public interoperability information: the USB HID PID "
            "specification and OpenFFBoard's MIT-licensed command documentation. It contains "
            "no EMC firmware, decompiled code, private protocol or license bypass. EMC is a "
            "third-party product name used only for identification; this project is not "
            "affiliated with or endorsed by its author.",
            fg=COLORS["muted"],
            bg=COLORS["panel"],
            font=FONTS["small"],
            wraplength=850,
        ).pack(anchor="w")
        make_label(
            card.content,
            "PyFFB: MIT. OpenFFBoard: MIT (separate project). Python, Tkinter and pyserial "
            "are used under their respective licenses.",
            fg=COLORS["faint"],
            bg=COLORS["panel"],
            font=FONTS["tiny"],
            wraplength=850,
        ).pack(anchor="w", pady=(8, 0))

        safety = Card(inner, title="Safety", accent=COLORS["red"])
        safety.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        make_label(
            safety.content,
            "A high-torque direct-drive wheel can injure hands, entangle clothing or damage "
            "hardware. Fit a physical emergency stop / power switch that does not depend on "
            "this program, confirm the firmware current limit before driving, and never "
            "configure motor parameters while the wheel is enabled.",
            fg=COLORS["muted"],
            bg=COLORS["panel"],
            font=FONTS["small"],
            wraplength=850,
        ).pack(anchor="w")

        links = tk.Frame(inner, bg=COLORS["bg"])
        links.grid(row=4, column=0, sticky="w", pady=(0, 20))
        for label, doc in (
            ("User guide", "USER_GUIDE.md"),
            ("Game setup", "GAMES.md"),
            ("Hardware", "HARDWARE.md"),
            ("Safety", "SAFETY.md"),
            ("Clean-room notes", "CLEAN_ROOM.md"),
        ):
            make_button(
                links, label, lambda name=doc: self.app.open_docs(name), kind="ghost"
            ).pack(side="left", padx=(0, 6))
        make_button(links, "Open config folder", self.app.open_config_dir, kind="secondary").pack(
            side="left"
        )
