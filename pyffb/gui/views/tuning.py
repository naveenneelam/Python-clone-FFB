"""Full wheel tuning view."""

from __future__ import annotations

import tkinter as tk

from ...models import WheelSettings
from ..theme import COLORS, FONTS
from ..widgets import (
    Card,
    LabeledSpinbox,
    ScrollableFrame,
    SliderControl,
    make_button,
    make_label,
)
from .base import BaseView


class TuningView(BaseView):
    page_title = "Tuning"
    page_subtitle = "Shape force feedback, conditioning and response limits"

    def build(self) -> None:
        self._loading = False
        self.sliders: dict[str, SliderControl] = {}
        self.spins: dict[str, LabeledSpinbox] = {}
        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.inner = self.scroll.inner
        self.inner.grid_columnconfigure(0, weight=1)
        self._build_toolbar()
        self._build_core_card()
        self._build_global_card()
        self._build_gain_card()
        self._build_filter_card()
        self._build_footer()

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self.inner, bg=COLORS["bg"])
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        left = tk.Frame(bar, bg=COLORS["bg"])
        left.pack(side="left")
        self.source_label = make_label(
            left,
            "Previewing selected profile",
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            font=FONTS["small"],
        )
        self.source_label.pack(anchor="w")
        self.warning_label = make_label(
            left,
            "Writes are limited by the app safety cap; motor current limits remain in firmware.",
            fg=COLORS["faint"],
            bg=COLORS["bg"],
            font=FONTS["tiny"],
        )
        self.warning_label.pack(anchor="w", pady=(2, 0))
        right = tk.Frame(bar, bg=COLORS["bg"])
        right.pack(side="right")
        self.read_btn = make_button(right, "Read from wheel", self._read, kind="ghost")
        self.read_btn.pack(side="left", padx=(0, 6))
        self.center_btn = make_button(right, "Center axis", self._center, kind="ghost")
        self.center_btn.pack(side="left", padx=(0, 6))
        self.apply_btn = make_button(right, "Apply (RAM)", self._apply, kind="secondary")
        self.apply_btn.pack(side="left", padx=(0, 6))
        self.save_btn = make_button(right, "Apply & save", self._save, kind="primary")
        self.save_btn.pack(side="left")

    def _card(self, row: int, title: str, subtitle: str) -> tk.Frame:
        card = Card(self.inner, title=title, subtitle=subtitle)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        content = card.content
        content.grid_columnconfigure(0, weight=1, uniform="tune")
        content.grid_columnconfigure(1, weight=1, uniform="tune")
        return content

    def _slider(
        self,
        parent: tk.Frame,
        row: int,
        column: int,
        field: str,
        label: str,
        *,
        suffix: str = "%",
    ) -> SliderControl:
        control = SliderControl(parent, label, value=getattr(self.app.settings, field), suffix=suffix)
        control.grid(row=row, column=column, sticky="ew", padx=(0, 22) if column == 0 else (22, 0), pady=6)
        self.sliders[field] = control
        return control

    def _spin(
        self,
        parent: tk.Frame,
        row: int,
        column: int,
        field: str,
        label: str,
        low: int,
        high: int,
        *,
        suffix: str = "",
        increment: int = 1,
    ) -> LabeledSpinbox:
        control = LabeledSpinbox(
            parent,
            label,
            from_=low,
            to=high,
            value=getattr(self.app.settings, field),
            suffix=suffix,
            increment=increment,
        )
        control.grid(row=row, column=column, sticky="ew", padx=(0, 22) if column == 0 else (22, 0), pady=8)
        self.spins[field] = control
        return control

    def _build_core_card(self) -> None:
        content = self._card(
            1,
            "Core feel",
            "The forces that define weight, self-alignment and steering range",
        )
        self._slider(content, 0, 0, "power_pct", "Overall strength")
        self._spin(content, 0, 1, "rotation_deg", "Wheel range", 90, 2520, suffix="°", increment=10)
        self._slider(content, 1, 0, "endstop_pct", "Endstop stiffness")
        self._spin(content, 1, 1, "max_speed_dps", "Speed limit", 0, 3600, suffix="°/s", increment=10)
        self._slider(content, 2, 0, "idle_spring_pct", "Idle spring")
        self._spin(content, 2, 1, "torque_rate", "Torque slew limit", 0, 32767, suffix="counts/ms", increment=50)
        self._slider(content, 3, 0, "game_effect_ratio_pct", "Game effect ratio")
        self._spin(content, 3, 1, "expo", "Response curve", -127, 127, suffix="expo")
        self.invert_var = tk.BooleanVar(value=self.app.settings.invert)
        tk.Checkbutton(
            content,
            text="Invert steering axis",
            variable=self.invert_var,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            activebackground=COLORS["panel"],
            activeforeground=COLORS["text"],
            selectcolor=COLORS["panel_alt"],
            font=FONTS["body"],
            bd=0,
            highlightthickness=0,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _build_global_card(self) -> None:
        content = self._card(
            2,
            "Always-on conditioning",
            "Artificial friction and inertia are not game effects; use them sparingly",
        )
        self._slider(content, 0, 0, "global_damper_pct", "Global damper")
        self._slider(content, 0, 1, "global_friction_pct", "Global friction")
        self._slider(content, 1, 0, "global_inertia_pct", "Global inertia")
        self._slider(content, 1, 1, "friction_ramp_pct", "Friction ramp-up")

    def _build_gain_card(self) -> None:
        content = self._card(
            3,
            "Game effect gains",
            "Firmware multipliers for game-supplied conditional effects",
        )
        note = make_label(
            content,
            "Stock OpenFFBoard defaults are spring 25%, damper 25%, friction 100%, inertia 50%. "
            "These are scalers, not output limits.",
            fg=COLORS["faint"],
            font=FONTS["tiny"],
            bg=COLORS["panel"],
            wraplength=780,
        )
        note.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._slider(content, 1, 0, "spring_gain_pct", "Spring gain")
        self._slider(content, 1, 1, "damper_gain_pct", "Damper gain")
        self._slider(content, 2, 0, "friction_gain_pct", "Friction gain")
        self._slider(content, 2, 1, "inertia_gain_pct", "Inertia gain")

    def _build_filter_card(self) -> None:
        content = self._card(
            4,
            "Filtering",
            "Low-pass filters smooth constant force and optional conditional effects",
        )
        self._spin(
            content,
            0,
            0,
            "constant_filter_hz",
            "Constant force filter",
            1,
            500,
            suffix="Hz",
            increment=10,
        )
        self._spin(
            content,
            0,
            1,
            "constant_filter_q",
            "Constant force Q",
            1,
            127,
            suffix="x0.01",
            increment=1,
        )
        self.condition_var = tk.BooleanVar(value=self.app.settings.condition_filters_enabled)
        self.condition_check = tk.Checkbutton(
            content,
            text="Use custom filters for spring, damper, friction and inertia",
            variable=self.condition_var,
            command=self._toggle_condition_filters,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            activebackground=COLORS["panel"],
            activeforeground=COLORS["text"],
            selectcolor=COLORS["panel_alt"],
            font=FONTS["body"],
            bd=0,
            highlightthickness=0,
        )
        self.condition_check.grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 2))
        self._spin(content, 2, 0, "condition_friction_hz", "Friction filter frequency", 1, 500, suffix="Hz", increment=5)
        self._spin(content, 2, 1, "condition_friction_q", "Friction filter Q", 1, 127, suffix="x0.01")
        self._spin(content, 3, 0, "condition_damper_hz", "Damper filter frequency", 1, 500, suffix="Hz", increment=5)
        self._spin(content, 3, 1, "condition_damper_q", "Damper filter Q", 1, 127, suffix="x0.01")
        self._spin(content, 4, 0, "condition_inertia_hz", "Inertia filter frequency", 1, 500, suffix="Hz", increment=5)
        self._spin(content, 4, 1, "condition_inertia_q", "Inertia filter Q", 1, 127, suffix="x0.01")

    def _build_footer(self) -> None:
        footer = tk.Frame(self.inner, bg=COLORS["bg"])
        footer.grid(row=5, column=0, sticky="ew", pady=(0, 20))
        make_label(
            footer,
            "Tuning applies to the live wheel only. Use Profiles → Duplicate to keep a custom setup.",
            fg=COLORS["faint"],
            bg=COLORS["bg"],
            font=FONTS["tiny"],
        ).pack(anchor="w")

    def _toggle_condition_filters(self) -> None:
        state = "normal" if self.condition_var.get() else "disabled"
        for field in (
            "condition_friction_hz",
            "condition_friction_q",
            "condition_damper_hz",
            "condition_damper_q",
            "condition_inertia_hz",
            "condition_inertia_q",
        ):
            self.spins[field].spin.configure(state=state)

    def _fill(self) -> None:
        settings = self.app.settings
        self._loading = True
        try:
            for field, control in self.sliders.items():
                control.set(int(getattr(settings, field)))
            for field, control in self.spins.items():
                control.set(int(getattr(settings, field)))
            self.invert_var.set(settings.invert)
            self.condition_var.set(settings.condition_filters_enabled)
            self._toggle_condition_filters()
        finally:
            self._loading = False
        if self.app.connected:
            profile = self.app.current_profile
            self.source_label.configure(
                text=f"Editing live wheel state · {profile.name if profile else 'no matching profile'}"
            )
        else:
            profile = self.app.selected_profile
            self.source_label.configure(
                text=f"Previewing {profile.name if profile else 'settings'} · connect to write"
            )
        state = "normal" if self.app.connected else "disabled"
        for button in (self.read_btn, self.center_btn, self.apply_btn, self.save_btn):
            button.configure(state=state)

    def collect(self) -> tuple[WheelSettings, list[str]]:
        values = {field: control.get() for field, control in self.sliders.items()}
        values.update({field: control.get() for field, control in self.spins.items()})
        values["invert"] = self.invert_var.get()
        values["condition_filters_enabled"] = self.condition_var.get()
        settings = WheelSettings.from_dict({**self.app.settings.to_dict(), **values})
        return settings.validated()

    def _read(self) -> None:
        self.app.reload_settings()

    def _center(self) -> None:
        from tkinter import messagebox

        if messagebox.askyesno(
            "Center axis",
            "Hold the wheel at the desired physical centre.\n\nSet this position as 0°?",
            parent=self,
        ):
            self.app.center_axis()

    def _apply(self) -> None:
        settings, warnings = self.collect()
        if warnings:
            self.app.set_status(warnings[0], "warning")
        self.app.apply_current_settings(settings, persist=False)

    def _save(self) -> None:
        settings, warnings = self.collect()
        if warnings:
            self.app.set_status(warnings[0], "warning")
        self.app.apply_current_settings(settings, persist=True)

    def on_show(self) -> None:
        self._fill()

    def on_connection_changed(self) -> None:
        self._fill()

    def on_settings_changed(self) -> None:
        self._fill()

    def on_profiles_changed(self) -> None:
        self._fill()
