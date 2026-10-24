import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""UI-61, UI-62: the tier colours (Settings > Tier colours...: swatches, a #RRGGBB field, reset) and dark mode (View >
Dark mode, not the default). Both are kept in the save and shown by reopening the window with the save still open
(App.reopen, app.reopen_while_asked): everything reads the palette when it is drawn."""
import json, os, tempfile, time
os.environ["HOME"] = tempfile.mkdtemp()
import tkinter as tk
import tierlist as T
import theme
import app as A
from fonts import init_fonts
from ui_style import apply_ttk_style

# ---- the palettes: the dark one has every role the light one has; apply() changes them in place
assert set(theme.DARK) == set(theme.LIGHT) and theme.PALETTE == theme.LIGHT
colors, rows = theme.TIER_COLORS, theme.TIER_ROW
theme.apply(dark=True)
assert theme.PALETTE["bg"] == theme.DARK["bg"] and theme.TIER_COLORS is colors and theme.TIER_ROW is rows
assert theme.TIER_ROW_TEXT[0] == theme.DARK["text"] and theme.TIER_COLORS == list(theme.DEFAULT_TIERS)
assert theme.ink_on(theme.TIER_COLORS[2]) == theme.TIER_TEXT          # (dark ink on a pastel, dark mode too)
assert theme.ink_on(theme.PALETTE["surface"]) == theme.DARK["text"]
theme.apply(dark=False, tiers=["#112233"] * 6)
assert theme.TIER_COLORS == ["#112233"] * 6 and theme.PALETTE["bg"] == theme.LIGHT["bg"]
theme.apply(tiers=["nonsense"] * 6)
assert theme.TIER_COLORS == list(theme.DEFAULT_TIERS)                 # (not colours: the defaults)
assert theme.is_hex("#FFB3C1") and not theme.is_hex("FFB3C1") and not theme.is_hex("#FFB3C")
assert all(theme.is_light(c) for c in theme.SWATCHES)                 # (every swatch takes the dark ink)

# ---- the window, in a save
s = T.Store(os.path.join(tempfile.mkdtemp(), "looks.db"))
w = [f"w{i:03d}" for i in range(40)]
s.insert_words(w); s.set_anchors(w[:6]); s.set_meta("dealt_asked", "1")


def new_root():
    r = tk.Tk(); r.withdraw(); init_fonts(r); apply_ttk_style(r)
    return r


def pump(root, n=6):
    for _ in range(n):
        root.update(); time.sleep(0.02)


A.apply_look(s)
root = new_root()
app = A.App(root, s, T.Definitions(s))
app.open_window(); pump(root, 10)
labels = [it[1] for it in dict(app._menu_items())["View"] if it[0] == "check"]
assert "Dark mode" in labels and "Tier colours..." in [it[1] for it in dict(app._menu_items())["Settings"]
                                                     if it[0] == "command"]
# Tier colours: a swatch recolours its tier's pill and field; typing a colour does too; reset puts the defaults back
dlg = app.edit_tier_colours(); pump(root)
dlg.pick(0, theme.SWATCHES[8]); pump(root)
assert dlg.vars[0].get() == theme.SWATCHES[8] and dlg.chips[0]._color == theme.SWATCHES[8]
assert dlg.strips[0].find_withtag("ring")                              # (the chosen swatch marked)
dlg.vars[1].set("#ABCDEF"); pump(root)
assert dlg.colors[1] == "#ABCDEF" and not dlg.strips[1].find_withtag("ring")      # (typed: no swatch marked)
dlg.vars[2].set("#12"); dlg.apply(); pump(root)
assert dlg.dlg.alive() and "#RRGGBB" in dlg.note.cget("text") and not app.reopening     # (not a colour: it says so)
dlg.reset(); pump(root)
assert dlg.colors == list(theme.DEFAULT_TIERS)
dlg.apply(); pump(root)                                               # (nothing changed: closes, no reopening)
assert not dlg.dlg.alive() and not app.reopening
# applying new colours: saved, the window reopens in them (the save stays open), and the pills wear them
dlg = app.edit_tier_colours(); pump(root)
dlg.pick(0, theme.SWATCHES[8])


def check_reopened():
    """In the reopened window: S is the colour picked; then turn on dark mode, which reopens again."""
    app2 = tk._default_root._app
    assert theme.TIER_COLORS[0] == theme.SWATCHES[8] and theme.PALETTE["bg"] == theme.LIGHT["bg"]
    assert app2.tier_row.buttons[0]._fill == theme.SWATCHES[8]
    app2.dark_var.set(True); app2.toggle_dark()


A.App._orig_init = A.App.__init__
def init_and_mark(self, root, *a, **kw):
    A.App._orig_init(self, root, *a, **kw)
    root._app = self
    steps = getattr(A, "_steps", [])
    if steps:
        root.after(300, steps.pop(0))
A.App.__init__ = init_and_mark
results = {}


def check_dark():
    root3 = tk._default_root
    app3 = root3._app
    results["dark_bg"] = root3.cget("bg")
    results["store_open"] = app3.store.get_meta("dark_mode")
    results["pill_ink"] = app3.tier_row.buttons[2].cget("fg")
    app3.dark_var.set(False); app3.toggle_dark()


def check_light_again():
    root4 = tk._default_root
    results["light_bg"] = root4.cget("bg")
    results["meta"] = (s.get_meta("dark_mode"), json.loads(s.get_meta("tier_colors"))[0])
    root4._app.on_close()


A._steps = [check_reopened, check_dark, check_light_again]
dlg.apply()
root.mainloop()                                                       # (the first window, until it reopens)
assert app.reopening and s.get_meta("tier_colors") == json.dumps(dlg.colors)
last = A.reopen_while_asked(app, s, app.defs, new_root)
assert results["dark_bg"] == theme.DARK["bg"] and results["store_open"] == "1", results
assert results["pill_ink"] == theme.TIER_TEXT                          # (a tier pill keeps the dark ink)
assert results["light_bg"] == theme.LIGHT["bg"] and not last.reopening
assert results["meta"] == ("0", theme.SWATCHES[8])
print("LOOKS OK")
