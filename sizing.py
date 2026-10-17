"""Window sizing that adapts to the screen and to the contents (used by every window).

Three questions this module answers:
    * How big is the usable screen?   usable_area(root): the monitor the pointer is on (Linux asks
      xrandr, because Tk reports all monitors as one wide screen), minus room for panels and title bars.
    * How big is "one unit" of UI?    ui_factor(root): 1.0 at the classic 96 dpi; larger on high-dpi
      screens where Tk's point-based fonts are bigger but pixel sizes written in code are not.
    * Where does a window go?         fit_size / center_geometry / place_dialog.

Layers that call this: App (main window), Browser, StartupWindow and the dialogs. Everything that
reads the screen goes through usable_area(), so tests can pretend to have a different screen.
"""
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


def monitor_box(root):
    """(x, y, w, h) of the monitor to open on: the one under the pointer, else the primary, else the screen."""
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    mons = [m for m in _xrandr_monitors(root) if m[0] + m[2] <= sw + 1 and m[1] + m[3] <= sh + 1]
    if mons:
        try:
            px, py = root.winfo_pointerxy()
        except Exception:
            px = py = -1
        for x, y, w, h, _p in mons:
            if x <= px < x + w and y <= py < y + h:
                return x, y, w, h
        for x, y, w, h, primary in mons:
            if primary:
                return x, y, w, h
        return mons[0][:4]
    if sw > 2.2 * sh:                      # several monitors reported as one very wide screen
        return 0, 0, int(sh * 16 / 9), sh
    return 0, 0, sw, sh


def usable_area(root):
    """(x, y, w, h): the part of the monitor a window may occupy."""
    x, y, w, h = monitor_box(root)
    uw, uh = int(w * WIDTH_USE), int(h * HEIGHT_USE)
    return x + (w - uw) // 2, y + (h - uh) // 2, uw, uh


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


def place_dialog(dlg, parent):
    """Size a dialog to its contents and centre it over `parent`, kept on the screen."""
    dlg.update_idletasks()
    area = usable_area(dlg)
    w = min(dlg.winfo_reqwidth(), area[2])
    h = min(dlg.winfo_reqheight(), area[3])
    try:
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
    except Exception:
        px, py = area[0] + area[2] // 2, area[1] + area[3] // 2
    x = min(max(px - w // 2, area[0]), area[0] + area[2] - w)
    y = min(max(py - h // 2, area[1]), area[1] + area[3] - h)
    dlg.geometry(f"{w}x{h}+{x}+{y}")
