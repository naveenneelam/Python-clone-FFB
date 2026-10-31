"""Dashboard: live wheel state, profile summary and quick controls."""

from __future__ import annotations

import tkinter as tk

from ...models import Telemetry
from ..theme import COLORS, FONTS
from ..widgets import (
    Badge,
    Card,
    MetricCard,
    ScrollableFrame,
    SliderControl,
    WheelGauge,
    make_button,
    make_label,
)
from .base import BaseView


class DashboardView(BaseView):
    page_title = "Dashboard"
    page_subtitle = "Live wheel telemetry, current profile and quick feel controls"

    def build(self) -> None:
        self._sync_guard = False
        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.root = self.scroll.inner
        self.root.grid_columnconfigure(0, weight=1)
        self._build_profile_card()
        self._build_body()
        self._build_quick_card()

    def _build_profile_card(self) -> None:
        card = Card(self.root, padx=18, pady=14, accent=COLORS["accent"])
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        content = card.content
        content.grid_columnconfigure(0, weight=1)
        left = tk.Frame(content, bg=COLORS["panel"])
        left.grid(row=0, column=0, sticky="w")
        make_label(
            left, "CURRENT PROFILE", fg=COLORS["faint"], bg=COLORS["panel"], font=FONTS["tiny"]
        ).pack(anchor="w")
        name_row = tk.Frame(left, bg=COLORS["panel"])
        name_row.pack(anchor="w", pady=(2, 0))
        self.profile_name = make_label(
            name_row, "Generic racing wheel", font=FONTS["subtitle"], bg=COLORS["panel"]
        )
        self.profile_name.pack(side="left")
        self.profile_badge = Badge(
            name_row,
            "PREVIEW",
            fg=COLORS["yellow"],
            bg="#3a3018",
        )
        self.profile_badge.pack(side="left", padx=(10, 0))
        self.profile_meta = make_label(
            left,
            "Apply a profile after connecting the wheel.",
            fg=COLORS["muted"],
            font=FONTS["small"],
            bg=COLORS["panel"],
        )
        self.profile_meta.pack(anchor="w", pady=(3, 0))

        buttons = tk.Frame(content, bg=COLORS["panel"])
        buttons.grid(row=0, column=1, sticky="e")
        self.apply_btn = make_button(
            buttons, "Apply profile", lambda: self._apply(persist=False), kind="primary"
        )
        self.apply_btn.pack(side="left", padx=(0, 7))
        self.save_btn = make_button(
            buttons, "Apply & save", lambda: self._apply(persist=True), kind="secondary"
        )
        self.save_btn.pack(side="left")

    def _build_body(self) -> None:
        body = tk.Frame(self.root, bg=COLORS["bg"])
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        gauge_card = Card(body, title="Wheel position", subtitle="Live HID axis")
        gauge_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.gauge = WheelGauge(gauge_card.content, size=322)
        self.gauge.pack(fill="both", expand=True)

        metrics = tk.Frame(body, bg=COLORS["bg"])
        metrics.grid(row=0, column=1, sticky="nsew")
        for index in range(3):
            metrics.grid_rowconfigure(index, weight=1, uniform="metric")
        for index in range(2):
            metrics.grid_columnconfigure(index, weight=1, uniform="metric")
        self.torque_metric = MetricCard(
            metrics, "Torque", "--", "game output", accent=COLORS["accent"]
        )
        self.torque_metric.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
        self.position_metric = MetricCard(
            metrics, "Position", "--", "normalised axis", accent=COLORS["blue"]
        )
        self.position_metric.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 6))
        self.speed_metric = MetricCard(
            metrics, "Wheel speed", "--", "degrees / second", accent=COLORS["purple"]
        )
        self.speed_metric.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=6)
        self.ffb_metric = MetricCard(
            metrics, "FFB state", "Offline", "firmware reports", accent=COLORS["green"]
        )
        self.ffb_metric.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=6)
        self.voltage_metric = MetricCard(
            metrics, "Supply", "--", "DC bus voltage", accent=COLORS["yellow"]
        )
        self.voltage_metric.grid(row=2, column=0, sticky="nsew", padx=(0, 6), pady=(6, 0))
        self.temp_metric = MetricCard(
            metrics, "Motor temp", "--", "driver temperature", accent=COLORS["red"]
        )
        self.temp_metric.grid(row=2, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))

    def _build_quick_card(self) -> None:
        card = Card(
            self.root,
            title="Quick feel",
            subtitle="Writes to RAM for instant testing",
        )
        card.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        content = card.content
        for index in range(4):
            content.grid_columnconfigure(index, weight=1, uniform="quick")
        self.quick_strength = SliderControl(
            content, "Strength", value=self.app.settings.power_pct, compact=True
        )
        self.quick_strength.grid(row=0, column=0, sticky="ew", padx=(0, 14))
        self.quick_idle = SliderControl(
            content, "Idle spring", value=self.app.settings.idle_spring_pct, compact=True
        )
        self.quick_idle.grid(row=0, column=1, sticky="ew", padx=(0, 14))
        self.quick_damper = SliderControl(
            content, "Global damper", value=self.app.settings.global_damper_pct, compact=True
        )
        self.quick_damper.grid(row=0, column=2, sticky="ew", padx=(0, 14))
        self.quick_endstop = SliderControl(
            content, "Endstop", value=self.app.settings.endstop_pct, compact=True
        )
        self.quick_endstop.grid(row=0, column=3, sticky="ew")
        bottom = tk.Frame(content, bg=COLORS["panel"])
        bottom.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        make_label(
            bottom,
            "Quick changes are not saved to a profile. Use Tuning for the full set, then Profiles to store one.",
            fg=COLORS["faint"],
            font=FONTS["tiny"],
            bg=COLORS["panel"],
        ).pack(side="left")
        self.quick_apply = make_button(
            bottom, "Push quick changes", self._apply_quick, kind="secondary"
        )
        self.quick_apply.pack(side="right")

    # ------------------------------------------------------------------ state
    def on_show(self) -> None:
        self._sync_profile()
        self._sync_controls()
        self.on_telemetry(self.app.telemetry)

    def on_connection_changed(self) -> None:
        self._sync_profile()
        self._sync_controls()
        if not self.app.connected:
            self.ffb_metric.set("Offline", "connect a wheel", accent=COLORS["faint"])
            self.gauge.set_state(0, 0, self.app.settings.rotation_deg, connected=False)

    def on_settings_changed(self) -> None:
        self._sync_profile()
        self._sync_controls()

    def on_game_changed(self, detected) -> None:
        self._sync_profile()

    def on_telemetry(self, telemetry: Telemetry) -> None:
        if not self.app.connected:
            self.torque_metric.set("--", "not connected", accent=COLORS["faint"])
            self.position_metric.set("--", "not connected", accent=COLORS["faint"])
            self.speed_metric.set("--", "not connected", accent=COLORS["faint"])
            self.ffb_metric.set("Offline", "connect a wheel", accent=COLORS["faint"])
            self.voltage_metric.set("--", "not connected", accent=COLORS["faint"])
            self.temp_metric.set("--", "not connected", accent=COLORS["faint"])
            self.gauge.set_state(0, 0, self.app.settings.rotation_deg, connected=False)
            return
        t = telemetry
        torque = t.torque_pct
        torque_color = COLORS["red"] if t.clipping else COLORS["accent"]
        self.torque_metric.set(
            f"{torque:+.1f}%" if torque is not None else "--",
            "CLIPPING" if t.clipping else "game output",
            accent=torque_color,
        )
        pos = t.position_deg
        pct = t.position_pct
        self.position_metric.set(
            f"{pos:+.0f}°" if pos is not None else "--",
            f"{pct:+.1f}% of axis" if pct is not None else "normalised axis",
            accent=COLORS["blue"],
        )
        speed = t.speed_dps
        self.speed_metric.set(
            f"{speed:+.0f}°/s" if speed is not None else "--",
            "degrees / second",
            accent=COLORS["purple"],
        )
        if t.ffb_active is True:
            self.ffb_metric.set("Active", "game effects enabled", accent=COLORS["green"])
        elif t.ffb_active is False:
            self.ffb_metric.set("Idle", "no game effects", accent=COLORS["yellow"])
        else:
            self.ffb_metric.set("Unknown", "no firmware status", accent=COLORS["faint"])
        voltage = t.supply_voltage
        self.voltage_metric.set(
            f"{voltage:.1f} V" if voltage is not None else "--",
            "DC bus voltage",
            accent=COLORS["yellow"],
        )
        temp = t.temperature_c
        self.temp_metric.set(
            f"{temp:.0f} °C" if temp is not None else "--",
            "driver temperature",
            accent=COLORS["red"] if temp is not None and temp > 65 else COLORS["green"],
        )
        self.gauge.set_state(
            t.position_pct,
            t.position_deg,
            self.app.settings.rotation_deg,
            connected=True,
        )

    # ------------------------------------------------------------------ action
    def _sync_profile(self) -> None:
        profile = self.app.current_profile or self.app.selected_profile
        if profile is None:
            self.profile_name.configure(text="Device settings")
            self.profile_meta.configure(text="No matching profile. Select one in Profiles.")
        else:
            self.profile_name.configure(text=profile.name)
            suffix = "applied" if self.app.current_profile else "selected"
            meta = f"{profile.game or 'Custom profile'}  ·  {suffix}"
            if not profile.builtin:
                meta += "  ·  custom"
            detected = self.app.detected_game
            if detected and detected.profile.id == profile.id:
                meta += f"  ·  running: {detected.executable}"
            self.profile_meta.configure(text=meta)
        if not self.app.connected:
            self.profile_badge.configure(text="PREVIEW", fg=COLORS["yellow"], bg="#3a3018")
        elif self.app.current_profile:
            self.profile_badge.configure(text="APPLIED", fg=COLORS["green"], bg=COLORS["green_dark"])
        else:
            self.profile_badge.configure(text="CONNECTED", fg=COLORS["blue"], bg="#172c42")

    def _sync_controls(self) -> None:
        state = "normal" if self.app.connected else "disabled"
        for button in (self.apply_btn, self.save_btn, self.quick_apply):
            button.configure(state=state)
        self._sync_guard = True
        settings = self.app.settings
        self.quick_strength.set(settings.power_pct)
        self.quick_idle.set(settings.idle_spring_pct)
        self.quick_damper.set(settings.global_damper_pct)
        self.quick_endstop.set(settings.endstop_pct)
        self._sync_guard = False

    def _apply(self, *, persist: bool) -> None:
        profile = self.app.current_profile or self.app.selected_profile
        if profile is None:
            self.app.set_status("Select a profile in the Profiles view first.", "warning")
            return
        self.app.apply_profile(profile.id, persist=persist, source="manual")

    def _apply_quick(self) -> None:
        if self._sync_guard:
            return
        settings = self.app.settings.merged(
            power_pct=self.quick_strength.get(),
            idle_spring_pct=self.quick_idle.get(),
            global_damper_pct=self.quick_damper.get(),
            endstop_pct=self.quick_endstop.get(),
        )
        self.app.apply_current_settings(settings, persist=False)
