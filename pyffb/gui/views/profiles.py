"""Profile browser, custom profile editor and import/export."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from ...models import Profile
from ..theme import COLORS, FONTS
from ..widgets import (
    Badge,
    Card,
    Divider,
    ScrollableFrame,
    make_button,
    make_label,
)
from .base import BaseView


class ProfileDialog(tk.Toplevel):
    """Small modal for creating or editing a custom profile's metadata."""

    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        *,
        name: str = "",
        game: str = "",
        exes: str = "",
        description: str = "",
        notes: str = "",
    ) -> None:
        super().__init__(parent)
        self.result: dict[str, Any] | None = None
        self.title(title)
        self.configure(bg=COLORS["panel"])
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        wrap = tk.Frame(self, bg=COLORS["panel"], padx=22, pady=18)
        wrap.pack(fill="both", expand=True)
        make_label(wrap, title, font=FONTS["subtitle"], bg=COLORS["panel"]).pack(anchor="w")
        make_label(
            wrap,
            "Custom profiles can be bound to executable names for automatic switching.",
            fg=COLORS["muted"],
            bg=COLORS["panel"],
            font=FONTS["small"],
        ).pack(anchor="w", pady=(2, 14))

        self.name_var = tk.StringVar(value=name)
        self.game_var = tk.StringVar(value=game)
        self.exe_var = tk.StringVar(value=exes)
        self.desc_var = tk.StringVar(value=description)
        self._field(wrap, "Name", self.name_var)
        self._field(wrap, "Game", self.game_var)
        self._field(wrap, "Executables (comma-separated)", self.exe_var)
        self._field(wrap, "Description", self.desc_var)
        make_label(
            wrap, "Notes (one per line)", fg=COLORS["muted"], bg=COLORS["panel"], font=FONTS["small"]
        ).pack(anchor="w", pady=(8, 3))
        self.notes_text = tk.Text(
            wrap,
            height=4,
            width=54,
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            bd=0,
            font=FONTS["body"],
            padx=8,
            pady=6,
            wrap="word",
        )
        self.notes_text.pack(fill="x")
        self.notes_text.insert("1.0", notes)
        buttons = tk.Frame(wrap, bg=COLORS["panel"])
        buttons.pack(fill="x", pady=(16, 0))
        make_button(buttons, "Cancel", self._cancel, kind="ghost").pack(side="right")
        make_button(buttons, "Save", self._save, kind="primary").pack(side="right", padx=(0, 8))
        self.name_var.set(name)
        self.bind("<Escape>", lambda _event: self._cancel())
        self.bind("<Return>", lambda _event: self._save())
        self.update_idletasks()
        self._center(parent)
        self.grab_set()
        self.wait_window(self)

    def _field(self, parent: tk.Misc, label: str, variable: tk.StringVar) -> None:
        make_label(parent, label, fg=COLORS["muted"], bg=COLORS["panel"], font=FONTS["small"]).pack(
            anchor="w", pady=(8, 3)
        )
        entry = ttk.Entry(parent, textvariable=variable, width=56)
        entry.pack(fill="x")

    def _center(self, parent: tk.Misc) -> None:
        try:
            px = parent.winfo_rootx() + parent.winfo_width() // 2
            py = parent.winfo_rooty() + parent.winfo_height() // 2
            width = self.winfo_width()
            height = self.winfo_height()
            self.geometry(f"+{max(0, px - width // 2)}+{max(0, py - height // 2)}")
        except tk.TclError:
            pass

    def _save(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Name required", "Give the profile a name.", parent=self)
            return
        self.result = {
            "name": name,
            "game": self.game_var.get().strip(),
            "exe_names": tuple(
                part.strip() for part in self.exe_var.get().split(",") if part.strip()
            ),
            "description": self.desc_var.get().strip(),
            "notes": tuple(
                line.strip() for line in self.notes_text.get("1.0", "end").splitlines() if line.strip()
            ),
        }
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class ProfilesView(BaseView):
    page_title = "Profiles"
    page_subtitle = "Game presets, custom setups and automatic process mappings"

    def build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._selected_id: str | None = None
        self._build_toolbar()
        self._build_split()
        self.refresh()

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self, bg=COLORS["bg"])
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        left = tk.Frame(bar, bg=COLORS["bg"])
        left.pack(side="left")
        make_label(bar, "Search", fg=COLORS["muted"], bg=COLORS["bg"], font=FONTS["small"]).pack(
            side="left", padx=(0, 6)
        )
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_args: self.refresh())
        search = ttk.Entry(bar, textvariable=self.search_var, width=26)
        search.pack(side="left")
        right = tk.Frame(bar, bg=COLORS["bg"])
        right.pack(side="right")
        make_button(right, "Import…", self._import, kind="ghost").pack(side="left", padx=(0, 6))
        make_button(
            right, "Create from current…", self._create_from_current, kind="primary"
        ).pack(side="left")

    def _build_split(self) -> None:
        split = tk.Frame(self, bg=COLORS["bg"])
        split.grid(row=1, column=0, sticky="nsew")
        split.grid_rowconfigure(0, weight=1)
        split.grid_columnconfigure(0, weight=0)
        split.grid_columnconfigure(1, weight=1)

        left_card = Card(split, title="Library", subtitle="Built-in and custom", padx=12, pady=12)
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left_card.configure(width=390)
        left_card.grid_propagate(False)
        self.count_label = make_label(
            left_card.content,
            "",
            fg=COLORS["faint"],
            bg=COLORS["panel"],
            font=FONTS["tiny"],
        )
        self.count_label.pack(anchor="w", pady=(0, 6))
        tree_wrap = tk.Frame(left_card.content, bg=COLORS["panel"])
        tree_wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            tree_wrap,
            columns=("name", "game"),
            show="headings",
            selectmode="browse",
            height=22,
        )
        self.tree.heading("name", text="PROFILE")
        self.tree.heading("game", text="GAME")
        self.tree.column("name", width=170, minwidth=120, stretch=True)
        self.tree.column("game", width=180, minwidth=120, stretch=True)
        scrollbar = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.tag_configure("custom", foreground=COLORS["green"])
        self.tree.tag_configure("builtin", foreground=COLORS["text"])

        detail_card = Card(split, padx=0, pady=0)
        detail_card.grid(row=0, column=1, sticky="nsew")
        self.detail_scroll = ScrollableFrame(detail_card.content, bg=COLORS["panel"])
        self.detail_scroll.pack(fill="both", expand=True)
        self.detail = self.detail_scroll.inner

    def refresh(self) -> None:
        query = self.search_var.get().strip().lower() if hasattr(self, "search_var") else ""
        selected = self._selected_id
        profiles = [
            profile
            for profile in self.app.library.all()
            if not query
            or query in profile.id.lower()
            or query in profile.name.lower()
            or query in profile.game.lower()
            or any(query in exe.lower() for exe in profile.exe_names)
        ]
        for item in self.tree.get_children():
            self.tree.delete(item)
        for profile in profiles:
            self.tree.insert(
                "",
                "end",
                iid=profile.id,
                values=(profile.name, profile.game or "—"),
                tags=("custom" if not profile.builtin else "builtin",),
            )
        self.count_label.configure(
            text=f"{len(profiles)} shown · {len(self.app.library.custom())} custom"
        )
        if selected and self.tree.exists(selected):
            self.tree.selection_set(selected)
            self.tree.see(selected)
        elif profiles:
            self._selected_id = profiles[0].id
            self.tree.selection_set(profiles[0].id)
            self.tree.see(profiles[0].id)
            self._render_detail(profiles[0])
        else:
            self._selected_id = None
            self._render_empty()

    def _selected_profile(self) -> Profile | None:
        if not self._selected_id:
            return None
        try:
            return self.app.library.get(self._selected_id)
        except KeyError:
            return None

    def _on_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        self._selected_id = selection[0]
        profile = self._selected_profile()
        if profile:
            self._render_detail(profile)

    def _clear_detail(self) -> None:
        for child in self.detail.winfo_children():
            child.destroy()

    def _render_empty(self) -> None:
        self._clear_detail()
        make_label(
            self.detail,
            "No profiles match the search.",
            fg=COLORS["muted"],
            bg=COLORS["panel"],
            font=FONTS["body"],
        ).pack(anchor="w", padx=24, pady=24)

    def _render_detail(self, profile: Profile) -> None:
        self._clear_detail()
        wrap = tk.Frame(self.detail, bg=COLORS["panel"], padx=24, pady=20)
        wrap.pack(fill="both", expand=True)
        header = tk.Frame(wrap, bg=COLORS["panel"])
        header.pack(fill="x")
        title = make_label(
            header, profile.name, font=FONTS["title"], bg=COLORS["panel"]
        )
        title.pack(side="left")
        is_current = self.app.current_profile_id == profile.id
        Badge(
            header,
            "APPLIED" if is_current else ("CUSTOM" if not profile.builtin else "BUILT-IN"),
            fg=COLORS["green"] if is_current else (COLORS["blue"] if not profile.builtin else COLORS["muted"]),
            bg=COLORS["green_dark"] if is_current else ("#172c42" if not profile.builtin else COLORS["panel_alt"]),
        ).pack(side="left", padx=(10, 0))
        if self.app.config.desktop_profile_id == profile.id:
            Badge(
                header,
                "DESKTOP",
                fg=COLORS["yellow"],
                bg="#3a3018",
            ).pack(side="left", padx=(6, 0))
        make_label(
            wrap,
            profile.game or "No game mapping",
            fg=COLORS["accent"],
            bg=COLORS["panel"],
            font=FONTS["small"],
        ).pack(anchor="w", pady=(4, 0))
        if profile.description:
            make_label(
                wrap,
                profile.description,
                fg=COLORS["muted"],
                bg=COLORS["panel"],
                font=FONTS["body"],
                wraplength=570,
            ).pack(anchor="w", pady=(10, 0))
        if profile.exe_names:
            make_label(
                wrap,
                "Executables: " + ", ".join(profile.exe_names),
                fg=COLORS["faint"],
                bg=COLORS["panel"],
                font=FONTS["mono_small"],
                wraplength=570,
            ).pack(anchor="w", pady=(8, 0))
        Divider(wrap, bg=COLORS["border"]).pack(fill="x", pady=14)

        make_label(
            wrap, "SETTINGS", fg=COLORS["faint"], bg=COLORS["panel"], font=FONTS["tiny"]
        ).pack(anchor="w")
        summary = tk.Frame(wrap, bg=COLORS["panel"])
        summary.pack(fill="x", pady=(7, 0))
        summary.grid_columnconfigure(0, weight=1, uniform="sum")
        summary.grid_columnconfigure(1, weight=1, uniform="sum")
        items = [
            ("Strength", f"{profile.settings.power_pct}%"),
            ("Wheel range", f"{profile.settings.rotation_deg}°"),
            ("Endstop", f"{profile.settings.endstop_pct}%"),
            ("Idle spring", f"{profile.settings.idle_spring_pct}%"),
            ("Global damper", f"{profile.settings.global_damper_pct}%"),
            ("Global friction", f"{profile.settings.global_friction_pct}%"),
            ("Effect ratio", f"{profile.settings.game_effect_ratio_pct}%"),
            ("Speed limit", f"{profile.settings.max_speed_dps}°/s"),
            ("Spring gain", f"{profile.settings.spring_gain_pct}%"),
            ("Damper gain", f"{profile.settings.damper_gain_pct}%"),
            ("Friction gain", f"{profile.settings.friction_gain_pct}%"),
            ("Inertia gain", f"{profile.settings.inertia_gain_pct}%"),
        ]
        for index, (label, value) in enumerate(items):
            row = tk.Frame(summary, bg=COLORS["panel"])
            row.grid(row=index // 2, column=index % 2, sticky="ew", pady=2)
            make_label(
                row,
                label,
                fg=COLORS["muted"],
                bg=COLORS["panel"],
                font=FONTS["small"],
            ).pack(side="left")
            make_label(
                row,
                value,
                fg=COLORS["text"],
                bg=COLORS["panel"],
                font=FONTS["small"],
            ).pack(side="right", padx=(0, 16))

        if profile.notes:
            Divider(wrap, bg=COLORS["border"]).pack(fill="x", pady=14)
            make_label(
                wrap, "NOTES", fg=COLORS["faint"], bg=COLORS["panel"], font=FONTS["tiny"]
            ).pack(anchor="w")
            for note in profile.notes:
                make_label(
                    wrap,
                    "• " + note,
                    fg=COLORS["muted"],
                    bg=COLORS["panel"],
                    font=FONTS["small"],
                    wraplength=570,
                ).pack(anchor="w", pady=(3, 0))

        Divider(wrap, bg=COLORS["border"]).pack(fill="x", pady=14)
        buttons = tk.Frame(wrap, bg=COLORS["panel"])
        buttons.pack(fill="x")
        state = "normal" if self.app.connected else "disabled"
        apply_btn = make_button(
            buttons,
            "Apply",
            lambda: self.app.apply_profile(profile.id, persist=False, source="manual"),
            kind="primary",
        )
        apply_btn.configure(state=state)
        apply_btn.pack(side="left", padx=(0, 7))
        save_btn = make_button(
            buttons,
            "Apply & save",
            lambda: self.app.apply_profile(profile.id, persist=True, source="manual"),
            kind="secondary",
        )
        save_btn.configure(state=state)
        save_btn.pack(side="left", padx=(0, 7))
        make_button(
            buttons, "Duplicate…", lambda: self._duplicate(profile), kind="ghost"
        ).pack(side="left", padx=(0, 7))
        make_button(
            buttons,
            "Set desktop",
            lambda: self.app.set_desktop_profile(profile.id),
            kind="ghost",
        ).pack(side="left", padx=(0, 7))
        make_button(buttons, "Export…", lambda: self._export(profile), kind="ghost").pack(
            side="left"
        )
        if not profile.builtin:
            second = tk.Frame(wrap, bg=COLORS["panel"])
            second.pack(fill="x", pady=(8, 0))
            make_button(
                second,
                "Update with current tuning",
                lambda: self._update_settings(profile),
                kind="secondary",
            ).pack(side="left", padx=(0, 7))
            make_button(
                second, "Edit metadata…", lambda: self._edit(profile), kind="ghost"
            ).pack(side="left", padx=(0, 7))
            make_button(
                second, "Delete", lambda: self._delete(profile), kind="danger"
            ).pack(side="left")

    def _create_from_current(self) -> None:
        dialog = ProfileDialog(
            self,
            "Create custom profile",
            name="My wheel setup",
            description="Created from the current live tuning.",
            notes="Tune this profile against the target car and track.",
        )
        if not dialog.result:
            return
        try:
            profile = self.app.create_custom_profile(
                dialog.result["name"],
                self.app.settings,
                game=dialog.result["game"],
                exe_names=dialog.result["exe_names"],
                description=dialog.result["description"],
                notes=dialog.result["notes"],
            )
        except Exception as exc:
            messagebox.showerror("Could not create profile", str(exc), parent=self)
            return
        self._selected_id = profile.id
        self.refresh()
        self.app.set_status(f"Created custom profile {profile.name}.", "success")

    def _duplicate(self, profile: Profile) -> None:
        name = simpledialog.askstring(
            "Duplicate profile",
            "Name for the new custom profile:",
            initialvalue=f"{profile.name} (custom)",
            parent=self,
        )
        if not name:
            return
        try:
            new_profile = self.app.create_custom_profile(
                name,
                profile.settings,
                game=profile.game,
                exe_names=profile.exe_names,
                description=profile.description,
                notes=profile.notes,
            )
        except Exception as exc:
            messagebox.showerror("Could not duplicate profile", str(exc), parent=self)
            return
        self._selected_id = new_profile.id
        self.refresh()
        self.app.set_status(f"Duplicated profile as {new_profile.name}.", "success")

    def _update_settings(self, profile: Profile) -> None:
        if profile.builtin:
            return
        if not messagebox.askyesno(
            "Update custom profile",
            f"Replace the stored settings of '{profile.name}' with the current live tuning?",
            parent=self,
        ):
            return
        try:
            updated = profile.with_settings(self.app.settings)
            self.app.update_custom_profile(updated)
        except Exception as exc:
            messagebox.showerror("Could not update profile", str(exc), parent=self)
            return
        self.refresh()
        self.app.set_status(f"Updated {profile.name}.", "success")

    def _edit(self, profile: Profile) -> None:
        if profile.builtin:
            return
        dialog = ProfileDialog(
            self,
            "Edit profile metadata",
            name=profile.name,
            game=profile.game,
            exes=", ".join(profile.exe_names),
            description=profile.description,
            notes="\n".join(profile.notes),
        )
        if not dialog.result:
            return
        try:
            updated = Profile(
                id=profile.id,
                name=dialog.result["name"],
                game=dialog.result["game"],
                exe_names=dialog.result["exe_names"],
                description=dialog.result["description"],
                notes=dialog.result["notes"],
                settings=profile.settings,
                builtin=False,
            )
            self.app.update_custom_profile(updated)
        except Exception as exc:
            messagebox.showerror("Could not update profile", str(exc), parent=self)
            return
        self.refresh()
        self.app.set_status("Profile metadata updated.", "success")

    def _delete(self, profile: Profile) -> None:
        if profile.builtin:
            return
        if not messagebox.askyesno(
            "Delete custom profile",
            f"Permanently delete '{profile.name}' from the local library?",
            parent=self,
        ):
            return
        try:
            self.app.delete_custom_profile(profile.id)
        except Exception as exc:
            messagebox.showerror("Could not delete profile", str(exc), parent=self)
            return
        self._selected_id = None
        self.refresh()
        self.app.set_status(f"Deleted {profile.name}.", "info")

    def _export(self, profile: Profile) -> None:
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export profile",
            defaultextension=".json",
            initialfile=f"{profile.id}.json",
            filetypes=[("JSON profile", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.app.export_profile_file(profile.id, Path(path))
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
            return
        self.app.set_status(f"Exported profile to {path}.", "success")

    def _import(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Import profile",
            filetypes=[("JSON profile", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            profile = self.app.import_profile_file(Path(path))
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc), parent=self)
            return
        self._selected_id = profile.id
        self.refresh()
        self.app.set_status(f"Imported {profile.name}.", "success")

    def on_show(self) -> None:
        self.refresh()

    def on_connection_changed(self) -> None:
        profile = self._selected_profile()
        if profile:
            self._render_detail(profile)

    def on_settings_changed(self) -> None:
        profile = self._selected_profile()
        if profile:
            self._render_detail(profile)

    def on_profiles_changed(self) -> None:
        self.refresh()
