import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""FS-1 (asked for): closing a pop-up opened from a header menu brings that menu back, the item it came from lit; an
item that opens nothing (Undo, a tick) closes the menu as before. In the real window too: Settings > Tier colours."""
import os, tempfile, types
os.environ["HOME"] = tempfile.mkdtemp()
os.environ["USERPROFILE"] = os.environ["HOME"]
import tkinter as tk
import tierlist as T
import app as A
from ui_style import apply_ttk_style
from fonts import init_fonts, load_typefaces
from theme import PALETTE
from widgets import HeaderMenus, StyledDialog

load_typefaces()
root = tk.Tk(); root.geometry("600x400+0+0"); init_fonts(root)


def update(n=4):
    for _ in range(n):
        root.update()


def lit(drop):
    return [it[1] for row, _parts, it in drop._rows if row.cget("bg") == PALETTE["select_bg"]]


ran, dialogs = [], []
def open_dialog(wait=False):
    d = StyledDialog(root, "t", "A dialog")
    d.button("OK", d.close, default=True)
    dialogs.append(d)
    if wait:
        root.after(50, d.close)
    d.show(wait=wait)


items = [("command", "Undo", lambda: ran.append("undo"), None),
         ("command", "Colours...", open_dialog, None),
         ("command", "Asks...", lambda: open_dialog(wait=True), None)]
hm = HeaderMenus(root, [("Settings", items), ("Edit", items[:1])]); hm.pack(); update()
drop = hm.drops["Settings"]

# nothing opened: the menu stays closed
hm.open_menu("Settings"); update(); drop.invoke(0); update()
assert ran == ["undo"] and hm.open_name is None and hm.returning is None
# a dialog: the menu waits while it is open, then comes back with the item lit (Escape closes it as well)
hm.open_menu("Settings"); update(); drop.invoke(1); update()
assert hm.open_name is None and hm.returning == ("Settings", "Colours...") and dialogs[-1].alive()
dialogs[-1].win.event_generate("<Escape>"); update(6)
assert hm.open_name == "Settings" and lit(drop) == ["Colours..."]
assert hm.returning is None
hm.close(); update()
# a dialog that waited (closed before the item returned): the menu is back at once
hm.open_menu("Settings"); update(); drop.invoke(2); update(6)
assert hm.open_name == "Settings" and lit(drop) == ["Asks..."]
hm.close(); update()
# another menu opened meanwhile: that one wins, nothing comes back over it
hm.open_menu("Settings"); update(); drop.invoke(1); update()
hm.open_menu("Edit"); update(); dialogs[-1].close(); update(6)
assert hm.open_name == "Edit"
hm.close(); update()
# the window being rebuilt in a new look: nothing opens here, `returning` stays for the new window (App.take_over)
hm.can_return = lambda: False
hm.open_menu("Settings"); update(); drop.invoke(1); update(); dialogs[-1].close(); update(6)
assert hm.open_name is None and hm.returning == ("Settings", "Colours...")
hm.can_return = lambda: True
# a second dialog still open over the window: the menu does not open behind it
hm.open_menu("Settings"); update(); drop.invoke(1); update()
first = dialogs[-1]; open_dialog(); first.close(); update(6)
assert hm.open_name is None
dialogs[-1].close(); update()
for job in root.tk.splitlist(root.tk.call("after", "info")):       # (timers left would fire into a gone root)
    root.tk.call("after", "cancel", job)
root.destroy()

# ---- the real window: Settings > Tier colours, then Cancel
s = T.Store(os.path.join(tempfile.mkdtemp(), "s.db"))
words = [f"w{i:03d}" for i in range(40)]
s.insert_words(words); s.set_anchors(words[:6])
made = []
class Recorded(A.TierColoursDialog):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); made.append(self)
A.TierColoursDialog = Recorded
root = tk.Tk(); root.withdraw(); root.geometry("1200x800+0+0")
app = T.App(root, s, T.Definitions(s)); app.open_window(); update(20)
app.header.open_menu("Settings"); update()
drop = app.header.drops["Settings"]
i = [it[1] for _r, _p, it in drop._rows].index("Tier colours...")
drop.invoke(i); update(6)
assert app.header.open_name is None and StyledDialog.last is not None and StyledDialog.last.alive()
StyledDialog.last.win.event_generate("<Escape>"); update(8)
assert app.header.open_name == "Settings" and lit(drop) == ["Tier colours..."]
app.on_key(types.SimpleNamespace(keysym="Escape", char="", time=None, state=0)); update()
assert app.header.open_name is None
# Apply with new colours rebuilds the window in them (App.reopen): the new window brings the Settings menu back
app.header.open_menu("Settings"); update(); drop.invoke(i); update(6)
tc = made[-1]
tc.colors = ["#FFC0CB"] + list(tc.colors[1:]); tc.apply()
root.mainloop()                                                    # (until it quits to reopen)
assert app.reopening and app.header.open_name is None            # (not on the window that is going)
real_open, seen = A.App.open_window, {}
def open_and_check(self):
    real_open(self)
    def check():
        seen["open"], seen["lit"] = self.header.open_name, lit(self.header.drops["Settings"])
        self.on_close()
    self.root.after(self.SETTLE_MS + 600, check)
A.App.open_window = open_and_check
def new_root():
    r = tk.Tk(); r.withdraw(); init_fonts(r); apply_ttk_style(r)
    return r
A.reopen_while_asked(app, s, app.defs, new_root)
A.App.open_window = real_open
assert seen == {"open": "Settings", "lit": ["Tier colours..."]}, seen
print("BACKMENU OK")
