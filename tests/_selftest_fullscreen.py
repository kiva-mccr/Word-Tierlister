import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""FS-2 (asked for): full screen. View > Full screen or F11 fills the screen and keeps it for the save; the four top
menus become one Menu button; Esc opens the pause menu (Esc again closes it; while comparing Esc still stops
comparing); its pages come from the top menus, with Back and a trail; a dialog opened there wears Back and the trail
in place of Cancel, and closing it is Back to the page it came from. A new look chosen there opens the menu again."""
import os, shutil, subprocess, tempfile, time, types
os.environ["HOME"] = tempfile.mkdtemp()
os.environ["USERPROFILE"] = os.environ["HOME"]
import tkinter as tk
import tierlist as T
import app as A
import keymap
import theme
from fonts import init_fonts
from fullscreen import PauseMenu, backdrop_colour, key_names
from theme import PALETTE
from ui_style import apply_ttk_style
from widgets import DropMenu, StyledDialog
DropMenu_labels = DropMenu.labels

# ---- the keys
km = keymap.Keymap()
assert km.lookup("place", "F11") == "full_screen" and km.lookup("place", "Escape") == "menu"
assert km.lookup("compare", "Escape") == "stop"                        # (comparing: Esc still stops it first)
assert key_names("Escape", "BackSpace") == "Esc / Backspace"

s = T.Store(os.path.join(tempfile.mkdtemp(), "fs.db"))
words = [f"w{i:03d}" for i in range(40)]
s.insert_words(words); s.set_anchors(words[:6]); s.set_meta("dealt_asked", "1")


def new_root():
    r = tk.Tk(); r.withdraw(); init_fonts(r); apply_ttk_style(r)
    return r


def pump(root, n=6):
    for _ in range(n):
        root.update(); time.sleep(0.02)


def key(app, ks):
    app.on_key(types.SimpleNamespace(keysym=ks, char="", time=None, state=0))
    app.on_key_release(types.SimpleNamespace(keysym=ks, time=None))
    pump(app.root, 3)


def press(widget, ks):
    top = widget.winfo_toplevel()
    widget.event_generate(f"<KeyPress-{ks}>"); pump(top, 3)


A.apply_look(s)
root = new_root(); root.geometry("1000x700+0+0")
# X11 honours full screen only through a window manager: openbox here when it is installed (Windows and macOS have one)
x11 = root.tk.call("tk", "windowingsystem") == "x11"
wm = subprocess.Popen(["openbox"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) \
    if x11 and shutil.which("openbox") else None
time.sleep(1.0 if wm else 0)
CHECK_WM = wm is not None or not x11


def full_attr(r):
    return int(r.attributes("-fullscreen")) if CHECK_WM else None
app = A.App(root, s, T.Definitions(s)); app.open_window(); pump(root, 10)
assert "Full screen" in DropMenu_labels(dict(app._menu_items())["View"])
key(app, "Escape")                                                    # (not in full screen: Esc does nothing)
assert app.pause is None and not app.menu_btn.winfo_ismapped()
# ---- F11: full screen, kept in the save; the Menu button in place of the four menus; "Esc menu" in the hint
key(app, "F11")
pump(root)
assert app.full_var.get() and s.get_meta("full_screen") == "1" and full_attr(root) in (1, None)
assert app.menu_btn.winfo_ismapped() and not app.header.winfo_ismapped()
assert app.hint_lbl.cget("text").startswith("Esc menu"), app.hint_lbl.cget("text")
# ---- Esc: the pause menu over the whole window, its first page; keys stay in it
key(app, "Escape")
pm = app.pause
assert pm is not None and pm.is_open() and pm.trail() == ["Menu"]
c = pm.canvas
assert c.winfo_width() == root.winfo_width() and c.cget("bg") == backdrop_colour()
labels = [r[1] for r in pm.pages["Menu"] if r[0] != "gap"]
assert labels == ["Resume", "File", "Edit", "View", "Settings", "Leave full screen", "Quit"], labels
assert pm.sel["Menu"] == 0                                            # (Resume lit to start with)
press(c, "Down"); press(c, "Down"); press(c, "Down"); press(c, "Down")
assert pm.pages["Menu"][pm.sel["Menu"]][1] == "Settings"
press(c, "Return"); app.anim.finish_all(); pump(root)
assert pm.trail() == ["Menu", "Settings"] and pm._back_box is not None
rows = pm.pages["Settings"]
assert [r[1] for r in rows if r[0] != "gap"][:4] == ["Anchor words...", "How words are dealt...",
                                                       "Keyboard shortcuts...", "Tier colours..."]
# a switch flips in place, the page stays
i = [r[1:2] and r[1] for r in rows].index("Always compare new words to anchors")
was = app.auto_var.get(); pm.activate(i); pump(root)
assert app.auto_var.get() != was and pm.trail() == ["Menu", "Settings"]
pm.activate(i); pump(root)
# Back (the button), then the arrows again: the row of the page just left is lit
x1, y1, x2, y2 = pm._back_box
c.event_generate("<ButtonRelease-1>", x=(x1 + x2) // 2, y=(y1 + y2) // 2); app.anim.finish_all(); pump(root)
assert pm.trail() == ["Menu"] and pm.pages["Menu"][pm.sel["Menu"]][1] == "Settings"
press(c, "Right"); app.anim.finish_all(); pump(root)                 # (Right opens a page too)
assert pm.trail() == ["Menu", "Settings"]
# ---- a dialog from a page: Back and the trail at its top, no Cancel, no repeated headline; Esc is Back to the page
made = []
real = A.TierColoursDialog
class Recorded(real):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); made.append(self)
A.TierColoursDialog = Recorded
pm.activate([r[1:2] and r[1] for r in rows].index("Tier colours...")); pump(root, 8)
dlg = made[-1].dlg
texts = []
stack = [dlg.win]
while stack:
    w = stack.pop(); stack.extend(w.winfo_children())
    if isinstance(w, tk.Label) and w.winfo_ismapped():
        texts.append(w.cget("text"))
assert "Tier colours" in texts and any("Settings" in t for t in texts), texts
assert texts.count("Tier colours") == 1                              # (the headline that repeated it is gone)
assert not dlg.buttons["Cancel"].winfo_ismapped() and dlg.buttons["Apply"].winfo_ismapped()
if root.tk.call("tk", "windowingsystem") != "aqua":
    assert int(dlg.win.overrideredirect() or 0) == 1                  # (no title bar: a card with a lilac edge)
dlg.win.event_generate("<Escape>"); pump(root, 8)
assert not dlg.alive() and pm.is_open() and pm.trail() == ["Menu", "Settings"]
assert str(root.focus_get()) == str(pm.canvas)                       # (the arrows work in the menu again)
A.TierColoursDialog = real
# ---- Esc: back a page, then out of the menu (asked for: "until you hit Escape again")
press(c, "Escape"); app.anim.finish_all()
assert pm.trail() == ["Menu"]
press(c, "Escape")
assert not pm.is_open()
# Resume closes it too; the Menu button opens it
app.menu_btn.invoke(); pump(root)
assert app.pause.is_open()
app.pause.activate(0); pump(root)
assert not app.pause.is_open()
# ---- while comparing, Esc stops comparing (the menu only opens after)
app.start_compare(); pump(root)
assert app.cmp
key(app, "Escape")
assert not app.cmp and (app.pause is None or not app.pause.is_open())
key(app, "Escape")
assert app.pause.is_open()
# ---- F11 inside the menu: leaves full screen, the menu goes, the four menus come back
press(app.pause.canvas, "F11")
assert not app.full_var.get() and not app.pause.is_open() and s.get_meta("full_screen") == "0"
assert full_attr(root) in (0, None)
pump(root)
assert app.header.winfo_ismapped() and not app.menu_btn.winfo_ismapped() and StyledDialog.decorate is None
# a plain dialog outside full screen has no Back bar
d2 = StyledDialog(root, "x", "Plain"); d2.button("Cancel", d2.close); d2.show(); pump(root)
assert d2.buttons["Cancel"].winfo_ismapped()
d2.close(); pump(root)
# ---- a new look chosen in the pause menu (Dark mode): the window rebuilds in place, full screen, the menu on its page
key(app, "F11"); key(app, "Escape")
app.pause.go("View"); pump(root)
results = {}
real_open = A.App.open_window
def open_and_check(self):
    real_open(self)
    def check():
        results["full"] = full_attr(self.root) if CHECK_WM else 1
        results["trail"] = self.pause.trail() if self.pause is not None and self.pause.is_open() else None
        results["bg"] = PALETTE["bg"]
        self.on_close()
    self.root.after(self.SETTLE_MS + 700, check)
A.App.open_window = open_and_check
dark = [r for r in app.pause.pages["View"] if r[1:2] == ("Dark mode",)]
app.pause.activate(app.pause.pages["View"].index(dark[0]))
root.mainloop()
last = A.reopen_while_asked(app, s, app.defs, new_root)
A.App.open_window = real_open
assert results == {"full": 1, "trail": ["Menu", "View"], "bg": theme.DARK["bg"]}, results

# ---- PauseMenu on its own: gaps are skipped by the arrows, Back on the first page closes it
r = new_root(); r.geometry("600x500"); r.deiconify()
done, ran = [], []
pm = PauseMenu(r, {"Top": [("command", "One", lambda: ran.append(1)), ("gap",), ("page", "Sub", "Sub")],
                   "Sub": [("command", "Two", lambda: ran.append(2))]}, on_close=lambda: done.append(1))
pm.open(); pump(r)
press(pm.canvas, "Down"); assert pm.sel["Top"] == 2               # (over the gap)
press(pm.canvas, "Down"); assert pm.sel["Top"] == 0               # (wrapping round)
press(pm.canvas, "Return"); assert ran == [1] and pm.is_open()   # (a command: the menu stays)
pm.open(["Sub"]); pump(r); assert pm.trail() == ["Top", "Sub"]   # (straight onto a page)
press(pm.canvas, "BackSpace"); assert pm.trail() == ["Top"]
press(pm.canvas, "Left"); assert not pm.is_open() and done == [1]
r.destroy()
if wm:
    wm.terminate()
print("FULLSCREEN OK" + ("" if CHECK_WM else " (no openbox: full screen itself not checked)"))
