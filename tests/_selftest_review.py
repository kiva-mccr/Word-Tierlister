import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""The review of the flagged obscene words (python tierlist.py --review-obscene): a developer tab, only with that
option; each flagged word (commonest first, never censored) answered Not obscene / Obscene / Swear word by key or
button, Back takes an answer back, a % bar shows how far; the answers win over any later finding and can be saved
to a file next to the save."""
import os, tempfile, time, types
os.environ["HOME"] = tempfile.mkdtemp()
import tkinter as tk
import tierlist as T

WORDS = ["table", "box", "bureaucracy", "bastard", "shit"] + [f"w{i:04d}" for i in range(60)]
s = T.Store(os.path.join(tempfile.mkdtemp(), "rev.db")); s.insert_words(WORDS)
s.set_obscene(["box", "bureaucracy", "bastard", "shit"]); s.set_meta("obscene_done", s.OBSCENE_VERSION)
s.set_censor(True)

# ---- the store: answers, progress, back, and answers winning over a later finding ---------------------------
assert s.review_progress() == (0, 4) and s.review_next()["word"] == "box"          # commonest first
s.review("box", "not"); s.review("bastard", "swear")
assert s.review_progress() == (2, 2) and s.review_next()["word"] == "bureaucracy"
assert "box" not in s.obscene_words() and "bastard" in s.obscene_words()          # (a swear word counts as obscene)
s.set_obscene(["box", "bureaucracy", "bastard", "shit"], replace=True)            # found again (a later look) ...
assert "box" not in s.obscene_words()                                              # ... the answer still wins
assert s.review_back() == "bastard" and s.review_progress() == (1, 3) and "bastard" in s.obscene_words()
try:
    s.review("table", "maybe"); raise AssertionError("an unknown answer was taken")
except ValueError:
    pass
s.review_back()
assert s.review_progress() == (0, 4) and s.review_back() is None

# ---- the tab: only with the option; keys from the keymap; never censored ------------------------------------
root = tk.Tk()
s2 = T.Store(s.path)
plain = T.App(root, s2, T.Definitions(s2))
assert "review" not in plain.mode_switch.visible and plain.mode != "review"
d = plain.edit_keys(); assert "Review obscene words" not in str([w.cget("text") for w in d.dlg.body.winfo_children()
                                                                 for w in w.winfo_children() if w.winfo_class() == "Label"])
plain.on_close()
root = tk.Tk()
app = T.App(root, s, T.Definitions(s), review=True)


def pump(n=6):
    for _ in range(n):
        root.update(); time.sleep(0.02)


def key(ks, char=""):
    app.on_key(types.SimpleNamespace(keysym=ks, char=char, time=None, state=0))
    app.on_key_release(types.SimpleNamespace(keysym=ks, time=None))
    pump(2)


pump(15)
assert app.mode == "review" and "review" in app.mode_switch.visible and app.show_defs
assert s.get_meta("show_defs", "0") == "0"                                        # (your own setting is kept)
assert app.review_word == "box" and not app.review_card.censored and not app.review_card.find_withtag("find")
assert app.review_btns["review_not"].cget("hint") == "1" and app.review_btns["review_back"].cget("hint") == "Bksp"
assert "0 of 4 reviewed (0%)" == app.review_lbl.cget("text") and app.review_bar["value"] == 0
key("1", "1")                                                                     # Not obscene
assert app.review_word == "bureaucracy" and s.review_rows() == [("box", "not")]
key("2", "2"); key("3", "3")                                                      # Obscene, Swear word
assert dict(s.review_rows()) == {"box": "not", "bureaucracy": "obscene", "bastard": "swear"}
assert app.review_lbl.cget("text") == "3 of 4 reviewed (75%)" and app.review_bar["value"] == 75
key("BackSpace")                                                                  # Back: bastard again
assert app.review_word == "bastard" and len(s.review_rows()) == 2
app.review_btns["review_swear"].invoke(); app.review_btns["review_not"].invoke(); pump(2)   # (the buttons too)
assert app.review_word is None and app.review_empty.title == "Every flagged word is reviewed"
assert not app.review_btns["review_not"].enabled and app.review_btns["review_back"].enabled
path = app.save_review()
lines = open(path, encoding="utf-8").read().splitlines()
assert lines[0].startswith("#") and lines[1:] == ["box\tnot", "bureaucracy\tobscene", "bastard\tswear", "shit\tnot"], lines
assert os.path.dirname(path) == os.path.dirname(s.path)
# the review keys can be changed like any other (UI-48), and the tab is one more stop for Tab
app.keys.set("review_back", ["b"]); app.apply_keys()
assert app.review_btns["review_back"].cget("hint") == "B"
app.mode_var.set("place"); app.on_mode_change(); pump(2)
key("Tab"); assert app.mode != "place"
app.on_close()
print("REVIEW OK")
