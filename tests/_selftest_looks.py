import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""UI-61, UI-62: the tier colours (Settings > Tier colours...: H / S / V bars, a hex code, reset) and dark mode (View >
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
assert theme.TIER_ROW_TEXT[0] == theme.DARK["text"] and theme.TIER_COLORS == list(theme.DUSK_TIERS)   # (Dusk, UI-77)
assert theme.default_tiers() == theme.DUSK_TIERS and theme.default_tiers(dark=False) == theme.DEFAULT_TIERS
assert theme.ink_on(theme.TIER_COLORS[2]) == theme.TIER_TEXT          # (dark ink on a pastel, dark mode too)
assert theme.ink_on(theme.PALETTE["surface"]) == theme.DARK["text"]
theme.apply(dark=False, tiers=["#112233"] * 6)
assert theme.TIER_COLORS == ["#112233"] * 6 and theme.PALETTE["bg"] == theme.LIGHT["bg"]
theme.apply(tiers=["nonsense"] * 6)
assert theme.TIER_COLORS == list(theme.DEFAULT_TIERS) and theme.default_tiers() == theme.DEFAULT_TIERS   # (not colours)
assert theme.is_hex("#FFB3C1") and not theme.is_hex("FFB3C1") and not theme.is_hex("#FFB3C")
# ---- contrast (UI-76): main and muted text about 7:1 or better on the page and on cards, in both looks; the dark ink
# (a tier pill's letter and its key) at least WCAG's 4.5:1 on every tier colour there is
assert round(theme.contrast("#000000", "#FFFFFF"), 1) == 21.0 and theme.contrast("#777777", "#777777") == 1
for look in (theme.LIGHT, theme.DARK):
    for back in (look["bg"], look["surface"]):
        assert theme.contrast(look["text"], back) >= 7 and theme.contrast(look["muted"], back) >= 6.9, (look, back)
assert min(theme.contrast(theme.TIER_TEXT, c) for c in theme.DEFAULT_TIERS + theme.DUSK_TIERS) >= 4.5

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
# Tier colours (UI-80): click a tier, then its H / S / V bars or a hex code; the bars and the code follow each other
import tiercolours
dlg = app.edit_tier_colours(); pump(root)
assert dlg.current == 0 and dlg.var.get() == theme.DEFAULT_TIERS[0]
assert dlg.pills.itemcget("ring0", "outline") and not dlg.pills.itemcget("ring1", "outline")   # (S wears the ring)
x4 = 5 + 4 * (dlg._pill_w + dlg._gap)                                # (a click anywhere on a pill picks it, not only its letter)
assert [dlg.tier_at(x4 + 2), dlg.tier_at(x4 + dlg._pill_w - 2), dlg.tier_at(x4 - 3)] == [4, 4, 4]
assert dlg.tier_at(0) == 0 and dlg.tier_at(10 ** 4) == 5
dlg.pills.event_generate("<Button-1>", x=x4 + 2, y=7); pump(root)
assert dlg.current == 4
assert dlg.var.get() == theme.DEFAULT_TIERS[4] and dlg.pills.itemcget("ring4", "outline")
assert not dlg.pills.itemcget("ring0", "outline")
_h, s_, v = dlg.hsv[4]
dlg.drag(0, dlg._knob // 2 + 1 + dlg._bar_w * 0.5); pump(root)        # (H to the middle: cyan, S and V kept)
assert abs(dlg.hsv[4][0] - 0.5) < 0.01 and dlg.hsv[4][1:] == [s_, v]
assert dlg.var.get() == dlg.colors[4] == tiercolours.to_hex(dlg.hsv[4])          # (the code follows the bars)
assert dlg.pills.itemcget("pill4", "fill") == dlg.colors[4]
assert dlg.readings[0].cget("text") == "180°"
dlg.var.set("ABCDEF"); pump(root)                                    # (typed, the # left out: the bars follow)
assert dlg.colors[4] == "#ABCDEF" and dlg.var.get() == "ABCDEF"      # (what is being typed is left alone)
assert tiercolours.to_hex(dlg.hsv[4]) == "#ABCDEF" and dlg.apply_button._enabled
dlg.var.set("#12"); pump(root)                                       # (not a colour: it says so, Apply waits)
assert "#RRGGBB" in dlg.note.cget("text") and not dlg.apply_button._enabled and dlg.colors[4] == "#ABCDEF"
hue_sat = dlg.hsv[4][:2]
dlg.drag(2, 0); pump(root)                                           # (V to 0: black, the hue and saturation kept)
assert dlg.colors[4] == "#000000" and dlg.var.get() == "#000000" and dlg.hsv[4][:2] == hue_sat
assert "Too dark" in dlg.note.cget("text") and "D" in dlg.note.cget("text") and not dlg.apply_button._enabled
dlg.apply(); pump(root)
assert dlg.dlg.alive() and not app.reopening                         # (too dark: Apply waits)
dlg.var.set("#000000"); dlg.var.set("#808080"); pump(root)            # (a grey keeps the hue it had)
assert dlg.hsv[4][0] == hue_sat[0] and dlg.colors[4] == "#808080"
dlg.reset(); pump(root)
assert dlg.colors == list(theme.DEFAULT_TIERS) and not dlg.note.cget("text") and dlg.apply_button._enabled
dlg.apply(); pump(root)                                               # (nothing changed: closes, no reopening)
assert not dlg.dlg.alive() and not app.reopening
assert tiercolours.too_dark("#696145") and not any(tiercolours.too_dark(c) for c in theme.DEFAULT_TIERS + theme.DUSK_TIERS)
assert tiercolours.to_hsv("#808080", [0.25, 0.5, 0.9])[0] == 0.25 and tiercolours.to_hsv("#000000", [0.25, 0.5, 0.9])[:2] == [0.25, 0.5]
# applying new colours: saved, the window reopens in them (the save stays open), and the pills wear them
PICK = "#A9DDF5"
dlg = app.edit_tier_colours(); pump(root)
dlg.var.set(PICK)


def check_reopened():
    """In the reopened window: S is the colour picked; then turn on dark mode, which reopens again."""
    app2 = tk._default_root._app
    results["geometry"] = app2.root.geometry()
    results["browse"] = any(b.alive() for b in app2.browsers)
    try:
        results["first_gone"] = not first_root.winfo_exists()
    except tk.TclError:                               # (its interpreter is gone: destroyed)
        results["first_gone"] = True
    assert theme.TIER_COLORS[0] == PICK and theme.PALETTE["bg"] == theme.LIGHT["bg"]
    assert app2.tier_row.buttons[0]._fill == PICK
    app2.dark_var.set(True); app2.toggle_dark()


A.App._orig_init = A.App.__init__
def init_and_mark(self, root, *a, **kw):
    if "old_up" not in results:                     # (the first reopen: the old window is still on screen)
        results["old_up"] = first_root.winfo_exists() and first_root.winfo_viewable()
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
    results["key_ink"] = app3.tier_row.buttons[2].itemcget("hint", "fill")
    app3.dark_var.set(False); app3.toggle_dark()


def check_light_again():
    root4 = tk._default_root
    results["light_bg"] = root4.cget("bg")
    results["meta"] = (s.get_meta("dark_mode"), json.loads(s.get_meta("tier_colors"))[0])
    root4._app.on_close()


A._steps = [check_reopened, check_dark, check_light_again]
first_root = root
root.geometry("1020x720+37+41"); app.open_browser(); pump(root, 8)
dlg.apply()
root.mainloop()                                                       # (the first window, until it reopens)
assert app.reopening and s.get_meta("tier_colors") == json.dumps(dlg.colors)
last = A.reopen_while_asked(app, s, app.defs, new_root)
assert results["dark_bg"] == theme.DARK["bg"] and results["store_open"] == "1", results
assert results["pill_ink"] == theme.TIER_TEXT                          # (a tier pill keeps the dark ink)
assert results["key_ink"].upper() == theme.TIER_TEXT                  # (its key too, UI-76: paler, it failed WCAG)
assert results["light_bg"] == theme.LIGHT["bg"] and not last.reopening
assert results["meta"] == ("0", PICK)
# asked for (closing and opening again was jarring): the new window is built while the old one is still on screen,
# takes its place and size and its Browse window, and only then does the old one close
assert results["old_up"] and results["first_gone"] and results["browse"], results
assert results["geometry"] == "1020x720+37+41", results["geometry"]
print("LOOKS OK")
