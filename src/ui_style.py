"""ttk / tk styling for Word Tierlister (UI-3): one place that gives every standard widget the
pastel look. Call apply_ttk_style(root) after init_fonts(root). Uses the 'clam' theme because it
is the only built-in ttk theme that honours custom colours on every platform. It also gives the program its icon
(IC-1: set_icon, on every window and the taskbar)."""
import os
import sys
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
    set_icon(root)

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

    # the button Enter presses in a dialog: the accent outline and a soft lilac fill, so it reads as the default
    style.configure("Default.TButton", background=P["select_bg"], bordercolor=P["accent"])
    style.map("Default.TButton", background=[("pressed", P["accent"]), ("active", P["surface2"])])

    for kind in ("TRadiobutton", "TCheckbutton"):
        style.configure(kind, background=P["bg"], foreground=P["text"], padding=(2, 3),
                        indicatorbackground=P["surface"], indicatorforeground=P["accent"],
                        indicatorcolor=P["surface"], upperbordercolor=P["border"],
                        lowerbordercolor=P["border"])
        style.map(kind,
                  background=[("active", P["bg"])],
                  indicatorcolor=[("selected", P["accent"]), ("active", P["surface2"])],
                  indicatorbackground=[("selected", P["accent"]), ("active", P["surface2"])])
    _tick_boxes(root, style, font("body").metrics("linespace"))

    for kind in ("TEntry", "TSpinbox"):
        style.configure(kind, fieldbackground=P["surface"], foreground=P["text"], padding=5,
                        bordercolor=P["border"], lightcolor=P["surface"], darkcolor=P["surface"],
                        insertcolor=P["text"], selectbackground=P["select_bg"],
                        selectforeground=P["text"])
        style.map(kind, bordercolor=[("focus", P["accent"])],
                  lightcolor=[("focus", P["accent"])], darkcolor=[("focus", P["accent"])])

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


def _tick_boxes(root, style, line):
    """Tick boxes drawn as images (the clam theme's own is a tiny cross that is hard to read): a rounded
    white box with a hairline, when ticked a lilac box with a white tick, and when only some of what it stands
    for is ticked (the "alternate" state: tick.state(["alternate"])) a lilac box with a white minus. Sized from the
    body font."""
    n = max(13, int(line * 0.8)) | 1
    name = f"Tick{n}.indicator"
    kept = getattr(root, "_tick_images", {})
    if name in style.element_names() and name in kept:
        _tick_layout(style, name)              # styled again (the main window after start-up): the same images,
        return                                 # since new ones would free those the element still draws

    def box(fill, edge):
        img = tk.PhotoImage(master=root, width=n, height=n)
        img.put(P["bg"], to=(0, 0, n, n))
        img.put(edge, to=(1, 0, n - 1, n))                  # a slightly rounded square: corners stay bg
        img.put(edge, to=(0, 1, n, n - 1))
        img.put(fill, to=(2, 1, n - 2, n - 1))
        img.put(fill, to=(1, 2, n - 1, n - 2))
        return img
    off = box(P["surface"], P["disabled"])
    on = box(P["accent"], P["accent"])
    t = max(2, n // 7)                                       # stroke width of the tick
    pts = [(0.24, 0.52), (0.42, 0.70), (0.76, 0.30)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        steps = n * 2
        for i in range(steps + 1):
            x = int((x1 + (x2 - x1) * i / steps) * n)
            y = int((y1 + (y2 - y1) * i / steps) * n)
            on.put(P["surface"], to=(x - t // 2, y - t // 2, x - t // 2 + t, y - t // 2 + t))
    mixed = box(P["accent"], P["accent"])
    y = n // 2 - t // 2
    mixed.put(P["surface"], to=(int(n * 0.26), y, n - int(n * 0.26), y + t))
    kept[name] = (off, on, mixed)                            # keep references (Tk images are freed otherwise)
    root._tick_images = kept
    if name not in style.element_names():
        style.element_create(name, "image", off, ("alternate", mixed), ("selected", on),
                              width=n + max(6, n // 2), sticky="w")
    _tick_layout(style, name)


def _tick_layout(style, name):
    style.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
        (name, {"side": "left", "sticky": ""}),
        ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
            ("Checkbutton.label", {"sticky": "nswe"})]})]})])
    style.configure("TCheckbutton", padding=(2, 3, 2, 3))


# the program's icon (IC-1; drawn by tools/make_icon.py): beside this file in src/icons, and in a built program in the
# folder it unpacks to (PyInstaller puts this module's file there; standalone.pyinstaller_args packs "icons")
ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
APP_ID = "WordTierlister"          # (Windows: the taskbar groups the program's windows under its own icon, not Python's)


def set_icon(root):
    """The program's icon on `root` and every window opened from it later (iconphoto's default), in each size, so
    the title bar, taskbar and window switcher each pick a sharp one. Quietly nothing when the files are missing."""
    if getattr(root, "_icons", None):
        return
    try:
        root._icons = [tk.PhotoImage(master=root, file=os.path.join(ICONS, f"icon-{n}.png")) for n in ICON_SIZES]
        root.iconphoto(True, *reversed(root._icons))          # (the biggest first: some window managers take it)
    except (tk.TclError, OSError):
        root._icons = None
        return
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except (AttributeError, OSError):
            pass
