"""ttk / tk styling for the word tier list (UI-3): one place that gives every standard widget the
pastel look. Call apply_ttk_style(root) after init_fonts(root). Uses the 'clam' theme because it
is the only built-in ttk theme that honours custom colours on every platform."""
import tkinter as tk
from tkinter import ttk

from fonts import font
from theme import PALETTE as P


def apply_ttk_style(root):
    """Style every ttk widget, the window background and (through the option database) menus, text panes and listboxes.

    Call once per root, after fonts.init_fonts(root). Returns the ttk.Style.
    """
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    body = font("body")
    root.configure(bg=P["bg"])

    # ---- plain tk widgets (menus, text panes, dialogs, listboxes) via the option database ----
    for pat, val in {
        "*Toplevel.background": P["bg"],
        "*Menu.background": P["surface"], "*Menu.foreground": P["text"],
        "*Menu.activeBackground": P["select_bg"], "*Menu.activeForeground": P["text"],
        "*Menu.relief": "flat", "*Menu.borderWidth": 0, "*Menu.font": body,
        "*Text.background": P["surface"], "*Text.foreground": P["text"],
        "*Text.relief": "flat", "*Text.highlightThickness": 1,
        "*Text.highlightBackground": P["border"], "*Text.highlightColor": P["accent"],
        "*Text.selectBackground": P["select_bg"], "*Text.selectForeground": P["text"],
        "*Text.insertBackground": P["text"], "*Text.padX": 8, "*Text.padY": 6,
        "*Listbox.background": P["surface"], "*Listbox.foreground": P["text"],
        "*Listbox.selectBackground": P["select_bg"], "*Listbox.selectForeground": P["text"],
        "*Listbox.relief": "flat", "*Listbox.highlightThickness": 0,
        "*TCombobox*Listbox.background": P["surface"], "*TCombobox*Listbox.foreground": P["text"],
        "*TCombobox*Listbox.selectBackground": P["select_bg"],
        "*TCombobox*Listbox.selectForeground": P["text"],
        "*TCombobox*Listbox.font": body,
    }.items():
        root.option_add(pat, val)

    # ---- ttk base ----
    style.configure(".", background=P["bg"], foreground=P["text"], font=body,
                    fieldbackground=P["surface"], bordercolor=P["border"],
                    lightcolor=P["bg"], darkcolor=P["bg"], troughcolor=P["surface2"],
                    focuscolor=P["bg"], selectbackground=P["select_bg"],
                    selectforeground=P["text"], insertcolor=P["text"])
    style.map(".", foreground=[("disabled", P["disabled"])])
    style.configure("TFrame", background=P["bg"])
    style.configure("TLabel", background=P["bg"], foreground=P["text"])

    style.configure("TButton", background=P["surface"], foreground=P["text"], padding=(14, 6),
                    borderwidth=1, relief="flat", bordercolor=P["border"],
                    lightcolor=P["surface"], darkcolor=P["surface"])
    style.map("TButton",
              background=[("pressed", P["select_bg"]), ("active", P["surface2"])],
              bordercolor=[("focus", P["accent"]), ("active", P["accent"])],
              lightcolor=[("pressed", P["select_bg"]), ("active", P["surface2"])],
              darkcolor=[("pressed", P["select_bg"]), ("active", P["surface2"])])

    for kind in ("TRadiobutton", "TCheckbutton"):
        style.configure(kind, background=P["bg"], foreground=P["text"], padding=(2, 3),
                        indicatorbackground=P["surface"], indicatorforeground=P["accent"],
                        indicatorcolor=P["surface"], upperbordercolor=P["border"],
                        lowerbordercolor=P["border"])
        style.map(kind,
                  background=[("active", P["bg"])],
                  indicatorcolor=[("selected", P["accent"]), ("active", P["surface2"])],
                  indicatorbackground=[("selected", P["accent"]), ("active", P["surface2"])])

    for kind in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(kind, fieldbackground=P["surface"], foreground=P["text"], padding=5,
                        bordercolor=P["border"], lightcolor=P["surface"], darkcolor=P["surface"],
                        insertcolor=P["text"], selectbackground=P["select_bg"],
                        selectforeground=P["text"])
        style.map(kind, bordercolor=[("focus", P["accent"])],
                  lightcolor=[("focus", P["accent"])], darkcolor=[("focus", P["accent"])])
    style.configure("TCombobox", arrowcolor=P["muted"], background=P["surface"])
    style.map("TCombobox", fieldbackground=[("readonly", P["surface"])],
              foreground=[("readonly", P["text"])], background=[("active", P["surface2"])])

    style.configure("Treeview", background=P["surface"], fieldbackground=P["surface"],
                    foreground=P["text"], borderwidth=0, relief="flat", rowheight=28)
    style.map("Treeview", background=[("selected", P["select_bg"])],
              foreground=[("selected", P["text"])])
    style.configure("Treeview.Heading", background=P["surface2"], foreground=P["muted"],
                    relief="flat", borderwidth=0, padding=(8, 5))
    style.map("Treeview.Heading", background=[("active", P["select_bg"])])

    for kind in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(kind, background=P["border"], troughcolor=P["bg"], bordercolor=P["bg"],
                        lightcolor=P["border"], darkcolor=P["border"], arrowcolor=P["muted"],
                        relief="flat", gripcount=0)
        style.map(kind, background=[("active", P["accent"]), ("pressed", P["accent"])])

    style.configure("Horizontal.TProgressbar", background=P["accent"], troughcolor=P["surface2"],
                    bordercolor=P["surface2"], lightcolor=P["accent"], darkcolor=P["accent"],
                    thickness=8)
    style.configure("TLabelframe", background=P["bg"], bordercolor=P["border"],
                    lightcolor=P["bg"], darkcolor=P["bg"], relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=P["bg"], foreground=P["muted"])
    style.configure("TSeparator", background=P["border"])
    return style
