import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""Settings > Keyboard shortcuts (UI-48): change, add and remove keys, swap on a clash, move the placing set, and
every key, hint and menu follows at once; saved in the save."""
import os, tempfile, time, types
os.environ["HOME"] = tempfile.mkdtemp()
import tkinter as tk
import tierlist as T
import keymap as K

WORDS = [f"w{i:04d}" for i in range(200)]
db = os.path.join(tempfile.mkdtemp(), "keys.db")
s = T.Store(db); s.insert_words(WORDS); s.set_anchors(WORDS[:6])
root = tk.Tk(); app = T.App(root, s, T.Definitions(s))
app.anim.reduce_motion = True


def pump(n=6):
    for _ in range(n):
        root.update(); time.sleep(0.02)


def key(ks, state=0, to=None, handler=None):       # a press (to a widget, for Browse) and its release
    e = types.SimpleNamespace(keysym=ks, time=None, state=state, widget=to)
    r = (handler or app.on_key)(e)
    app.on_key_release(types.SimpleNamespace(keysym=ks, time=None))
    return r


pump(10)
assert "Keyboard shortcuts..." in [it[1] for it in app.header.menus["Settings"] if len(it) > 1]
d = app.edit_keys(); pump()
assert d.dlg.alive() and set(d.caps) >= {("undo", 0), ("undo", 1), ("place", 0), ("later", None)}
assert d.caps[("place", 0)].cget("text") == "1 … 6"

# change a key: click it, press the new one; the button's hint and the key itself follow at once
d.listen("later", 0); pump(2)
assert d.caps[("later", 0)].cget("text") == "…" and "Remove this key" in [
    w.cget("text") for w in d.note.winfo_children()[1:]]
d.caps[("later", 0)].event_generate("<KeyPress>", keysym="q"); pump(2)      # a real key press, caught by the keycap
assert app.keys.keys_of("later") == ["q", "question"] and d.waiting is None
assert app.later_btn.cget("hint") == "Q / ?" and K.Keymap(s.get_meta("keymap")).keys_of("later") == ["q", "question"]
before = s.next_unplaced()["word"]
key("q"); pump(2); assert s.next_unplaced()["word"] != before                  # Q sends the word to the back
key("u"); pump(1)                                                              # U does nothing now
# add a key ("+"), and a clash in the same view offers a swap
d.listen("better", None); d.press("Return")
assert d.offer and "already Same tier" in d.note_text and app.keys.keys_of("better") == ["Up", "b"]
d.swap(); pump(2)
assert app.keys.keys_of("better") == ["Up", "b", "Return"] and "Return" not in app.keys.keys_of("same")
d.listen("worse", 1); d.press("b")                                              # b is Better's: swap gives Better w
assert "Better gets W" in d.note_text; d.swap()
assert app.keys.keys_of("worse") == ["Down", "b"] and app.keys.keys_of("better") == ["Up", "w", "Return"]
assert app.cmp_btns["better"].cget("hint") == "↑ / W / Enter"
d.listen("skip", 0); d.press("u")                                               # another view's key: fine
assert app.keys.keys_of("skip") == ["u"] and not d.offer
d.listen("tie", None); d.press("Escape")                                        # every key can be changed: Escape too
assert app.keys.keys_of("tie") == ["Down", "t", "Escape"]
# the placing set moves together; a key with no five after it, and the menu keys, are refused
d.listen("place", 0); d.press("m")
assert "no five keys" in d.note_text and app.keys.keys_of("place") == list("123456")
d.press("Alt+f"); assert "File menu" in d.note_text
d.press("a"); pump(2)
assert app.keys.keys_of("place") == list("asdfgh") and d.caps[("place", 0)].cget("text") == "A … H"
assert [b.cget("hint") for b in app.tier_btns] == list("ASDFGH")
placed = s.stats()["placed"]
key("d"); pump(2)                                                               # D: now Place in C, not Definition
assert s.stats()["placed"] == placed + 1 and not app.show_defs
d.listen("place", 0); d.press("q")                                              # Q..Y holds Q (Don't know): a swap
assert d.offer and "already Don't know / later" in d.note_text and "gets A" in d.note_text
d.cancel(); assert app.keys.keys_of("place") == list("asdfgh")                   # ...turned down: nothing changed
d.listen("later", 0); d.press("a")
assert "one of the placing keys" in d.note_text and app.keys.keys_of("later") == ["q", "question"]
d.cancel()
# remove a key; Ctrl keys change too, and the menus' shortcut column follows
d.listen("undo", 0); d.remove()
assert app.keys.keys_of("undo") == ["Ctrl+z"] and app.hint_lbl.cget("text").startswith("Ctrl Z undo")
d.listen("zoom_in", 0); d.press("Ctrl+i")
assert app.keys.keys_of("zoom_in") == ["Ctrl+i", "Ctrl+equal"]
assert next(it[3] for it in app.header.menus["View"] if it[0] == "command" and it[1] == "Zoom in") == "Ctrl I"
z0 = app.zoom; key("i", 0x4); pump(2); assert app.zoom > z0; app.set_zoom(1.0)
d.listen("defs", 0); d.press("F2"); assert app.def_btn.cget("text") == "Definition (F2)"
# Browse uses the same keys: Unplace on X, but not while typing in the search box
d.listen("unplace", 0); d.press("x")
app.open_browser(); pump(6); bw = app.browsers[0]
first = next(w for w in bw.tree.get_children() if w not in app.anchors)          # (anchors are protected)
bw.tree.selection_set(first); bw.current = first; pump(2)
key("x", to=bw.entry, handler=bw._on_key); pump(2)                              # typing an x in the search box
assert s.get_word(first)["tier"] is not None
key("x", to=bw.tree, handler=bw._on_key); pump(2); assert s.get_word(first)["tier"] is None   # in the list: unplaced
bw.close()
# per row and all at once back to the defaults; and everything survives a restart
d.reset("place"); assert app.keys.keys_of("place") == list("123456")
assert ("place", 0) in d.caps and not app.keys.is_default("later")
saved = s.get_meta("keymap")
d.dlg.close(); app.on_close()
s = T.Store(db); root = tk.Tk(); app = T.App(root, s, T.Definitions(s)); app.anim.reduce_motion = True; pump(6)
assert app.keys.dumps() == saved and app.later_btn.cget("hint") == "Q / ?"
d = app.edit_keys(); pump(); d.reset_all(); pump(2)
assert s.get_meta("keymap") == "{}" and app.later_btn.cget("hint") == "U / ?" and app.def_btn.cget("text") == "Definition (D)"
d.dlg.close(); app.on_close()
print("SHORTCUTS OK")
