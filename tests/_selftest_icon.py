import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""IC-1: the program's icon (tools/make_icon.py draws it into src/icons): every size is there and square, every window
wears it (ui_style.set_icon, from apply_ttk_style), the source and a build carry it, the Windows program has the .ico
and the macOS one the .icns as its own icon, and the Linux launcher points at a copy that outlives a built program."""
import os
import tkinter as tk
import standalone as S
import ui_style
from fonts import init_fonts

# ---- the files: a PNG per size (square, that size), the .ico, the big one for the launcher
for n in ui_style.ICON_SIZES + (1024,):
    with open(os.path.join(ui_style.ICONS, f"icon-{n}.png"), "rb") as f:
        head = f.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n" and int.from_bytes(head[16:20], "big") == n == int.from_bytes(head[20:24], "big"), n
with open(os.path.join(ui_style.ICONS, "icon.ico"), "rb") as f:
    ico = f.read(6)
assert ico[:4] == b"\x00\x00\x01\x00" and int.from_bytes(ico[4:6], "little") == len(ui_style.ICON_SIZES)

# ---- on the windows: styling a root gives it every size once (a second call adds nothing)
root = tk.Tk(); root.withdraw(); init_fonts(root)
ui_style.apply_ttk_style(root)
assert [im.width() for im in root._icons] == list(ui_style.ICON_SIZES)
first = root._icons
ui_style.apply_ttk_style(root)
assert root._icons is first
# a window opened later wears it too (iconphoto's default); with the files missing nothing breaks
top = tk.Toplevel(root); top.update_idletasks(); top.destroy()
was = ui_style.ICONS
ui_style.ICONS = "/nonexistent"
other = tk.Toplevel(root)
ui_style.set_icon(other)
assert other._icons is None
ui_style.ICONS = was
root.destroy()

# ---- the source and the build carry it; only Windows' program gets the .ico as its own icon
files = {f.replace(os.sep, "/") for f in S.source_files()}
assert {f"src/icons/icon-{n}.png" for n in ui_style.ICON_SIZES} | {"src/icons/icon.ico", "src/icons/icon.icns"} <= files
for platform, ico in (("win32", "icon.ico"), ("linux", None), ("darwin", "icon.icns")):
    args = S.pyinstaller_args("dist", "work", platform=platform)
    sep = ";" if platform == "win32" else ":"
    assert f"{os.path.join(S.ROOT, 'src', 'icons')}{sep}icons" in args
    assert ("--icon" in args) == bool(ico) and (not ico or args[args.index("--icon") + 1].endswith(ico))
with open(os.path.join(ui_style.ICONS, "icon.icns"), "rb") as f:
    assert f.read(4) == b"icns"                                         # (the macOS app bundle's icon)
# Linux (reported: no icon on the built program's file on Fedora): a program file cannot carry one there, so the
# file manager's custom icon is set with gio, to a copy of the icon that stays (~/.local/share/icons)
import deps, tempfile
home = tempfile.mkdtemp()
os.environ.pop("XDG_DATA_HOME", None)
ran = []
def run(cmd, **kw):
    ran.append(cmd)
    return type("R", (), {"returncode": 0})()
assert S.give_icon("/opt/word-tierlister", platform="linux", which=lambda n: "/usr/bin/gio", run=run, home=home)
kept = os.path.join(home, ".local", "share", "icons", "word-tierlister.png")
assert ran == [["gio", "set", "/opt/word-tierlister", "metadata::custom-icon", "file://" + kept]]
assert open(kept, "rb").read() == open(deps.ICON, "rb").read()
assert not S.give_icon("/opt/x", platform="linux", which=lambda n: None, run=run, home=home)      # (no gio: nothing)
assert not S.give_icon("C:/x.exe", platform="win32", which=lambda n: "/usr/bin/gio", run=run, home=home)  # (its own)
assert len(ran) == 1
print("ICON OK")
