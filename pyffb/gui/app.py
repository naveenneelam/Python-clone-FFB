"""Main Tk application, asynchronous device I/O and cross-view state."""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from logging import Handler, LogRecord
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable

from .. import __version__
from ..backends import BackendError, make_backend
from ..config import AppConfig, ConfigStore, ProfileLibrary
from ..controller import SafetyPolicy, WheelController
from ..gamewatch import DetectedGame, GameSession, find_running_game, process_snapshot
from ..models import (
    ApplyReport,
    DeviceInfo,
    Profile,
    Telemetry,
    WheelSettings,
)
from .theme import COLORS, FONTS, configure_style
from .views import (
    AboutView,
    DashboardView,
    DiagnosticsView,
    GamesView,
    ProfilesView,
    TuningView,
)
from .widgets import StatusPill, make_button, make_label

log = logging.getLogger(__name__)

BACKEND_LABELS = {
    "openffboard": "OpenFFBoard (USB CDC)",
    "simulator": "Simulator (no hardware)",
}
BACKEND_KEYS = {label: key for key, label in BACKEND_LABELS.items()}
NO_PORT = "No ports"


@dataclass
class _Task:
    future: Future
    label: str
    on_success: Callable[[Any], None] | None
    on_error: Callable[[BaseException], None] | None


class GuiLogHandler(Handler):
    def __init__(self, target_queue: queue.Queue[str]) -> None:
        super().__init__(logging.INFO)
        self.target_queue = target_queue
        self.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-7s  %(name)s  %(message)s", "%H:%M:%S")
        )

    def emit(self, record: LogRecord) -> None:
        try:
            self.target_queue.put_nowait(self.format(record))
        except Exception:
            pass


class PyFFBApp(tk.Tk):
    def __init__(
        self,
        *,
        store: ConfigStore,
        config: AppConfig,
        library: ProfileLibrary,
    ) -> None:
        super().__init__()
        self.store = store
        self.config = config
        self.library = library
        self.controller: WheelController | None = None
        self.device_info: DeviceInfo | None = None
        self._connected = False
        self._connecting = False
        self._disconnecting = False
        self._closing = False
        self._estop_active = False
        self._telemetry = Telemetry()
        self._telemetry_future: Future | None = None
        self._telemetry_failures = 0
        self._user_io_active = 0
        self._tasks: list[_Task] = []
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pyffb-io")
        self._ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._log_queue: queue.Queue[str] = queue.Queue()
        self._log_buffer: list[str] = []
        self._log_handler: GuiLogHandler | None = None
        self._auto_inflight = False
        self._pending_auto_change = None
        self._detected_game: DetectedGame | None = None
        self._last_game_change = None
        self._status_job: str | None = None
        self._poll_job: str | None = None
        self._telemetry_job: str | None = None
        self._game_job: str | None = None
        self._views: dict[str, Any] = {}
        self._nav_buttons: dict[str, tuple[tk.Frame, tk.Frame, tk.Button]] = {}
        self._active_view = "dashboard"
        self._settings = self._initial_settings()
        self._current_profile_id: str | None = self.config.last_profile_id
        self._session = GameSession(
            self.library,
            self.config.desktop_profile_id,
        )

        self.title(f"PyFFB Studio {__version__}")
        self.configure(bg=COLORS["bg"])
        self.geometry(self.config.window_geometry)
        self.minsize(1100, 690)
        configure_style(self)
        self._build_ui()
        self._install_log_handler()
        self.after(10, self._fit_window)
        self.after(30, self._startup)

    # ----------------------------------------------------------------- setup
    def _initial_settings(self) -> WheelSettings:
        try:
            return self.library.get(self.config.last_profile_id).settings
        except KeyError:
            return WheelSettings()

    @property
    def settings(self) -> WheelSettings:
        return self._settings

    @property
    def telemetry(self) -> Telemetry:
        return self._telemetry

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def detected_game(self) -> DetectedGame | None:
        return self._detected_game

    @property
    def last_game_change(self):
        return self._last_game_change

    @property
    def current_profile_id(self) -> str | None:
        return self._current_profile_id

    @property
    def selected_profile_id(self) -> str:
        return self._current_profile_id or self.config.last_profile_id

    @property
    def current_profile(self) -> Profile | None:
        if not self._current_profile_id:
            return None
        try:
            return self.library.get(self._current_profile_id)
        except KeyError:
            return None

    @property
    def selected_profile(self) -> Profile | None:
        try:
            return self.library.get(self.selected_profile_id)
        except KeyError:
            return None

    @property
    def config_dir(self) -> Path:
        return self.store.base_dir

    @property
    def busy(self) -> bool:
        return self._user_io_active > 0

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_sidebar()
        self._build_topbar()
        self._build_content()
        self._build_statusbar()

    def _build_sidebar(self) -> None:
        sidebar = tk.Frame(self, bg=COLORS["sidebar"], width=218)
        sidebar.grid(row=0, column=0, rowspan=3, sticky="nsew")
        sidebar.grid_propagate(False)
        brand = tk.Frame(sidebar, bg=COLORS["sidebar"], height=92)
        brand.pack(fill="x", padx=22, pady=(20, 8))
        brand.pack_propagate(False)
        icon = tk.Canvas(brand, width=42, height=42, bg=COLORS["sidebar"], highlightthickness=0)
        icon.pack(side="left")
        icon.create_oval(4, 4, 38, 38, outline=COLORS["accent"], width=4)
        icon.create_oval(16, 16, 26, 26, outline=COLORS["text"], width=2)
        icon.create_line(21, 6, 21, 16, fill=COLORS["text"], width=3)
        icon.create_line(8, 31, 17, 22, fill=COLORS["text"], width=3)
        icon.create_line(34, 31, 25, 22, fill=COLORS["text"], width=3)
        text = tk.Frame(brand, bg=COLORS["sidebar"])
        text.pack(side="left", padx=(10, 0))
        make_label(
            text, "PYFFB", fg=COLORS["text"], bg=COLORS["sidebar"], font=(FONTS["title"][0], 16, "bold")
        ).pack(anchor="w")
        make_label(
            text, "STUDIO", fg=COLORS["accent"], bg=COLORS["sidebar"], font=FONTS["tiny"]
        ).pack(anchor="w")

        nav = tk.Frame(sidebar, bg=COLORS["sidebar"])
        nav.pack(fill="x", padx=12, pady=(10, 0))
        items = [
            ("dashboard", "Dashboard", "Live wheel status"),
            ("tuning", "Tuning", "FFB and response"),
            ("profiles", "Profiles", "Game presets"),
            ("games", "Game Sync", "Automatic switching"),
            ("diagnostics", "Diagnostics", "Device console"),
            ("about", "About", "Scope and safety"),
        ]
        for key, label, hint in items:
            row = tk.Frame(nav, bg=COLORS["sidebar"])
            row.pack(fill="x", pady=2)
            bar = tk.Frame(row, bg=COLORS["sidebar"], width=3, height=44)
            bar.pack(side="left", fill="y")
            button = tk.Button(
                row,
                text=label,
                command=lambda name=key: self.show_view(name),
                bg=COLORS["sidebar"],
                fg=COLORS["muted"],
                activebackground=COLORS["panel"],
                activeforeground=COLORS["text"],
                relief="flat",
                bd=0,
                highlightthickness=0,
                anchor="w",
                padx=13,
                pady=5,
                font=FONTS["body_bold"],
                cursor="hand2",
            )
            button.pack(side="left", fill="x", expand=True)
            self._nav_buttons[key] = (row, bar, button)

        bottom = tk.Frame(sidebar, bg=COLORS["sidebar"])
        bottom.pack(side="bottom", fill="x", padx=20, pady=18)
        self.estop_btn = make_button(
            bottom,
            "E-STOP",
            self.emergency_stop,
            kind="danger",
            font=FONTS["body_bold"],
            padx=10,
            pady=9,
        )
        self.estop_btn.configure(state="disabled")
        self.estop_btn.pack(fill="x", pady=(0, 14))
        tk.Frame(bottom, bg=COLORS["border"], height=1).pack(fill="x", pady=(0, 14))
        self.side_status = StatusPill(bottom, "Offline", bg=COLORS["sidebar"])
        self.side_status.pack(anchor="w")
        self.side_device = make_label(
            bottom,
            "No wheel connected",
            fg=COLORS["muted"],
            bg=COLORS["sidebar"],
            font=FONTS["small"],
            wraplength=175,
        )
        self.side_device.pack(anchor="w", pady=(10, 2))
        self.side_profile = make_label(
            bottom,
            "Profile: --",
            fg=COLORS["faint"],
            bg=COLORS["sidebar"],
            font=FONTS["tiny"],
            wraplength=175,
        )
        self.side_profile.pack(anchor="w")
        docs = tk.Button(
            bottom,
            text="Documentation",
            command=lambda: self.open_docs("USER_GUIDE.md"),
            bg=COLORS["sidebar"],
            fg=COLORS["faint"],
            activebackground=COLORS["sidebar"],
            activeforeground=COLORS["muted"],
            relief="flat",
            bd=0,
            font=FONTS["tiny"],
            cursor="hand2",
            anchor="w",
            padx=0,
            pady=0,
        )
        docs.pack(anchor="w", pady=(10, 0))
        make_label(
            bottom,
            "Clean-room build",
            fg=COLORS["faint"],
            bg=COLORS["sidebar"],
            font=FONTS["tiny"],
        ).pack(anchor="w", pady=(2, 0))

    def _build_topbar(self) -> None:
        top = tk.Frame(self, bg=COLORS["bg"], height=86)
        top.grid(row=0, column=1, sticky="ew", padx=(24, 22), pady=(14, 0))
        top.grid_propagate(False)
        top.grid_columnconfigure(0, weight=1)
        title_box = tk.Frame(top, bg=COLORS["bg"])
        title_box.grid(row=0, column=0, sticky="nw")
        self.page_title = make_label(
            title_box, "Dashboard", fg=COLORS["text"], bg=COLORS["bg"], font=FONTS["display"]
        )
        self.page_title.pack(anchor="w")
        self.page_subtitle = make_label(
            title_box,
            "Live telemetry and quick wheel controls",
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            font=FONTS["small"],
        )
        self.page_subtitle.pack(anchor="w", pady=(2, 0))

        controls = tk.Frame(top, bg=COLORS["bg"])
        controls.grid(row=0, column=1, sticky="ne", pady=(7, 0))
        backend_wrap = tk.Frame(controls, bg=COLORS["bg"])
        backend_wrap.pack(side="left", padx=(0, 7))
        make_label(
            backend_wrap, "BACKEND", fg=COLORS["faint"], bg=COLORS["bg"], font=FONTS["tiny"]
        ).pack(anchor="w")
        self.backend_var = tk.StringVar(
            value=BACKEND_LABELS.get(self.config.backend_key, BACKEND_LABELS["openffboard"])
        )
        self.backend_combo = ttk.Combobox(
            backend_wrap,
            textvariable=self.backend_var,
            values=list(BACKEND_LABELS.values()),
            state="readonly",
            width=24,
        )
        self.backend_combo.pack(anchor="w", pady=(2, 0))
        self.backend_combo.bind("<<ComboboxSelected>>", self._on_backend_selected)

        port_wrap = tk.Frame(controls, bg=COLORS["bg"])
        port_wrap.pack(side="left", padx=(0, 5))
        make_label(port_wrap, "PORT", fg=COLORS["faint"], bg=COLORS["bg"], font=FONTS["tiny"]).pack(
            anchor="w"
        )
        port_row = tk.Frame(port_wrap, bg=COLORS["bg"])
        port_row.pack(anchor="w", pady=(2, 0))
        self.port_var = tk.StringVar(value=self.config.port or NO_PORT)
        self.port_combo = ttk.Combobox(
            port_row,
            textvariable=self.port_var,
            state="readonly",
            width=16,
        )
        self.port_combo.pack(side="left")
        self.port_refresh_btn = make_button(
            port_row, "↻", self.refresh_ports, kind="ghost", padx=7, pady=4
        )
        self.port_refresh_btn.pack(side="left", padx=(4, 0))

        connect_wrap = tk.Frame(controls, bg=COLORS["bg"])
        connect_wrap.pack(side="left", padx=(7, 0), pady=(16, 0))
        self.connect_btn = make_button(connect_wrap, "Connect", self.toggle_connection, kind="primary")
        self.connect_btn.pack()

    def _build_content(self) -> None:
        self.content = tk.Frame(self, bg=COLORS["bg"])
        self.content.grid(row=1, column=1, sticky="nsew", padx=(24, 22), pady=(4, 2))
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        views = {
            "dashboard": DashboardView,
            "tuning": TuningView,
            "profiles": ProfilesView,
            "games": GamesView,
            "diagnostics": DiagnosticsView,
            "about": AboutView,
        }
        for key, view_class in views.items():
            view = view_class(self.content, self)
            view.grid(row=0, column=0, sticky="nsew")
            self._views[key] = view
        self._views["dashboard"].tkraise()
        self._set_active_nav("dashboard")

    def _build_statusbar(self) -> None:
        bar = tk.Frame(self, bg=COLORS["sidebar"], height=28)
        bar.grid(row=2, column=1, sticky="ew", padx=(24, 22), pady=(2, 12))
        bar.pack_propagate(False)
        self.status_label = make_label(
            bar, "Ready", fg=COLORS["muted"], bg=COLORS["sidebar"], font=FONTS["small"]
        )
        self.status_label.pack(side="left", padx=8)
        make_label(
            bar,
            f"v{__version__}  ·  safety cap {self.config.safety_max_power_pct}%",
            fg=COLORS["faint"],
            bg=COLORS["sidebar"],
            font=FONTS["tiny"],
        ).pack(side="right", padx=8)

    def _install_log_handler(self) -> None:
        self._log_handler = GuiLogHandler(self._log_queue)
        logging.getLogger().addHandler(self._log_handler)

    def _fit_window(self) -> None:
        """Keep the whole window, including the E-stop, on screen."""

        try:
            self.update_idletasks()
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            # Small or high-DPI displays are more reliable maximized.
            if screen_w < 1420 or screen_h < 840:
                self.state("zoomed")
                return
            width = max(1100, min(self.winfo_width(), screen_w - 50))
            height = max(690, min(self.winfo_height(), screen_h - 90))
            x = max(10, (screen_w - width) // 2)
            y = max(10, (screen_h - height) // 2)
            self.geometry(f"{width}x{height}+{x}+{y}")
        except tk.TclError:
            pass

    def _startup(self) -> None:
        self.refresh_ports(announce=False)
        self._poll_job = self.after(60, self._poll_loop)
        interval = max(50, int(1000 / max(1, self.config.poll_hz)))
        self._telemetry_job = self.after(interval, self._telemetry_tick)
        self._game_job = self.after(1800, self._game_tick)
        self._refresh_sidebar()
        self._notify_connection_changed()
        for warning in self.store.warnings:
            self.set_status(warning, "warning")
            break
        if self.config.backend_key == "simulator":
            self.set_status("Simulator selected — click Connect to explore without hardware.", "info")
        else:
            self.set_status(
                "Select a port and connect. Use the simulator if no wheel is attached.", "info"
            )

    # -------------------------------------------------------------- navigation
    def _set_active_nav(self, key: str) -> None:
        for name, (row, bar, button) in self._nav_buttons.items():
            active = name == key
            row.configure(bg=COLORS["panel"] if active else COLORS["sidebar"])
            bar.configure(bg=COLORS["accent"] if active else COLORS["sidebar"])
            button.configure(
                bg=COLORS["panel"] if active else COLORS["sidebar"],
                fg=COLORS["text"] if active else COLORS["muted"],
                activebackground=COLORS["panel"],
            )

    def show_view(self, key: str) -> None:
        view = self._views.get(key)
        if view is None:
            return
        self._active_view = key
        view.tkraise()
        self._set_active_nav(key)
        self.page_title.configure(text=view.page_title)
        self.page_subtitle.configure(text=view.page_subtitle)
        if hasattr(view, "on_show"):
            view.on_show()

    def current_view(self) -> Any:
        return self._views.get(self._active_view)

    # ----------------------------------------------------------------- status
    def set_status(self, message: str, kind: str = "info") -> None:
        colors = {
            "info": COLORS["muted"],
            "success": COLORS["green"],
            "warning": COLORS["yellow"],
            "error": COLORS["red"],
        }
        self.status_label.configure(text=message, fg=colors.get(kind, COLORS["muted"]))
        if self._status_job:
            try:
                self.after_cancel(self._status_job)
            except tk.TclError:
                pass
        self._status_job = self.after(12000, self._clear_status)

    def _clear_status(self) -> None:
        self._status_job = None
        if self._closing:
            return
        if self._connected:
            self.status_label.configure(text="Connected", fg=COLORS["muted"])
        else:
            self.status_label.configure(text="Ready", fg=COLORS["muted"])

    def _refresh_sidebar(self) -> None:
        if self._connected and self.device_info:
            self.side_status.set("Online", COLORS["green"])
            info = self.device_info
            self.side_device.configure(
                text=f"{info.port}  ·  fw {info.firmware or '?'}\n{info.display_name}"
            )
        else:
            self.side_status.set("Offline", COLORS["faint"], text_color=COLORS["muted"])
            self.side_device.configure(text="No wheel connected")
        profile = self.current_profile or self.selected_profile
        self.side_profile.configure(
            text=f"Profile: {profile.name if profile else 'device state'}"
        )

    # ------------------------------------------------------------------ ports
    def _selected_backend_key(self) -> str:
        return BACKEND_KEYS.get(self.backend_var.get(), "openffboard")

    def _on_backend_selected(self, _event=None) -> None:
        if self._connected:
            return
        self.refresh_ports(announce=True)

    def refresh_ports(self, announce: bool = True) -> None:
        key = self._selected_backend_key()
        if key == "simulator":
            values = ["simulator"]
            self.port_var.set("simulator")
        else:
            values = []
            try:
                backend = make_backend(key)
                values = [item.port for item in backend.list_devices()]
            except BackendError as exc:
                self.set_status(str(exc), "warning")
            if not values:
                values = [NO_PORT]
                self.port_var.set(NO_PORT)
                if announce:
                    self.set_status(
                        "No serial ports found. Check USB/driver, or use the simulator backend.",
                        "warning",
                    )
            else:
                preferred = self.config.port
                self.port_var.set(preferred if preferred in values else values[0])
                if announce:
                    self.set_status(f"Found {len(values)} serial port(s).", "success")
        self.port_combo.configure(values=values)
        if self._connected:
            self.port_combo.configure(state="disabled")
            self.backend_combo.configure(state="disabled")
            self.port_refresh_btn.configure(state="disabled")
        else:
            self.port_combo.configure(state="readonly")
            self.backend_combo.configure(state="readonly")
            self.port_refresh_btn.configure(state="normal")
        self.estop_btn.configure(state="normal" if self._connected else "disabled")

    # ------------------------------------------------------------- connection
    def toggle_connection(self) -> None:
        if self._connected:
            self.disconnect_device()
        else:
            self.connect_device()

    def connect_device(self) -> None:
        if self._connecting or self._disconnecting or self._user_io_active:
            return
        key = self._selected_backend_key()
        port = self.port_var.get().strip()
        if key != "simulator" and (not port or port == NO_PORT):
            self.set_status("Choose a serial port before connecting.", "warning")
            return
        if port == NO_PORT:
            return
        self._connecting = True
        self.connect_btn.configure(state="disabled", text="Connecting…")
        self.backend_combo.configure(state="disabled")
        self.port_combo.configure(state="disabled")
        self.port_refresh_btn.configure(state="disabled")
        self._run_task(
            "Connecting…",
            lambda: self._open_session(key, port),
            self._connection_opened,
            self._connection_failed,
        )

    def _open_session(self, key: str, port: str):
        backend = make_backend(key)
        controller = WheelController(
            backend,
            SafetyPolicy(max_power_pct=self.config.safety_max_power_pct),
        )
        try:
            info = controller.connect(port)
            read = controller.read_settings()
            try:
                telemetry = controller.read_telemetry(read.settings.rotation_deg)
            except BackendError:
                telemetry = Telemetry()
            return controller, info, read, telemetry
        except BaseException:
            try:
                controller.disconnect()
            except Exception:
                pass
            raise

    def _connection_opened(self, result) -> None:
        controller, info, read, telemetry = result
        self._connecting = False
        self.controller = controller
        self.device_info = info
        self._connected = True
        self._settings = read.settings
        self._telemetry = telemetry
        self._telemetry_failures = 0
        self._current_profile_id = self._matching_profile_id(read.settings)
        self._session.reset()
        self.connect_btn.configure(state="normal", text="Disconnect")
        self.refresh_ports(announce=False)
        self._save_config(backend_key=controller.backend.key, port=info.port)
        self._refresh_sidebar()
        self._notify_connection_changed()
        self._notify_settings_changed()
        self.set_status(
            f"Connected to {info.display_name} on {info.port} (fw {info.firmware or '?'}).",
            "success",
        )
        if read.missing:
            self.set_status(
                "Connected, but some settings could not be read: " + ", ".join(read.missing),
                "warning",
            )

    def _connection_failed(self, error: BaseException) -> None:
        self._connecting = False
        self._connected = False
        self.controller = None
        self.device_info = None
        self.connect_btn.configure(state="normal", text="Connect")
        self._enable_connection_controls(True)
        self._refresh_sidebar()
        self._notify_connection_changed()
        self.set_status(f"Connection failed: {error}", "error")
        self.estop_btn.configure(state="disabled")

    def disconnect_device(self) -> None:
        if self._disconnecting or not self.controller:
            return
        self._disconnecting = True
        self.connect_btn.configure(state="disabled", text="Disconnecting…")
        controller = self.controller
        self._run_task(
            "Disconnecting…",
            controller.disconnect,
            lambda _result: self._connection_closed(),
            lambda error: self._connection_closed(error),
        )

    def _connection_closed(self, error: BaseException | None = None) -> None:
        self._disconnecting = False
        self._connected = False
        self.controller = None
        self.device_info = None
        self._telemetry = Telemetry()
        self._telemetry_failures = 0
        self._session.reset()
        self._current_profile_id = self.config.last_profile_id
        self._settings = self._initial_settings()
        self.connect_btn.configure(state="normal", text="Connect")
        self._enable_connection_controls(True)
        self.refresh_ports(announce=False)
        self._refresh_sidebar()
        self._notify_connection_changed()
        self._notify_settings_changed()
        if error:
            self.set_status(f"Disconnected with error: {error}", "warning")
        else:
            self.set_status("Disconnected.", "info")

    def _enable_connection_controls(self, enabled: bool) -> None:
        state = "readonly" if enabled else "disabled"
        self.backend_combo.configure(state=state)
        self.port_combo.configure(state=state)
        self.port_refresh_btn.configure(state="normal" if enabled else "disabled")

    # ------------------------------------------------------------- e-stop
    def emergency_stop(self) -> None:
        if not self._connected or not self.controller or self._estop_active:
            return
        self._estop_active = True
        self.estop_btn.configure(state="disabled", text="STOPPING")
        controller = self.controller

        def worker() -> None:
            error: BaseException | None = None
            try:
                controller.emergency_stop()
                try:
                    controller.disconnect()
                except Exception:
                    pass
            except BaseException as exc:
                error = exc
            self._ui_queue.put(lambda: self._after_emergency_stop(error))

        threading.Thread(target=worker, name="pyffb-estop", daemon=True).start()

    def _after_emergency_stop(self, error: BaseException | None) -> None:
        self._estop_active = False
        self.estop_btn.configure(text="E-STOP")
        if error:
            self.estop_btn.configure(state="normal")
            messagebox.showerror(
                "Emergency stop failed",
                "The software stop command failed.\n\n"
                "USE THE HARDWARE KILL SWITCH / POWER SWITCH IMMEDIATELY.\n\n"
                f"Error: {error}",
            )
            self.set_status("Software E-stop failed — use the hardware switch now.", "error")
            return
        self._connection_closed()
        self.set_status(
            "Emergency stop sent. Power-cycle the wheel and check the cause before reconnecting.",
            "error",
        )
        messagebox.showwarning(
            "Emergency stop sent",
            "Motor torque has been disabled.\n\n"
            "Power-cycle the wheel before reconnecting. Investigate the cause and verify "
            "the hardware emergency stop works.",
        )

    # ---------------------------------------------------------------- profiles
    def set_auto_switch(self, enabled: bool) -> None:
        self._save_config(auto_switch_games=bool(enabled))
        self._session.reset()
        self._notify_games_changed()
        self.set_status(
            "Automatic game switching enabled." if enabled else "Automatic game switching disabled.",
            "info",
        )
        if enabled:
            self.check_games_now()

    def set_auto_geometry(self, enabled: bool) -> None:
        self._save_config(auto_apply_geometry=bool(enabled))
        self._notify_games_changed()

    def set_auto_persist(self, enabled: bool) -> None:
        if enabled:
            self.set_status(
                "Auto-persist writes flash on every game start/exit; this is not recommended.",
                "warning",
            )
        self._save_config(auto_persist=bool(enabled))
        self._notify_games_changed()

    def set_desktop_profile(self, profile_id: str) -> None:
        if not self.library.has(profile_id):
            self.set_status(f"Unknown profile: {profile_id}", "error")
            return
        self._save_config(desktop_profile_id=profile_id)
        self._session.desktop_profile_id = profile_id
        self._notify_profiles_changed()
        self.set_status(f"Desktop profile set to {profile_id}.", "success")

    def save_custom_profiles(self) -> None:
        self._save_config(custom_profiles=[p.to_dict() for p in self.library.custom()])
        self._notify_profiles_changed()

    def create_custom_profile(
        self,
        name: str,
        settings: WheelSettings,
        *,
        game: str = "",
        exe_names: tuple[str, ...] = (),
        description: str = "",
        notes: tuple[str, ...] = (),
    ) -> Profile:
        profile = self.library.make_custom(
            name,
            settings,
            game=game,
            exe_names=exe_names,
            description=description,
            notes=notes,
        )
        self.save_custom_profiles()
        return profile

    def update_custom_profile(self, profile: Profile) -> Profile:
        if profile.builtin or profile.id not in {p.id for p in self.library.custom()}:
            raise ValueError("only custom profiles can be edited")
        updated = self.library.add_custom(profile, replace_existing=True)
        self.save_custom_profiles()
        return updated

    def delete_custom_profile(self, profile_id: str) -> None:
        if profile_id == self.config.desktop_profile_id:
            raise ValueError("the desktop profile cannot be deleted; choose another desktop profile first")
        self.library.remove_custom(profile_id)
        changes: dict[str, Any] = {
            "custom_profiles": [p.to_dict() for p in self.library.custom()]
        }
        if self.config.last_profile_id == profile_id:
            changes["last_profile_id"] = self.config.desktop_profile_id
        self._save_config(**changes)
        if self._current_profile_id == profile_id:
            self._current_profile_id = None
        self._notify_profiles_changed()
        self._refresh_sidebar()
        self.set_status(f"Deleted custom profile {profile_id}.", "info")

    def import_profile_file(self, path: Path) -> Profile:
        from ..config import import_profile

        profile = import_profile(path)
        result = self.library.add_custom(profile)
        self.save_custom_profiles()
        return result

    def export_profile_file(self, profile_id: str, path: Path) -> None:
        from ..config import export_profile

        export_profile(self.library.get(profile_id), path)

    def _notify_profiles_changed(self) -> None:
        for view in self._views.values():
            callback = getattr(view, "on_profiles_changed", None)
            if callback:
                try:
                    callback()
                except Exception:
                    log.exception("Profile view refresh failed")
        self._refresh_sidebar()

    def apply_profile(
        self,
        profile_id: str,
        *,
        persist: bool = False,
        source: str = "manual",
    ) -> bool:
        if not self._connected or not self.controller:
            self.set_status("Connect a wheel before applying a profile.", "warning")
            return False
        if self._user_io_active:
            self.set_status("Another device operation is still running; try again in a moment.", "warning")
            return False
        try:
            profile = self.library.get(profile_id)
        except KeyError:
            self.set_status(f"Unknown profile: {profile_id}", "error")
            return False
        include_geometry = True if source == "manual" else self.config.auto_apply_geometry
        label = (
            f"Applying {profile.name}…"
            if source != "auto"
            else f"Auto-switch: applying {profile.name}…"
        )
        controller = self.controller
        self._run_task(
            label,
            lambda: controller.apply_profile(
                profile,
                include_geometry=include_geometry,
                persist=persist,
            ),
            lambda report: self._profile_applied(
                profile, report, include_geometry, source, controller
            ),
            lambda error: self.set_status(f"Profile apply failed: {error}", "error"),
        )
        return True

    def _profile_applied(
        self,
        profile: Profile,
        report: ApplyReport,
        include_geometry: bool,
        source: str,
        controller: WheelController,
    ) -> None:
        if self.controller is not controller or not self._connected:
            return
        if not report.ok:
            self.set_status("Profile apply failed: " + "; ".join(report.errors), "error")
            if report.rolled_back:
                self.set_status("Profile apply failed; previous settings were restored.", "error")
            return
        effective, _ = controller.policy.enforce(profile.settings)
        values = self._settings.to_dict()
        for field in report.fields:
            if field in values:
                values[field] = getattr(effective, field)
        if report.persisted:
            pass
        self._settings = WheelSettings.from_dict(values)
        self._current_profile_id = profile.id
        if source == "manual":
            self._save_config(last_profile_id=profile.id)
        self._notify_settings_changed()
        self._refresh_sidebar()
        suffix = "saved to flash" if report.persisted else "applied in RAM"
        count = len(report.fields)
        self.set_status(
            f"{profile.name}: {suffix} ({count} field(s) changed).",
            "success",
        )
        for warning in report.warnings:
            self.set_status(f"{profile.name}: {warning}", "warning")
            break
        if source == "auto":
            self._auto_inflight = False
            self._process_pending_auto_change()

    def apply_current_settings(self, settings: WheelSettings, *, persist: bool = False) -> bool:
        if not self._connected or not self.controller:
            self.set_status("Connect a wheel before writing settings.", "warning")
            return False
        if self._user_io_active:
            self.set_status("Another device operation is still running.", "warning")
            return False
        controller = self.controller
        self._run_task(
            "Applying tuning…",
            lambda: controller.apply_settings(settings, include_geometry=True, persist=persist),
            lambda report: self._tuning_applied(settings, report, controller),
            lambda error: self.set_status(f"Apply failed: {error}", "error"),
        )
        return True

    def _tuning_applied(
        self,
        requested: WheelSettings,
        report: ApplyReport,
        controller: WheelController,
    ) -> None:
        if self.controller is not controller or not self._connected:
            return
        if not report.ok:
            self.set_status("Tuning was not applied: " + "; ".join(report.errors), "error")
            return
        effective, _ = controller.policy.enforce(requested)
        values = self._settings.to_dict()
        for field in report.fields:
            if field in values:
                values[field] = getattr(effective, field)
        self._settings = WheelSettings.from_dict(values)
        self._current_profile_id = None
        self._notify_settings_changed()
        self._refresh_sidebar()
        suffix = "saved to flash" if report.persisted else "applied in RAM"
        self.set_status(f"Tuning {suffix}.", "success")
        for warning in report.warnings:
            self.set_status(warning, "warning")
            break

    def center_axis(self) -> None:
        if not self._connected or not self.controller:
            self.set_status("Connect a wheel first.", "warning")
            return
        if self._user_io_active:
            self.set_status("Another device operation is still running.", "warning")
            return
        controller = self.controller
        self._run_task(
            "Setting axis centre…",
            controller.center_axis,
            lambda _result: self.set_status(
                "Wheel centre set. Check the direction and endstops before applying force.",
                "success",
            ),
            lambda error: self.set_status(f"Centre command failed: {error}", "error"),
        )

    def reload_settings(self) -> None:
        if not self._connected or not self.controller:
            self.set_status("Connect a wheel first.", "warning")
            return
        if self._user_io_active:
            self.set_status("Another device operation is still running.", "warning")
            return
        controller = self.controller
        self._run_task(
            "Reading wheel settings…",
            controller.read_settings,
            lambda read: self._settings_reloaded(read, controller),
            lambda error: self.set_status(f"Read failed: {error}", "error"),
        )

    def _settings_reloaded(self, read, controller: WheelController) -> None:
        if self.controller is not controller or not self._connected:
            return
        self._settings = read.settings
        self._current_profile_id = self._matching_profile_id(read.settings)
        self._notify_settings_changed()
        self._refresh_sidebar()
        if read.missing:
            self.set_status(
                "Settings read with missing fields: " + ", ".join(read.missing), "warning"
            )
        else:
            self.set_status("Settings read from wheel.", "success")

    def _matching_profile_id(self, settings: WheelSettings) -> str | None:
        target = settings.to_dict()
        for profile in self.library.all():
            if profile.settings.to_dict() == target:
                return profile.id
        return None

    # ------------------------------------------------------------------ games
    def _game_tick(self) -> None:
        if self._closing:
            return
        self._scan_games()
        self._game_job = self.after(2000, self._game_tick)

    def check_games_now(self) -> None:
        self.set_status("Scanning for running games…", "info")
        self._scan_games(force=True)
        if not self._auto_inflight and not self._user_io_active:
            self.set_status("Game scan complete.", "info")

    def _scan_games(self, force: bool = False) -> None:
        try:
            names = process_snapshot()
        except Exception as exc:
            log.warning("Process scan failed: %s", exc)
            names = []
        detected = find_running_game(self.library, names)
        self._detected_game = detected
        for view in self._views.values():
            callback = getattr(view, "on_game_changed", None)
            if callback:
                try:
                    callback(detected)
                except Exception:
                    log.exception("Game view refresh failed")
        if not self.config.auto_switch_games:
            self._session.reset()
            return
        change = self._session.update(names)
        if change is None:
            return
        self._last_game_change = change
        if self._auto_inflight:
            self._pending_auto_change = change
            return
        self._start_auto_apply(change)

    def _start_auto_apply(self, change) -> None:
        try:
            profile = self.library.get(change.profile_id)
        except KeyError:
            self.set_status(f"Auto profile not found: {change.profile_id}", "error")
            return
        if not self._connected or not self.controller:
            self._last_game_change = change
            return
        self._auto_inflight = True
        reason = {
            "game_started": "Game started",
            "game_switched": "Game changed",
            "game_exited": "Game exited",
        }.get(change.reason, change.reason)
        controller = self.controller
        geometry = self.config.auto_apply_geometry
        persist = self.config.auto_persist
        self._run_task(
            f"{reason}: applying {profile.name}…",
            lambda: controller.apply_profile(
                profile,
                include_geometry=geometry,
                persist=persist,
            ),
            lambda report: self._auto_applied(profile, report, controller),
            lambda error: self._auto_failed(error),
        )

    def _auto_applied(
        self,
        profile: Profile,
        report: ApplyReport,
        controller: WheelController,
    ) -> None:
        self._auto_inflight = False
        if self.controller is not controller or not self._connected:
            self._process_pending_auto_change()
            return
        if report.ok:
            effective, _ = controller.policy.enforce(profile.settings)
            values = self._settings.to_dict()
            for field in report.fields:
                if field in values:
                    values[field] = getattr(effective, field)
            self._settings = WheelSettings.from_dict(values)
            self._current_profile_id = profile.id
            self._notify_settings_changed()
            self._refresh_sidebar()
            self.set_status(f"Auto-switched to {profile.name}.", "success")
        else:
            self.set_status("Auto-switch failed: " + "; ".join(report.errors), "error")
        self._process_pending_auto_change()

    def _auto_failed(self, error: BaseException) -> None:
        self._auto_inflight = False
        self.set_status(f"Auto-switch failed: {error}", "error")
        self._process_pending_auto_change()

    def _process_pending_auto_change(self) -> None:
        change = self._pending_auto_change
        self._pending_auto_change = None
        if change is not None:
            self.after(10, lambda: self._start_auto_apply(change))

    # ------------------------------------------------------------- diagnostics
    def send_raw_command(self, command: str, callback: Callable[[Any], None]) -> None:
        if not self._connected or not self.controller:
            self.set_status("Connect a wheel before sending commands.", "warning")
            return
        if self._user_io_active:
            self.set_status("Another device operation is still running.", "warning")
            return

        controller = self.controller

        def done(reply) -> None:
            if self.controller is controller:
                callback(reply)

        self._run_task(
            "Sending diagnostic command…",
            lambda: controller.raw_command(command),
            done,
            lambda error: self.set_status(f"Command failed: {error}", "error"),
        )

    def run_self_test(self, callback: Callable[[str], None]) -> None:
        if not self._connected or not self.controller:
            callback("Not connected.")
            return
        if self._user_io_active:
            callback("Another device operation is still running.")
            return

        controller = self.controller

        def work() -> str:
            lines = ["PyFFB self-test", f"time: {time.strftime('%Y-%m-%d %H:%M:%S')}"]
            info = self.device_info
            if info:
                lines.extend(
                    [
                        f"backend: {info.backend_key}",
                        f"port: {info.port}",
                        f"firmware: {info.firmware}",
                        f"hardware: {info.hardware}",
                    ]
                )
            read = controller.read_settings()
            lines.append(
                "settings read: "
                + ("OK" if read.complete else "partial (" + ", ".join(read.missing) + ")")
            )
            telemetry = controller.read_telemetry(read.settings.rotation_deg)
            lines.extend(
                [
                    f"position_deg: {_fmt(telemetry.position_deg)}",
                    f"torque_pct: {_fmt(telemetry.torque_pct)}",
                    f"speed_dps: {_fmt(telemetry.speed_dps)}",
                    f"ffb_active: {telemetry.ffb_active}",
                    f"supply_voltage: {_fmt(telemetry.supply_voltage)}",
                    f"temperature_c: {_fmt(telemetry.temperature_c)}",
                    "result: PASS",
                ]
            )
            return "\n".join(lines)

        self._run_task(
            "Running self-test…",
            work,
            callback,
            lambda error: callback(f"Self-test failed: {error}"),
        )

    def diagnostic_report(self) -> str:
        info = self.device_info
        t = self._telemetry
        lines = [
            f"PyFFB Studio {__version__}",
            f"config: {self.config_dir}",
            f"backend: {self.config.backend_key}",
            f"connected: {self._connected}",
        ]
        if info:
            lines.extend(
                [
                    f"device: {info.display_name}",
                    f"port: {info.port}",
                    f"firmware: {info.firmware}",
                    f"hardware: {info.hardware}",
                ]
            )
        lines.extend(
            [
                f"profile: {self.current_profile_id or self.selected_profile_id}",
                f"telemetry: pos={_fmt(t.position_deg)} torque={_fmt(t.torque_pct)} "
                f"ffb={t.ffb_active} voltage={_fmt(t.supply_voltage)} temp={_fmt(t.temperature_c)}",
                f"safety cap: {self.config.safety_max_power_pct}%",
            ]
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------ tasks
    def _run_task(
        self,
        label: str,
        function: Callable[[], Any],
        on_success: Callable[[Any], None] | None,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> None:
        if self._closing:
            return
        try:
            future = self._executor.submit(function)
        except RuntimeError:
            self.set_status("Application is shutting down.", "warning")
            return
        self._user_io_active += 1
        self._tasks.append(_Task(future, label, on_success, on_error))
        self.set_status(label, "info")

    def _poll_loop(self) -> None:
        if self._closing:
            return
        self._drain_tasks()
        self._drain_ui_queue()
        self._drain_logs()
        self._check_telemetry()
        self._poll_job = self.after(60, self._poll_loop)

    def _drain_tasks(self) -> None:
        pending = list(self._tasks)
        for task in pending:
            if not task.future.done():
                continue
            try:
                self._tasks.remove(task)
            except ValueError:
                continue
            self._user_io_active = max(0, self._user_io_active - 1)
            try:
                result = task.future.result()
            except BaseException as exc:
                log.error("%s failed: %s", task.label, exc)
                try:
                    if task.on_error:
                        task.on_error(exc)
                    else:
                        self.set_status(f"{task.label} failed: {exc}", "error")
                except Exception:
                    log.exception("Task error callback failed")
                continue
            try:
                if task.on_success:
                    task.on_success(result)
            except Exception:
                log.exception("Task success callback failed")

    def _drain_ui_queue(self) -> None:
        while True:
            try:
                callback = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                callback()
            except Exception:
                log.exception("UI callback failed")

    def _drain_logs(self) -> None:
        while True:
            try:
                message = self._log_queue.get_nowait()
            except queue.Empty:
                break
            self._log_buffer.append(message)
            if len(self._log_buffer) > 1200:
                del self._log_buffer[:200]
            diagnostics = self._views.get("diagnostics")
            if diagnostics and hasattr(diagnostics, "append_log"):
                try:
                    diagnostics.append_log(message)
                except Exception:
                    pass

    # --------------------------------------------------------------- telemetry
    def _telemetry_tick(self) -> None:
        if self._closing:
            return
        interval = max(50, int(1000 / max(1, self.config.poll_hz)))
        self._telemetry_job = self.after(interval, self._telemetry_tick)
        if (
            not self._connected
            or self.controller is None
            or self._user_io_active
            or self._telemetry_future is not None
            or self._telemetry_failures >= 4
        ):
            return
        rotation = self._settings.rotation_deg
        try:
            self._telemetry_future = self._executor.submit(
                self.controller.read_telemetry, rotation
            )
        except RuntimeError:
            self._telemetry_future = None

    def _check_telemetry(self) -> None:
        future = self._telemetry_future
        if future is None or not future.done():
            return
        self._telemetry_future = None
        try:
            telemetry = future.result()
        except BaseException as exc:
            self._telemetry_failures += 1
            log.debug("Telemetry read failed (%s): %s", self._telemetry_failures, exc)
            if self._telemetry_failures == 3:
                self.set_status(f"Telemetry unavailable: {exc}", "warning")
            if self._telemetry_failures >= 4 and self._connected:
                self._connection_lost()
            return
        self._telemetry_failures = 0
        self._telemetry = telemetry
        for view in self._views.values():
            callback = getattr(view, "on_telemetry", None)
            if callback:
                try:
                    callback(telemetry)
                except Exception:
                    log.exception("Telemetry view update failed")
        self._refresh_sidebar()

    def _connection_lost(self) -> None:
        self.set_status("Connection lost. Reconnect the wheel.", "error")
        controller = self.controller
        if controller:
            try:
                controller.backend.disconnect()
            except Exception:
                pass
        self._connection_closed()

    # --------------------------------------------------------------- notify
    def _notify_connection_changed(self) -> None:
        for view in self._views.values():
            callback = getattr(view, "on_connection_changed", None)
            if callback:
                try:
                    callback()
                except Exception:
                    log.exception("Connection view update failed")

    def _notify_settings_changed(self) -> None:
        for view in self._views.values():
            callback = getattr(view, "on_settings_changed", None)
            if callback:
                try:
                    callback()
                except Exception:
                    log.exception("Settings view update failed")

    def _notify_games_changed(self) -> None:
        for view in self._views.values():
            callback = getattr(view, "on_profiles_changed", None)
            if callback:
                try:
                    callback()
                except Exception:
                    log.exception("Game settings view update failed")

    # ----------------------------------------------------------------- config
    def _save_config(self, **changes: Any) -> None:
        try:
            data = self.config.to_dict()
            data.update(changes)
            config = AppConfig.from_dict(data)
            self.config = config
            self.store.save(config)
        except Exception as exc:
            log.exception("Could not save config")
            self.set_status(f"Could not save configuration: {exc}", "error")

    # ------------------------------------------------------------------- misc
    def open_docs(self, name: str = "USER_GUIDE.md") -> None:
        candidates = [
            Path(__file__).resolve().parents[2] / "docs" / name,
            Path.cwd() / "docs" / name,
            Path(__file__).resolve().parents[2] / name,
        ]
        for path in candidates:
            if path.exists():
                self._open_path(path)
                return
        self.set_status(f"Documentation file not found: docs/{name}", "warning")

    def open_config_dir(self) -> None:
        self.store.ensure_dirs()
        self._open_path(self.store.base_dir)

    def open_log_dir(self) -> None:
        self.store.ensure_dirs()
        self._open_path(self.store.log_dir)

    def _open_path(self, path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            self.set_status(f"Could not open {path}: {exc}", "warning")

    # ------------------------------------------------------------------ close
    def on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        geometry = ""
        try:
            geometry = self.geometry()
        except tk.TclError:
            pass
        if geometry:
            self._save_config(window_geometry=geometry)
        for job in (self._poll_job, self._telemetry_job, self._game_job):
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        if self._log_handler:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler = None
        controller = self.controller
        if controller:
            try:
                controller.disconnect()
            except Exception:
                pass
        self._executor.shutdown(wait=False, cancel_futures=True)
        try:
            self.destroy()
        except tk.TclError:
            pass


def _fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, float):
        return f"{value:.1f}{suffix}"
    return f"{value}{suffix}"


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()  # type: ignore[attr-defined]
    except Exception:
        pass


def run_gui(*, store: ConfigStore, config: AppConfig, library: ProfileLibrary) -> int:
    _enable_dpi_awareness()
    try:
        app = PyFFBApp(store=store, config=config, library=library)
    except tk.TclError as exc:
        print(f"Could not start the desktop UI: {exc}", file=sys.stderr)
        return 2
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
    return 0
