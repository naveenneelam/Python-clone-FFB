"""Diagnostics view with device identity, raw commands and local logs."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...models import Telemetry
from ..theme import COLORS, FONTS
from ..widgets import Card, make_button, make_label
from .base import BaseView


class DiagnosticsView(BaseView):
    page_title = "Diagnostics"
    page_subtitle = "Identity, raw OpenFFBoard commands, self-test and logs"

    def build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build_info()
        self._build_command()
        self._build_log()
        self._refresh_info()

    def _build_info(self) -> None:
        row = tk.Frame(self, bg=COLORS["bg"])
        row.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)

        card = Card(row, title="Device", subtitle="Read-only")
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        grid = tk.Frame(card.content, bg=COLORS["panel"])
        grid.pack(fill="x")
        grid.grid_columnconfigure(1, weight=1)
        self.info_values: dict[str, tk.Label] = {}
        for index, (key, label) in enumerate(
            (
                ("connection", "Connection"),
                ("backend", "Backend"),
                ("port", "Port"),
                ("firmware", "Firmware"),
                ("hardware", "Hardware"),
                ("profile", "Profile"),
            )
        ):
            make_label(
                grid, label, fg=COLORS["muted"], bg=COLORS["panel"], font=FONTS["small"]
            ).grid(row=index, column=0, sticky="w", pady=2)
            value = make_label(
                grid, "—", fg=COLORS["text"], bg=COLORS["panel"], font=FONTS["small"]
            )
            value.grid(row=index, column=1, sticky="e", pady=2)
            self.info_values[key] = value

        actions = Card(row, title="Checks", subtitle="Safe, read-only operations")
        actions.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        make_label(
            actions.content,
            "Run a read-only self-test or copy a support report. No motor current or "
            "driver parameters are modified.",
            fg=COLORS["muted"],
            bg=COLORS["panel"],
            font=FONTS["small"],
            wraplength=390,
        ).pack(anchor="w")
        buttons = tk.Frame(actions.content, bg=COLORS["panel"])
        buttons.pack(fill="x", pady=(12, 0))
        self.test_btn = make_button(buttons, "Run self-test", self._self_test, kind="primary")
        self.test_btn.pack(side="left", padx=(0, 7))
        make_button(buttons, "Copy report", self._copy_report, kind="secondary").pack(
            side="left", padx=(0, 7)
        )
        make_button(buttons, "Log folder", self.app.open_log_dir, kind="ghost").pack(side="left")

    def _build_command(self) -> None:
        card = Card(self, title="Raw read-only command", subtitle="Advanced diagnostics")
        card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        row = tk.Frame(card.content, bg=COLORS["panel"])
        row.pack(fill="x")
        make_label(
            row,
            "Command",
            fg=COLORS["muted"],
            bg=COLORS["panel"],
            font=FONTS["small"],
        ).pack(side="left", padx=(0, 7))
        self.command_var = tk.StringVar(value="axis.0.power?")
        self.command_entry = ttk.Entry(row, textvariable=self.command_var)
        self.command_entry.pack(side="left", fill="x", expand=True)
        self.command_entry.bind("<Return>", lambda _event: self._send())
        make_button(row, "Send", self._send, kind="secondary").pack(side="left", padx=(7, 0))
        make_label(
            card.content,
            "Read-only. Examples: axis.0.power?  ·  main.0.ffbactive?  ·  fx.0.spring?  ·  "
            "axis.0.curpos?  (Use Tuning for writes.)",
            fg=COLORS["faint"],
            bg=COLORS["panel"],
            font=FONTS["mono_small"],
        ).pack(anchor="w", pady=(5, 7))
        self.output = tk.Text(
            card.content,
            height=6,
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            bd=0,
            font=FONTS["mono"],
            padx=8,
            pady=6,
            wrap="word",
        )
        self.output.pack(fill="x")
        self.output.configure(state="disabled")
        self._output(
            "Ready. This console is read-only; motor/encoder/current-limit writes are not "
            "offered by the GUI."
        )

    def _build_log(self) -> None:
        card = Card(self, title="Log", subtitle="Rotating local log")
        card.grid(row=2, column=0, sticky="nsew")
        wrap = tk.Frame(card.content, bg=COLORS["panel"])
        wrap.pack(fill="both", expand=True)
        self.log_text = tk.Text(
            wrap,
            bg=COLORS["panel_alt"],
            fg=COLORS["muted"],
            insertbackground=COLORS["text"],
            relief="flat",
            bd=0,
            font=FONTS["mono_small"],
            padx=8,
            pady=6,
            wrap="none",
            state="disabled",
        )
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        footer = tk.Frame(card.content, bg=COLORS["panel"])
        footer.pack(fill="x", pady=(7, 0))
        make_button(footer, "Clear log", self._clear_log, kind="ghost").pack(side="right")
        make_label(
            footer,
            "Logs are stored under the PyFFB application data directory.",
            fg=COLORS["faint"],
            bg=COLORS["panel"],
            font=FONTS["tiny"],
        ).pack(side="left")

    def _refresh_info(self) -> None:
        if not hasattr(self, "info_values"):
            return
        info = self.app.device_info
        if info and self.app.connected:
            values = {
                "connection": "Online",
                "backend": info.backend_key,
                "port": info.port,
                "firmware": info.firmware or "unknown",
                "hardware": info.hardware or "unknown",
                "profile": self.app.current_profile_id or "device state",
            }
        else:
            values = {
                "connection": "Offline",
                "backend": self.app.config.backend_key,
                "port": "—",
                "firmware": "—",
                "hardware": "—",
                "profile": self.app.selected_profile_id,
            }
        for key, value in values.items():
            self.info_values[key].configure(text=value)
        state = "normal" if self.app.connected else "disabled"
        for widget in (self.test_btn, self.command_entry):
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass

    def _output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", text.rstrip() + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def _send(self) -> None:
        command = self.command_var.get().strip()
        if not command:
            return
        self._output(f"> {command}")
        self.app.send_raw_command(command, self._command_done)

    def _command_done(self, reply) -> None:
        self._output(f"< {reply.raw}")
        if getattr(reply, "value", None) is not None:
            self._output(
                f"  path={reply.path or '?'}  value={reply.value}  status={reply.status or 'ok'}"
            )
        elif getattr(reply, "status", ""):
            self._output(f"  status={reply.status}")

    def _self_test(self) -> None:
        self.test_btn.configure(state="disabled", text="Testing…")
        self._output("Running read-only self-test…")
        self.app.run_self_test(self._self_test_done)

    def _self_test_done(self, text: str) -> None:
        if not self.app.connected:
            self.test_btn.configure(state="disabled", text="Run self-test")
        else:
            self.test_btn.configure(state="normal", text="Run self-test")
        self._output(text)
        self.app.set_status("Self-test complete.", "success" if "PASS" in text else "warning")

    def _copy_report(self) -> None:
        report = self.app.diagnostic_report()
        try:
            self.clipboard_clear()
            self.clipboard_append(report)
            self.app.set_status("Diagnostic report copied to clipboard.", "success")
        except tk.TclError as exc:
            self.app.set_status(f"Could not copy report: {exc}", "error")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def append_log(self, message: str) -> None:
        if not hasattr(self, "log_text"):
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message.rstrip() + "\n")
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 1200:
            self.log_text.delete("1.0", f"{lines - 1200}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def on_show(self) -> None:
        self._refresh_info()

    def on_connection_changed(self) -> None:
        self._refresh_info()

    def on_settings_changed(self) -> None:
        self._refresh_info()

    def on_telemetry(self, telemetry: Telemetry) -> None:
        if self.app.connected:
            self.info_values["connection"].configure(
                text="Online" if not self.app.telemetry.age_s > 2 else "Stale telemetry"
            )
