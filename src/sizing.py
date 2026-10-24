"""Window sizing that adapts to the screen and to the contents (used by every window).

Three questions this module answers:
    * How big is the usable screen?   usable_area(root): the monitor root's window is on (the pointer's for a
      window not shown yet; Linux asks xrandr, because Tk reports all monitors as one wide screen; Windows asks
      the system, because Tk reports only the main monitor), minus room for panels and title bars. monitor_at(root, x, y) and
      clamp_to_monitor() keep pop-ups (drop-downs, hover notes) on the monitor they open from.
    * Windows display scaling: set_dpi_awareness() (called before the first window) tells Windows the
      program sizes itself, so at 125% / 150% it is drawn sharp instead of stretched as a picture.
    * How big is "one unit" of UI?    ui_factor(root): 1.0 at the classic 96 dpi; larger on high-dpi
      screens where Tk's point-based fonts are bigger but pixel sizes written in code are not.
    * Where does a window go?         fit_size / center_geometry / place_dialog.
    * Is it maximized?                is_maximized(win) (the main window keeps a zoom of its own for that).

Layers that call this: App (main window), Browser, StartupWindow and the dialogs. Everything that
reads the screen goes through usable_area(), so tests can pretend to have a different screen.
"""
import os
import re
import shutil
import subprocess

REFERENCE_SCALING = 96 / 72      # Tk "scaling" (pixels per point) at 96 dpi
WIDTH_USE = 0.96                 # fraction of the monitor a window may take (leaves side bars)
HEIGHT_USE = 0.90                # smaller: panels, docks and the title bar eat vertical space

_MONITOR_RE = re.compile(r"^(\S+) connected (primary )?(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", re.M)
_xrandr_cache = {}


def ui_factor(root):
    """How much bigger than the classic 96 dpi layout this screen's text is (about 0.75 .. 3)."""
    try:
        scaling = float(root.tk.call("tk", "scaling"))
    except Exception:
        return 1.0
    return min(3.0, max(0.75, scaling / REFERENCE_SCALING))


def parse_xrandr(text):
    """Monitors from `xrandr --current` output: [(x, y, w, h, is_primary)], connected ones with a mode."""
    return [(int(x), int(y), int(w), int(h), bool(p))
            for _name, p, w, h, x, y in _MONITOR_RE.findall(text)]


def _xrandr_monitors(root):
    """Monitors on X11 (asked once); [] when xrandr is missing or not applicable."""
    if "monitors" in _xrandr_cache:
        return _xrandr_cache["monitors"]
    found = []
    try:
        if root.tk.call("tk", "windowingsystem") == "x11" and shutil.which("xrandr"):
            out = subprocess.run(["xrandr", "--current"], capture_output=True, text=True, timeout=1.5)
            found = parse_xrandr(out.stdout)
    except Exception:
        found = []
    _xrandr_cache["monitors"] = found
    return found


def _windows_monitors(user32=None):
    """Windows: each monitor's work area (without the taskbar) as [(x, y, w, h, is_primary)], [] on failure.
    Real pixels once set_dpi_awareness() has run (else Windows hands out scaled ones)."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = user32 or ctypes.windll.user32

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long),
                        ("bottom", ctypes.c_long)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

        found = []

        def each(hmon, _hdc, _rect, _data):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                r = info.rcWork
                found.append((r.left, r.top, r.right - r.left, r.bottom - r.top, bool(info.dwFlags & 1)))
            return 1
        proc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(RECT),
                                  ctypes.c_ssize_t)(each)
        user32.EnumDisplayMonitors(None, None, proc, 0)
        return found
    except Exception:
        return []


def monitors(root):
    """Every monitor as (x, y, w, h, is_primary), asked once; [] when the system cannot tell (then Tk's single
    screen is used)."""
    if "monitors" not in _xrandr_cache:
        found = []
        try:
            system = root.tk.call("tk", "windowingsystem")
        except Exception:
            system = ""
        if system == "x11":
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            found = [m for m in _xrandr_monitors(root) if m[0] + m[2] <= sw + 1 and m[1] + m[3] <= sh + 1]
        elif system == "win32":
            found = _windows_monitors()
        _xrandr_cache["monitors"] = found
    return _xrandr_cache["monitors"]


def monitor_at(root, px, py):
    """(x, y, w, h) of the monitor the point is on: else the nearest one, else Tk's whole screen."""
    mons = monitors(root)
    if mons:
        for x, y, w, h, _p in mons:
            if x <= px < x + w and y <= py < y + h:
                return x, y, w, h
        def gap(m):
            x, y, w, h, _p = m
            return max(x - px, 0, px - (x + w)) + max(y - py, 0, py - (y + h))
        return min(mons, key=gap)[:4]
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    if sw > 2.2 * sh:                      # several monitors reported as one very wide screen
        return 0, 0, int(sh * 16 / 9), sh
    return 0, 0, sw, sh


def _shown_window(w):
    """The window `w` is in, or the one that window belongs to (a dialog not shown yet: its parent), if it is on
    screen; else None."""
    try:
        top = w.winfo_toplevel()
        while top is not None:
            if top.winfo_viewable():
                return top
            top = top.master.winfo_toplevel() if top.master is not None else None
    except Exception:
        pass
    return None


def monitor_box(root):
    """(x, y, w, h) of the monitor to use: the one `root`'s window is on (or its parent's, for a dialog about to
    open); for a window not on screen yet, the one under the pointer, else the primary, else the screen. (It
    used to be always the pointer's: with the window on one monitor and the pointer on the other, a dialog was
    pushed onto the wrong one and the main window fitted itself to the wrong size.)"""
    win = _shown_window(root)
    if win is not None:
        try:
            return monitor_at(root, win.winfo_rootx() + win.winfo_width() // 2,
                              win.winfo_rooty() + win.winfo_height() // 2)
        except Exception:
            pass
    try:
        px, py = root.winfo_pointerxy()
    except Exception:
        px = py = -1
    mons = monitors(root)
    if mons and not any(x <= px < x + w and y <= py < y + h for x, y, w, h, _p in mons):
        for x, y, w, h, primary in mons:
            if primary:
                return x, y, w, h
    return monitor_at(root, px, py)


def clamp_to_monitor(root, x, y, w, h, at=None):
    """(x, y) moved just enough that a w x h pop-up stays on the monitor of the point `at` (default: x, y).
    A pop-up from a window on a second monitor stays there (it used to be pushed onto the main one)."""
    mx, my, mw, mh = monitor_at(root, *(at or (x, y)))
    return max(mx, min(x, mx + mw - w)), max(my, min(y, my + mh - h))


def set_dpi_awareness(windll=None):
    """Windows: tell the system this program handles display scaling itself (per monitor), before the first
    window opens. Without it, at 125% / 150% Windows draws the window small and stretches it like a
    picture, so text and every rounded button look soft and pixelated, and positions are scaled too (pop-ups
    land in the wrong place on a second monitor). Tk then reports the real dpi and the layout follows
    (ui_factor). Returns True if it was set. Does nothing elsewhere; `windll` is for tests."""
    if windll is None:
        if os.name != "nt":
            return False
        import ctypes
        windll = ctypes.windll
    try:                                   # Windows 10 1703+: per monitor, version 2
        import ctypes
        fn = windll.user32.SetProcessDpiAwarenessContext
        fn.argtypes = [ctypes.c_ssize_t]
        if fn(-4):                         # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            return True
    except Exception:
        pass
    try:                                   # Windows 8.1+: per monitor
        if windll.shcore.SetProcessDpiAwareness(2) == 0:
            return True
    except Exception:
        pass
    try:                                   # Vista+: the whole system's dpi
        return bool(windll.user32.SetProcessDPIAware())
    except Exception:
        return False


def usable_area(root):
    """(x, y, w, h): the part of the monitor a window may occupy."""
    x, y, w, h = monitor_box(root)
    uw, uh = int(w * WIDTH_USE), int(h * HEIGHT_USE)
    return x + (w - uw) // 2, y + (h - uh) // 2, uw, uh


def is_maximized(win):
    """True while `win` is maximized: its state is "zoomed" on Windows and macOS; on Linux the window manager says
    so through the -zoomed attribute (Tk keeps it up to date; the state stays "normal" there)."""
    try:
        if win.state() == "zoomed":
            return True
    except Exception:                        # (a window being destroyed)
        return False
    try:
        return bool(int(win.attributes("-zoomed")))
    except Exception:                        # (no such attribute on Windows: its state said it already)
        return False


def fit_size(content, preferred, area):
    """Window size: the preferred size, but at least the content needs, and never bigger than `area` (w, h)."""
    return (min(max(content[0], preferred[0]), area[0]),
            min(max(content[1], preferred[1]), area[1]))


def center_geometry(w, h, area):
    """Tk geometry string putting a w x h window in the middle of `area` = (x, y, w, h)."""
    ax, ay, aw, ah = area
    x = ax + max(0, (aw - w) // 2)
    y = ay + max(0, (ah - h) // 2)
    return f"{w}x{h}+{x}+{y}"


def keep_on_screen(win):
    """After a window grew (a message shown, a row grew): move it, and if need be shrink it, so it stays on its
    monitor's usable area. A window that fits where it is is left alone (at its natural size)."""
    try:
        win.update_idletasks()
        ax, ay, aw, ah = usable_area(win)
        w, h = min(win.winfo_reqwidth(), aw), min(win.winfo_reqheight(), ah)
        x0, y0 = win.winfo_x(), win.winfo_y()
        x, y = min(max(x0, ax), ax + aw - w), min(max(y0, ay), ay + ah - h)
        if (x, y) != (x0, y0) or (w, h) != (win.winfo_reqwidth(), win.winfo_reqheight()):
            win.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        pass


def place_dialog(dlg, parent):
    """Size a dialog to its contents and centre it over `parent` (over the screen when the parent is
    hidden), kept on the screen."""
    dlg.update_idletasks()
    area = usable_area(dlg)
    w = min(dlg.winfo_reqwidth(), area[2])
    h = min(dlg.winfo_reqheight(), area[3])
    try:
        if not parent.winfo_viewable():
            raise ValueError("hidden parent")
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
    except Exception:
        px, py = area[0] + area[2] // 2, area[1] + area[3] // 2
    x = min(max(px - w // 2, area[0]), area[0] + area[2] - w)
    y = min(max(py - h // 2, area[1]), area[1] + area[3] - h)
    dlg.geometry(f"{w}x{h}+{x}+{y}")
