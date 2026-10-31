"""Reusable Tk widgets with a consistent dark-sim-racing look."""

from __future__ import annotations

import math
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from .theme import COLORS, FONTS


def make_button(
    parent: tk.Misc,
    text: str,
    command: Callable[[], Any] | None = None,
    *,
    kind: str = "secondary",
    width: int | None = None,
    font: tuple[Any, ...] | None = None,
    padx: int = 14,
    pady: int = 7,
) -> tk.Button:
    palette = {
        "primary": (COLORS["accent"], COLORS["white"], COLORS["accent_hover"], COLORS["accent_dark"]),
        "secondary": (COLORS["panel_alt"], COLORS["text"], COLORS["panel_hover"], COLORS["border"]),
        "ghost": (COLORS["panel"], COLORS["muted"], COLORS["panel_alt"], COLORS["text"]),
        "danger": (COLORS["red_dark"], COLORS["red"], "#64252a", COLORS["white"]),
        "success": (COLORS["green_dark"], COLORS["green"], "#1b4d3d", COLORS["white"]),
    }
    bg, fg, active_bg, active_fg = palette.get(kind, palette["secondary"])
    kwargs: dict[str, Any] = {
        "text": text,
        "command": command,
        "bg": bg,
        "fg": fg,
        "activebackground": active_bg,
        "activeforeground": active_fg,
        "disabledforeground": COLORS["faint"],
        "relief": "flat",
        "bd": 0,
        "highlightthickness": 0,
        "font": font or FONTS["body_bold"],
        "cursor": "hand2",
        "padx": padx,
        "pady": pady,
    }
    if width:
        kwargs["width"] = width
    return tk.Button(parent, **kwargs)


def make_label(
    parent: tk.Misc,
    text: str = "",
    *,
    fg: str | None = None,
    bg: str | None = None,
    font: tuple[Any, ...] | None = None,
    anchor: str = "w",
    justify: str = "left",
    wraplength: int = 0,
) -> tk.Label:
    label = tk.Label(
        parent,
        text=text,
        fg=fg or COLORS["text"],
        bg=bg or COLORS["panel"],
        font=font or FONTS["body"],
        anchor=anchor,
        justify=justify,
    )
    if wraplength:
        label.configure(wraplength=wraplength)
    return label


class Card(tk.Frame):
    """Flat card with a one-pixel border and optional heading."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        padx: int = 18,
        pady: int = 16,
        accent: str | None = None,
    ) -> None:
        super().__init__(parent, bg=COLORS["border"], bd=0, highlightthickness=0)
        self.body = tk.Frame(self, bg=COLORS["panel"], bd=0)
        self.body.pack(fill="both", expand=True, padx=1, pady=1)
        if accent:
            stripe = tk.Frame(self.body, bg=accent, width=3)
            stripe.pack(side="left", fill="y")
        container = tk.Frame(self.body, bg=COLORS["panel"])
        container.pack(fill="both", expand=True, padx=padx, pady=pady)
        if title:
            header = tk.Frame(container, bg=COLORS["panel"])
            header.pack(fill="x", pady=(0, 10))
            make_label(header, title, font=FONTS["subtitle"], bg=COLORS["panel"]).pack(
                side="left", anchor="w"
            )
            if subtitle:
                make_label(
                    header,
                    subtitle,
                    fg=COLORS["muted"],
                    font=FONTS["small"],
                    bg=COLORS["panel"],
                ).pack(side="right", anchor="e")
        self.content = tk.Frame(container, bg=COLORS["panel"])
        self.content.pack(fill="both", expand=True)


class Divider(tk.Frame):
    def __init__(self, parent: tk.Misc, *, bg: str | None = None) -> None:
        super().__init__(parent, bg=bg or COLORS["border"], height=1)


class Badge(tk.Label):
    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        *,
        fg: str | None = None,
        bg: str | None = None,
        font: tuple[Any, ...] | None = None,
    ) -> None:
        super().__init__(
            parent,
            text=text,
            fg=fg or COLORS["green"],
            bg=bg or COLORS["green_dark"],
            font=font or FONTS["tiny"],
            padx=8,
            pady=3,
        )


class MetricCard(Card):
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        value: str = "--",
        detail: str = "",
        *,
        accent: str | None = None,
        value_font: tuple[Any, ...] | None = None,
    ) -> None:
        super().__init__(parent, padx=14, pady=11)
        accent = accent or COLORS["accent"]
        top = tk.Frame(self.content, bg=COLORS["panel"])
        top.pack(fill="x")
        self._dot = tk.Canvas(
            top, width=7, height=7, bg=COLORS["panel"], highlightthickness=0, bd=0
        )
        self._dot.create_oval(1, 1, 6, 6, fill=accent, outline="")
        self._dot.pack(side="left", padx=(0, 7))
        self._title = make_label(
            top, title.upper(), fg=COLORS["muted"], font=FONTS["tiny"], bg=COLORS["panel"]
        )
        self._title.pack(side="left")
        self._value = make_label(
            self.content,
            value,
            font=value_font or FONTS["metric"],
            bg=COLORS["panel"],
        )
        self._value.pack(fill="x", pady=(6, 0))
        self._detail = make_label(
            self.content,
            detail,
            fg=COLORS["muted"],
            font=FONTS["small"],
            bg=COLORS["panel"],
        )
        self._detail.pack(fill="x")
        self._accent = accent

    def set(self, value: str, detail: str = "", *, accent: str | None = None) -> None:
        self._value.configure(text=value)
        self._detail.configure(text=detail)
        if accent is not None:
            self._dot.itemconfigure(1, fill=accent)
            self._accent = accent


class StatusPill(tk.Frame):
    def __init__(self, parent: tk.Misc, text: str = "Offline", *, bg: str | None = None) -> None:
        super().__init__(parent, bg=bg or COLORS["panel_alt"], padx=9, pady=4)
        self._dot = tk.Canvas(
            self, width=8, height=8, bg=bg or COLORS["panel_alt"], highlightthickness=0, bd=0
        )
        self._dot.create_oval(1, 1, 7, 7, fill=COLORS["faint"], outline="")
        self._dot.pack(side="left", padx=(0, 6))
        self._label = make_label(
            self,
            text,
            fg=COLORS["muted"],
            font=FONTS["small"],
            bg=bg or COLORS["panel_alt"],
        )
        self._label.pack(side="left")

    def set(self, text: str, color: str, *, text_color: str | None = None) -> None:
        self._dot.itemconfigure(1, fill=color)
        self._label.configure(text=text, fg=text_color or COLORS["text"])


class SliderControl(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        label: str,
        *,
        from_: int = 0,
        to: int = 100,
        value: int = 0,
        suffix: str = "%",
        command: Callable[[int], Any] | None = None,
        compact: bool = False,
        bg: str | None = None,
    ) -> None:
        background = bg or COLORS["panel"]
        super().__init__(parent, bg=background)
        self._suffix = suffix
        self._command = command
        self._bg = background
        row = tk.Frame(self, bg=background)
        row.pack(fill="x")
        make_label(row, label, fg=COLORS["muted"], font=FONTS["small"], bg=background).pack(
            side="left"
        )
        self._value_label = make_label(
            row,
            f"{value}{suffix}",
            font=FONTS["small"],
            bg=background,
            fg=COLORS["text"],
        )
        self._value_label.pack(side="right")
        self._var = tk.IntVar(value=value)
        self.scale = ttk.Scale(
            self,
            from_=from_,
            to=to,
            orient="horizontal",
            variable=self._var,
            command=self._on_scale,
            length=170 if compact else 280,
        )
        self.scale.pack(fill="x", pady=(4, 0))

    def _on_scale(self, _value: str) -> None:
        try:
            current = int(round(float(self.scale.get())))
        except Exception:
            current = 0
        self._value_label.configure(text=f"{current}{self._suffix}")
        if self._command:
            self._command(current)

    def get(self) -> int:
        return int(round(float(self.scale.get())))

    def set(self, value: int) -> None:
        self.scale.set(value)
        self._value_label.configure(text=f"{int(round(value))}{self._suffix}")


class LabeledSpinbox(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        label: str,
        *,
        from_: int,
        to: int,
        value: int,
        suffix: str = "",
        increment: int = 1,
        width: int = 8,
        bg: str | None = None,
    ) -> None:
        background = bg or COLORS["panel"]
        super().__init__(parent, bg=background)
        make_label(self, label, fg=COLORS["muted"], font=FONTS["small"], bg=background).pack(
            side="left"
        )
        self.var = tk.StringVar(value=str(value))
        self.spin = ttk.Spinbox(
            self,
            from_=from_,
            to=to,
            increment=increment,
            textvariable=self.var,
            width=width,
            justify="right",
        )
        self.spin.pack(side="right")
        if suffix:
            make_label(
                self,
                suffix,
                fg=COLORS["faint"],
                font=FONTS["tiny"],
                bg=background,
            ).pack(side="right", padx=(0, 5))

    def get(self, default: int = 0) -> int:
        try:
            return int(float(self.var.get()))
        except ValueError:
            return default

    def set(self, value: int) -> None:
        self.var.set(str(value))


class ScrollableFrame(ttk.Frame):
    """Vertically scrollable container that works with the dark theme."""

    def __init__(self, parent: tk.Misc, *, bg: str | None = None) -> None:
        background = bg or COLORS["bg"]
        super().__init__(parent, style="TFrame")
        self.canvas = tk.Canvas(
            self,
            bg=background,
            highlightthickness=0,
            bd=0,
        )
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=background)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.after_idle(self._sync_scrollbar)

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)
        self.after_idle(self._sync_scrollbar)

    def _sync_scrollbar(self) -> None:
        try:
            needed = self.inner.winfo_reqheight() > self.canvas.winfo_height() + 1
            mapped = bool(self.scrollbar.winfo_ismapped())
            if needed and not mapped:
                self.scrollbar.pack(side="right", fill="y")
            elif not needed and mapped:
                self.scrollbar.pack_forget()
                self.canvas.yview_moveto(0)
        except tk.TclError:
            pass

    def _bind_wheel(self, _event: tk.Event) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_linux_wheel)
        self.canvas.bind_all("<Button-5>", self._on_linux_wheel)

    def _unbind_wheel(self, _event: tk.Event) -> None:
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        delta = int(getattr(event, "delta", 0))
        if not delta:
            return
        steps = max(1, abs(delta) // 120)
        self.canvas.yview_scroll(-steps if delta > 0 else steps, "units")

    def _on_linux_wheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(-1 if getattr(event, "num", 0) == 4 else 1, "units")


class WheelGauge(tk.Canvas):
    """Stylised wheel and position gauge; all drawing is vector-based."""

    def __init__(self, parent: tk.Misc, *, size: int = 300) -> None:
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=COLORS["panel"],
            highlightthickness=0,
            bd=0,
        )
        self.size = size
        self._position_pct = 0.0
        self._degrees = 0.0
        self._range = 900
        self._connected = False
        self.bind("<Configure>", lambda _event: self.redraw())

    def set_state(
        self,
        position_pct: float | None,
        degrees: float | None,
        range_deg: int,
        *,
        connected: bool = True,
    ) -> None:
        self._position_pct = max(-100.0, min(100.0, position_pct or 0.0))
        self._degrees = degrees or 0.0
        self._range = max(90, range_deg)
        self._connected = connected
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = max(200, self.winfo_width())
        height = max(200, self.winfo_height())
        cx, cy = width / 2.0, height / 2.0
        outer = min(width, height) * 0.37
        wheel_r = outer * 0.68
        pct = self._position_pct / 100.0

        # Outer gauge arc from lower-left over the top to lower-right.
        self.create_arc(
            cx - outer,
            cy - outer,
            cx + outer,
            cy + outer,
            start=225,
            extent=-270,
            style="arc",
            outline=COLORS["panel_alt"],
            width=3,
        )
        angle = 225.0 + (-270.0 * ((pct + 1.0) / 2.0))
        track_extent = (pct + 1.0) / 2.0 * -270.0
        if abs(track_extent) > 0.5:
            self.create_arc(
                cx - outer,
                cy - outer,
                cx + outer,
                cy + outer,
                start=225,
                extent=track_extent,
                style="arc",
                outline=COLORS["accent"] if self._connected else COLORS["faint"],
                width=4,
            )

        # Tick marks.
        for index in range(21):
            t = index / 20.0
            theta = math.radians(225.0 - 270.0 * t)
            inner = outer + 6
            length = 7 if index % 5 == 0 else 4
            x1 = cx + math.cos(theta) * inner
            y1 = cy - math.sin(theta) * inner
            x2 = cx + math.cos(theta) * (inner + length)
            y2 = cy - math.sin(theta) * (inner + length)
            color = COLORS["muted"] if index % 5 == 0 else COLORS["faint"]
            self.create_line(x1, y1, x2, y2, fill=color, width=1)

        # Pointer.
        theta = math.radians(angle)
        px = cx + math.cos(theta) * (outer - 3)
        py = cy - math.sin(theta) * (outer - 3)
        self.create_line(
            cx,
            cy,
            px,
            py,
            fill=COLORS["accent"] if self._connected else COLORS["faint"],
            width=2,
            dash=(3, 5),
        )
        self.create_oval(
            px - 4, py - 4, px + 4, py + 4,
            fill=COLORS["accent"] if self._connected else COLORS["faint"],
            outline="",
        )

        # Steering wheel, rotated visually within +/- 120 degrees.
        rotation = math.radians(pct * 120.0)
        rim_color = COLORS["border"] if not self._connected else COLORS["text"]
        self.create_oval(
            cx - wheel_r,
            cy - wheel_r,
            cx + wheel_r,
            cy + wheel_r,
            outline=COLORS["panel_alt"],
            width=17,
        )
        self.create_oval(
            cx - wheel_r,
            cy - wheel_r,
            cx + wheel_r,
            cy + wheel_r,
            outline=rim_color,
            width=6,
        )
        for base in (90, 210, 330):
            theta = math.radians(base) + rotation
            x = cx + math.cos(theta) * wheel_r * 0.82
            y = cy - math.sin(theta) * wheel_r * 0.82
            self.create_line(
                cx,
                cy,
                x,
                y,
                fill=rim_color,
                width=9,
                capstyle="round",
            )
        self.create_oval(
            cx - 25,
            cy - 25,
            cx + 25,
            cy + 25,
            fill=COLORS["panel_alt"],
            outline=rim_color,
            width=2,
        )
        # Top marker at 12 o'clock, rotating with the wheel.
        theta = math.radians(90) + rotation
        mx = cx + math.cos(theta) * wheel_r
        my = cy - math.sin(theta) * wheel_r
        self.create_oval(
            mx - 6, my - 6, mx + 6, my + 6,
            fill=COLORS["accent"] if self._connected else COLORS["faint"],
            outline=COLORS["panel"],
            width=2,
        )

        self.create_text(
            cx,
            cy + outer + 9,
            text=f"{self._degrees:+.0f}°" if self._connected else "OFFLINE",
            fill=COLORS["text"] if self._connected else COLORS["faint"],
            font=FONTS["metric_small"],
        )
        self.create_text(
            cx,
            cy + outer + 29,
            text=f"{self._range}° range",
            fill=COLORS["muted"],
            font=FONTS["small"],
        )
