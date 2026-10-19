import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""UI-51: look up any word from the word card (the magnifier, or /), type it on the card, Enter brings it up to sort
now; a placed word or one not in the list shakes the card and says so; Enter again adds a new word."""
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
app.on_close()
print("LOOKUP OK")
