"""Shared visual language for the Tkinter UI."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

COLORS = {
    "bg": "#0d1014",
    "sidebar": "#11161c",
    "panel": "#171d24",
    "panel_alt": "#1c232c",
    "panel_hover": "#232c37",
    "border": "#2a3441",
    "text": "#ecf1f6",
    "muted": "#8d9aa8",
    "faint": "#5f6c7a",
    "accent": "#ff6b35",
    "accent_hover": "#ff8054",
    "accent_dark": "#b84219",
    "green": "#43d6a0",
    "green_dark": "#14382d",
    "blue": "#59a7ff",
    "yellow": "#f5c451",
    "red": "#ff5a5f",
    "red_dark": "#401b1e",
    "purple": "#b993ff",
    "white": "#ffffff",
}

if sys.platform == "win32":
    UI_FONT = "Segoe UI"
    MONO_FONT = "Consolas"
elif sys.platform == "darwin":
    UI_FONT = "Helvetica Neue"
    MONO_FONT = "Menlo"
else:
    UI_FONT = "DejaVu Sans"
    MONO_FONT = "DejaVu Sans Mono"

FONTS = {
    "display": (UI_FONT, 26, "bold"),
    "title": (UI_FONT, 18, "bold"),
    "subtitle": (UI_FONT, 14, "bold"),
    "body": (UI_FONT, 10),
    "body_bold": (UI_FONT, 10, "bold"),
    "small": (UI_FONT, 9),
    "tiny": (UI_FONT, 8),
    "metric": (UI_FONT, 25, "bold"),
    "metric_small": (UI_FONT, 17, "bold"),
    "mono": (MONO_FONT, 9),
    "mono_small": (MONO_FONT, 8),
}


def configure_style(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(
        ".",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        fieldbackground=COLORS["panel_alt"],
        bordercolor=COLORS["border"],
        darkcolor=COLORS["panel"],
        lightcolor=COLORS["panel"],
        troughcolor=COLORS["panel_alt"],
        font=FONTS["body"],
    )
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Panel.TFrame", background=COLORS["panel"])
    style.configure("Card.TFrame", background=COLORS["panel"])
    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["text"])
    style.configure(
        "Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=FONTS["small"]
    )
    style.configure(
        "PanelMuted.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["muted"],
        font=FONTS["small"],
    )
    style.configure(
        "Title.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=FONTS["title"],
    )
    style.configure(
        "Subtitle.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["text"],
        font=FONTS["subtitle"],
    )
    style.configure(
        "TEntry",
        fieldbackground=COLORS["panel_alt"],
        foreground=COLORS["text"],
        insertcolor=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        padding=6,
    )
    style.map(
        "TEntry",
        fieldbackground=[("disabled", COLORS["panel"]), ("readonly", COLORS["panel_alt"])],
        foreground=[("disabled", COLORS["faint"])],
        bordercolor=[("focus", COLORS["accent"])],
    )
    style.configure(
        "TCombobox",
        fieldbackground=COLORS["panel_alt"],
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        arrowcolor=COLORS["muted"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        padding=5,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLORS["panel_alt"])],
        foreground=[("readonly", COLORS["text"])],
        selectbackground=[("readonly", COLORS["panel_alt"])],
        selectforeground=[("readonly", COLORS["text"])],
        bordercolor=[("focus", COLORS["accent"])],
    )
    style.configure(
        "TSpinbox",
        fieldbackground=COLORS["panel_alt"],
        foreground=COLORS["text"],
        arrowcolor=COLORS["muted"],
        bordercolor=COLORS["border"],
        padding=5,
    )
    style.configure(
        "TCheckbutton",
        background=COLORS["panel"],
        foreground=COLORS["text"],
        focuscolor=COLORS["panel"],
    )
    style.map(
        "TCheckbutton",
        background=[("active", COLORS["panel"])],
        foreground=[("active", COLORS["text"])],
    )
    style.configure(
        "TScale",
        background=COLORS["panel"],
        troughcolor=COLORS["panel_alt"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["accent"],
        darkcolor=COLORS["accent"],
    )
    style.map(
        "TScale",
        background=[("active", COLORS["panel"])],
        lightcolor=[("active", COLORS["accent_hover"])],
        darkcolor=[("active", COLORS["accent_hover"])],
    )
    style.configure(
        "Treeview",
        background=COLORS["panel"],
        fieldbackground=COLORS["panel"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        rowheight=28,
        font=FONTS["body"],
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["panel_alt"],
        foreground=COLORS["muted"],
        relief="flat",
        font=FONTS["small"],
        padding=(6, 6),
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["accent_dark"])],
        foreground=[("selected", COLORS["white"])],
    )
    style.map(
        "Treeview.Heading",
        background=[("active", COLORS["panel_hover"])],
    )
    style.configure("TScrollbar", background=COLORS["panel_alt"], troughcolor=COLORS["bg"])
    style.configure("Vertical.TScrollbar", width=11, arrowsize=12)
    style.configure("Horizontal.TScrollbar", height=11, arrowsize=12)
    return style
