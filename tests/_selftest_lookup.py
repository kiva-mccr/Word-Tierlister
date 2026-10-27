import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""UI-51: look up any word from the word card (the magnifier, or /), type it on the card, Enter brings it up to sort
now; a placed word or one not in the list shakes the card and says so; Enter again adds a new word. W-1: a word
clicked in a definition (the drawer or Browse's pane) shows its definition there and waits in Browse, greyed at the
bottom, to be placed with the tier buttons or keys; a word not in the list is offered to add first."""
import os, tempfile, time, types
os.environ["HOME"] = tempfile.mkdtemp()
import tkinter as tk
import tierlist as T

WORDS = [f"w{i:04d}" for i in range(300)]
s = T.Store(os.path.join(tempfile.mkdtemp(), "look.db")); s.insert_words(WORDS); s.set_anchors(WORDS[:6])
root = tk.Tk(); app = T.App(root, s, T.Definitions(s))
app.anim.reduce_motion = True


def pump(n=6):
    for _ in range(n):
        root.update(); time.sleep(0.02)


def key(ks, char=""):
    app.on_key(types.SimpleNamespace(keysym=ks, char=char, time=None, state=0))
    app.on_key_release(types.SimpleNamespace(keysym=ks, time=None))


def type_word(text):
    for ch in text:
        key(ch if ch.isalnum() else "minus", ch)


pump(10)
card = app.word_card
first = app.cur_word
assert card.find_withtag("find")                                                # the magnifier, top right
x, y, size = card.find_box()
assert x > card.winfo_width() * 0.6 and y < card.winfo_height() * 0.4
assert app._card_note(types.SimpleNamespace(x=x + size / 2, y=y + size / 2)) == "Look up a word (/)"
assert app._card_note(types.SimpleNamespace(x=5, y=card.winfo_height() - 5)) is None

# "/" starts typing on the card; keys type (1 is a letter here, not "place in S"); Escape puts the word back
placed0 = s.stats()["placed"]
key("slash", "/"); assert card.typing and card.word == card.PLACEHOLDER and card.find_withtag("caret") and card.sub == card.TYPE_HINT
type_word("w1"); key("BackSpace"); type_word("12")
assert card.typed == "w12" and s.stats()["placed"] == placed0
key("Escape"); assert not card.typing and card.word == first

# an unplaced word comes up to sort now; the queue order of the rest does not change
app.start_lookup(); type_word("w0150"); key("Return"); pump(2)
assert app.cur_word == "w0150" and app.looked_up == "w0150" and "looked up" in card.sub and not card.typing
key("3"); pump(2)
assert s.get_word("w0150")["tier"] == 2 and app.cur_word == first and app.looked_up is None
# a placed word: the card says so and stays ready to type
app.start_lookup(); type_word("w0150"); key("Return")
assert card.typing and "Already placed in B" in card.sub
key("Escape")
# a word not in the list: the first Enter says so, the second adds it (at the end of the list) and brings it up
last_rank = s.db.execute("SELECT MAX(rank) FROM words").fetchone()[0]
pen_done = s.get_meta("pen_done")
app.start_lookup(); type_word("snorkelwisp"); key("Return")
assert card.typing and "Not in the word list" in card.sub and not s.has_word("snorkelwisp")
key("Return"); pump(2)
assert s.has_word("snorkelwisp") and app.cur_word == "snorkelwisp" and not card.typing
assert s.get_word("snorkelwisp")["rank"] == last_rank + 1 and s.get_meta("pen_done") == pen_done   # nothing redone
assert app.toast.cget("text") == "'snorkelwisp' added to the word list"
# Don't know / later on a looked-up word sends it back like any other, and the queue carries on
key("u"); pump(2); assert app.cur_word == first and app.looked_up is None
# the magnifier again goes back; clicking a tier pill while typing places the word on the card, not the typing
app.start_lookup(); app.start_lookup(); assert not card.typing and card.word == first
app.start_lookup(); type_word("w02"); app.tier_btns[5].invoke(); pump(2)
assert not card.typing and s.get_word(first)["tier"] == 5
# typing is dropped on a tab switch; the key can be changed like any other (UI-48)
app.start_lookup(); type_word("w0"); app.mode_var.set("refine"); app.on_mode_change(); pump(2)
assert not card.typing
app.mode_var.set("place"); app.on_mode_change(); pump(2)
app.keys.set("find", ["Ctrl+f"]); app.apply_keys()
key("slash", "/"); assert not card.typing
app.on_key(types.SimpleNamespace(keysym="f", char="\x06", time=None, state=0x4)); assert card.typing
key("Escape")
# the card shakes for "no" (with motion on), and ends where it started
app.anim.reduce_motion = False
before = card.coords("card")
app.start_lookup(); type_word("w0150"); key("Return")
moved = set()
for _ in range(10):
    root.update(); time.sleep(0.015); moved.add(card.coords("card")[0])
app.anim.finish_all(); pump(2)
assert len(moved) > 1 and card.coords("card") == before, moved               # it moved, and came back
key("Escape")
app.anim.reduce_motion = True
# found in testing (asked for): a new word typed with capitals is added in lower case, like the list, and is found
# again in lower case (it was added as "Zorp", then a second "zorp")
app.start_lookup(); type_word("Zorp"); key("Return"); key("Return"); pump(2)
assert app.cur_word == "zorp" and not s.has_word("Zorp")
app.start_lookup(); type_word("zorp"); key("Return"); pump(2)
assert not card.typing and s.db.execute("SELECT COUNT(*) FROM words WHERE lower(word)='zorp'").fetchone()[0] == 1
key("u"); pump(2)
# runs of spaces are one space, and characters that show nothing are dropped; nothing without a letter is added
from constants import typed_word
assert typed_word("  ice \u200b cream ") == "ice cream" and typed_word("\u200b") == ""
s.add_word("ice cream")
app.start_lookup(); type_word("ice"); key("space", " "); key("space", " "); type_word("cream"); key("Return"); pump(2)
assert app.cur_word == "ice cream" and not card.typing
key("u"); pump(2)
app.start_lookup(); key("x", "\U0001F600"); key("Return"); key("Return"); pump(2)
assert card.typing and "Type a word" in card.sub and not s.has_word("\U0001F600")
key("Escape")
# undoing the placement of a looked-up word brings it back onto the card (it went back to its place in the queue)
app.start_lookup(); type_word("w0200"); key("Return"); pump(2); key("2"); pump(2)
assert s.get_word("w0200")["tier"] == 1 and app.cur_word != "w0200"
app.undo(); pump(2)
assert app.cur_word == "w0200" and s.get_word("w0200")["tier"] is None and "looked up" in card.sub
key("u"); pump(2); app.undo(); pump(2); assert app.cur_word == "w0200"             # (a skip too)
key("u"); pump(2)
# Edit > Undo while typing puts the word back first (the card stayed in typing mode, the typed text hidden)
s.place(app.cur_word, 4); app.refresh(); pump(2)
app.start_lookup(); type_word("qq"); app.undo(); pump(2)
assert not card.typing and card.word == app.cur_word
# the card's label comes back after typing (Escape lost it); a refresh while typing keeps what is typed on show
s.db.execute("UPDATE words SET kinds=3"); s.db.commit(); app.refresh(); pump(2)
label = card.kind
assert label == "noun \u00b7 verb"
app.start_lookup(); type_word("ab"); app.refresh(); pump(2)
assert card.typing and card.word == "ab" and card.typed == "ab"
key("Escape"); assert card.word == app.cur_word and card.kind == label
app.on_close()

# ---- W-1: a word clicked in a definition ----------------------------------------------------------------------------
import app as A, widgets as Wd
s = T.Store(os.path.join(tempfile.mkdtemp(), "w1.db"))
s.insert_words(WORDS[:12] + ["apple", "orchard", "fruit"]); s.set_anchors(WORDS[:6]); s.set_meta("dealt_asked", "1")
s.unplace("apple")                                               # (comes up next)
root = tk.Tk(); app = T.App(root, s, T.Definitions(s)); app.anim.reduce_motion = True
app.mem_defs.update({"apple": "1. (noun) A round fruit, grown in an orchard.\n   e.g. \"an apple a day\"",
                     "orchard": "1. (noun) A garden of fruit trees.", "fruit": "1. (noun) The seed-bearing part.",
                     "zorbleflax": "1. (noun) A made-up thing."})
pump(10); app.toggle_defs(True); pump(6)
t = app.def_frame.text
def spot(text, word):
    i = text.search(word, "1.0"); x, y, _w, _h = text.bbox(i)
    return x + 2, y + 2
assert app.cur_word == "apple"
x, y = spot(t, "orchard")
assert Wd.word_at(t, x, y)[2] == "orchard" and Wd.word_at(t, *spot(t, "noun")) is None   # (a label: not a link)
hx, hy = spot(t, "apple")
assert Wd.word_at(t, hx, hy) is None                             # (the heading itself: not a link)
t.event_generate("<Motion>", x=x, y=y); pump(2)
assert t.tag_ranges("link") and t.cget("cursor") == "hand2"      # underlined under the pointer, with a hand
t.event_generate("<Button-1>", x=x, y=y); pump(3)
assert app.lookups == ["orchard"] and t.get("1.0", "2.0").startswith("Back to apple")
assert "garden of fruit trees" in t.get("1.0", "end")
bx, by = spot(t, "Back to")
t.event_generate("<Motion>", x=bx, y=by); pump(1)
assert t.cget("cursor") == "hand2"
t.event_generate("<Button-1>", x=bx, y=by); pump(3)               # (the "Back to ..." line)
assert "round fruit" in t.get("1.0", "end") and app.def_lookup is None
# in Browse: waiting at the bottom, greyed, "not placed yet"; the placing keys place it for real
app.open_browser(); pump(6)
bw = app.browsers[0]
assert bw.tree.get_children()[-1] == "orchard" and "lookup" in bw.tree.item("orchard", "tags")
assert bw.tree.item("orchard", "values")[2] == bw.NOT_PLACED
bw.tree.selection_set("orchard"); pump(2)
bw._on_key(types.SimpleNamespace(keysym="2", char="2", state=0, widget=bw.tree, keycode=0)); pump(3)
assert s.get_word("orchard")["tier"] == 1 and app.lookups == []  # placed in A, and no longer waiting
assert "lookup" not in bw.tree.item("orchard", "tags")
# clicked in Browse's own pane: its row selected and its definition there; a refresh lets it go
bt = bw.def_text
bw.look_up("fruit"); pump(3)
assert bw.tree.selection() == ("fruit",) and "seed-bearing" in bt.get("1.0", "end") and "fruit" in bw._temp
bw.reload(keep_view=True); pump(2)
assert not bw.tree.exists("fruit") and app.lookups == []         # (refreshed: it was only there for the moment)
# a word not in the list: offered to add first; "Just show it" shows only its definition
A.ask_yes_no = lambda *a, **kw: False
bw.look_up("zorbleflax"); pump(3)
assert not s.has_word("zorbleflax") and "made-up" in bt.get("1.0", "end") and not bw.tree.exists("zorbleflax")
A.ask_yes_no = lambda *a, **kw: True
bw.look_up("zorbleflax"); pump(3)
assert s.has_word("zorbleflax") and bw.tree.selection() == ("zorbleflax",)
# the word's Wiktionary page (asked for: etymology and the rest), from a small icon at the top right of the
# definition; only while Wiktionary can be reached (checked on a worker thread; the tests are always offline)
import definitions as D
opened = []
A.webbrowser.open = lambda url, new=0: opened.append(url)
drawer = app.def_frame.text
def link_shown(t):
    b = getattr(t, "_link_button", None)
    return b is not None and b.winfo_ismapped()
assert not app.online.online and not link_shown(drawer) and not link_shown(bt)          # offline: no link
app.online.online = True; app._watch_online(); pump(4)
assert link_shown(drawer) and link_shown(bt), (link_shown(drawer), link_shown(bt))
b = drawer._link_button
assert b.winfo_x() > drawer.winfo_width() * 0.7 and b.winfo_y() < 20                    # (top right)
b.event_generate("<Enter>"); b.event_generate("<ButtonRelease-1>"); pump(2)
assert opened == [D.wiktionary_url(drawer._link_word)] and opened[0].startswith("https://en.wiktionary.org/wiki/")
bt._link_button.event_generate("<ButtonRelease-1>"); pump(2)
assert opened[-1] == D.wiktionary_url(bw.showing or bw.current)
assert D.wiktionary_url("ice cream") == "https://en.wiktionary.org/wiki/ice_cream#English"
assert D.wiktionary_url("naïve") == "https://en.wiktionary.org/wiki/na%C3%AFve#English"
app.online.online = False; app._watch_online(); pump(4)
assert not link_shown(drawer) and not link_shown(bt)                                    # the connection went: gone
# the project's page from the menu bar's top right (UI-75), online or not
from constants import REPO_PAGE
gh = app.github
assert gh.winfo_ismapped() and gh.winfo_rootx() > app.root.winfo_rootx() + app.root.winfo_width() * 0.7
assert gh.winfo_rooty() < app.mode_switch.winfo_rooty()                                 # (in the menus' row)
gh.event_generate("<ButtonRelease-1>"); pump(2)
assert opened[-1] == REPO_PAGE == "https://github.com/kiva-mccr/Word-Tierlister"
# the check itself: a probe on a worker thread, again every EVERY seconds; never with WORD_TIERLISTER_OFFLINE
calls = []
o = D.Online(probe=lambda: calls.append(1) or True)
assert o.start().online is False and not calls                                          # (the tests: offline)
saved = os.environ.pop(D.OFFLINE_ENV)
o.EVERY = 0.05; o.start(); time.sleep(0.3); o.stop()
os.environ[D.OFFLINE_ENV] = saved
assert o.online is True and len(calls) >= 2
bw.close(); assert app.lookups == []
app.on_close()
print("LOOKUP OK")
