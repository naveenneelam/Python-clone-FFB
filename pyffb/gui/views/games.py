"""Game Sync: process detection, automatic switching and executable mappings."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..theme import COLORS, FONTS
from ..widgets import Badge, Card, make_button, make_label
from .base import BaseView


class GamesView(BaseView):
    page_title = "Game Sync"
    page_subtitle = "Switch profiles automatically when a racing title starts or exits"

    def build(self) -> None:
        self._loading = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build_options()
        self._build_detection()
        self._build_mapping()
        self._sync()

    def _build_options(self) -> None:
        card = Card(self, title="Automation", subtitle="All changes are stored locally")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        content = card.content
        self.auto_var = tk.BooleanVar(value=self.app.config.auto_switch_games)
        self.geometry_var = tk.BooleanVar(value=self.app.config.auto_apply_geometry)
        self.persist_var = tk.BooleanVar(value=self.app.config.auto_persist)
        row = tk.Frame(content, bg=COLORS["panel"])
        row.pack(fill="x")
        self._check(
            row,
            "Enable automatic profile switching",
            self.auto_var,
            self._toggle_auto,
        )
        self._check(
            row,
            "Also apply wheel range / invert",
            self.geometry_var,
            self._toggle_geometry,
        )
        self._check(
            row,
            "Persist auto changes to flash",
            self.persist_var,
            self._toggle_persist,
        )
        make_label(
            content,
            "Auto-switching applies the tuned FFB values only unless geometry is enabled. "
            "Flash persistence is off by default to avoid unnecessary EEPROM wear.",
            fg=COLORS["faint"],
            bg=COLORS["panel"],
            font=FONTS["tiny"],
            wraplength=900,
        ).pack(anchor="w", pady=(9, 0))

    def _check(self, parent: tk.Misc, text: str, variable: tk.BooleanVar, command) -> None:
        tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            command=command,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            activebackground=COLORS["panel"],
            activeforeground=COLORS["text"],
            selectcolor=COLORS["panel_alt"],
            font=FONTS["small"],
            bd=0,
            highlightthickness=0,
        ).pack(side="left", padx=(0, 24))

    def _build_detection(self) -> None:
        card = Card(self, title="Detected game", subtitle="Checked every two seconds", accent=COLORS["green"])
        card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        content = card.content
        left = tk.Frame(content, bg=COLORS["panel"])
        left.pack(side="left", fill="x", expand=True)
        title_row = tk.Frame(left, bg=COLORS["panel"])
        title_row.pack(anchor="w")
        self.detected_title = make_label(
            title_row, "No racing game detected", font=FONTS["subtitle"], bg=COLORS["panel"]
        )
        self.detected_title.pack(side="left")
        self.detected_badge = Badge(
            title_row, "MONITORING", fg=COLORS["muted"], bg=COLORS["panel_alt"]
        )
        self.detected_badge.pack(side="left", padx=(10, 0))
        self.detected_detail = make_label(
            left,
            "Start a supported game, or use Scan now. Profiles can still be applied manually.",
            fg=COLORS["muted"],
            bg=COLORS["panel"],
            font=FONTS["small"],
        )
        self.detected_detail.pack(anchor="w", pady=(3, 0))
        right = tk.Frame(content, bg=COLORS["panel"])
        right.pack(side="right")
        make_button(right, "Scan now", self.app.check_games_now, kind="secondary").pack(
            side="left", padx=(0, 7)
        )
        make_button(
            right,
            "Compatibility guide",
            lambda: self.app.open_docs("GAMES.md"),
            kind="ghost",
        ).pack(side="left")

    def _build_mapping(self) -> None:
        card = Card(self, title="Executable mappings", subtitle="Custom profiles take priority")
        card.grid(row=2, column=0, sticky="nsew")
        content = card.content
        make_label(
            content,
            "Exact executable basenames are used. Edit a custom profile's metadata to add or change mappings.",
            fg=COLORS["faint"],
            bg=COLORS["panel"],
            font=FONTS["tiny"],
        ).pack(side="bottom", anchor="w", pady=(8, 0))
        tree_wrap = tk.Frame(content, bg=COLORS["panel"])
        tree_wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            tree_wrap,
            columns=("profile", "game", "executables"),
            show="headings",
            selectmode="browse",
        )
        headings = {
            "profile": ("PROFILE", 220, 150),
            "game": ("GAME", 250, 150),
            "executables": ("EXECUTABLES", 330, 200),
        }
        for key, (text, width, minimum) in headings.items():
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, minwidth=minimum, stretch=key != "profile")
        scroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.tag_configure("custom", foreground=COLORS["green"])
        self.tree.tag_configure("unmapped", foreground=COLORS["faint"])

    def _sync(self) -> None:
        self._loading = True
        try:
            self.auto_var.set(self.app.config.auto_switch_games)
            self.geometry_var.set(self.app.config.auto_apply_geometry)
            self.persist_var.set(self.app.config.auto_persist)
        finally:
            self._loading = False
        self._refresh_table()
        self.on_game_changed(self.app.detected_game)

    def _refresh_table(self) -> None:
        selected = self.tree.selection()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for profile in self.app.library.all():
            exes = ", ".join(profile.exe_names) or "unmapped"
            self.tree.insert(
                "",
                "end",
                iid=profile.id,
                values=(
                    profile.name,
                    profile.game or "Any game",
                    exes,
                ),
                tags=(
                    "unmapped"
                    if not profile.exe_names
                    else ("custom" if not profile.builtin else ""),
                ),
            )
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected[0])

    def _toggle_auto(self) -> None:
        if self._loading:
            return
        self.app.set_auto_switch(self.auto_var.get())
        self._sync()

    def _toggle_geometry(self) -> None:
        if self._loading:
            return
        self.app.set_auto_geometry(self.geometry_var.get())
        self._sync()

    def _toggle_persist(self) -> None:
        if self._loading:
            return
        self.app.set_auto_persist(self.persist_var.get())
        self._sync()

    def on_game_changed(self, detected) -> None:
        if not hasattr(self, "detected_title"):
            return
        if detected:
            self.detected_title.configure(text=detected.profile.name)
            game = detected.profile.game or "Recognised executable"
            self.detected_detail.configure(
                text=f"{game}  ·  {detected.executable}  ·  profile {detected.profile.id}"
            )
            if self.app.config.auto_switch_games:
                self.detected_badge.configure(
                    text="AUTO", fg=COLORS["green"], bg=COLORS["green_dark"]
                )
            else:
                self.detected_badge.configure(
                    text="DETECTED", fg=COLORS["yellow"], bg="#3a3018"
                )
        else:
            self.detected_title.configure(text="No racing game detected")
            change = self.app.last_game_change
            detail = "Start a supported game, or use Scan now."
            if change and change.reason == "game_exited":
                detail = "The last game exited; the desktop profile is the auto-switch target."
            elif not self.app.config.auto_switch_games:
                detail = "Automatic switching is disabled. Apply profiles manually or enable automation."
            self.detected_detail.configure(text=detail)
            self.detected_badge.configure(
                text="OFF" if not self.app.config.auto_switch_games else "MONITORING",
                fg=COLORS["faint"] if not self.app.config.auto_switch_games else COLORS["muted"],
                bg=COLORS["panel_alt"],
            )

    def on_show(self) -> None:
        self._sync()

    def on_profiles_changed(self) -> None:
        self._sync()

    def on_connection_changed(self) -> None:
        self.on_game_changed(self.app.detected_game)
