import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""The review of Claude's sorting, meaning by meaning (OB-4; python tierlist.py --review-obscene): a developer tab,
only with that option. word_categories.tsv next to the save is loaded on start (again when it changes; answers
stay); the words to check come commonest first, each meaning with its kind, changeable by key or button; the
whole-word smear; what the answers lead to; Next word keeps them, Back takes them back, "not sure" comes back
later; the answers can be saved to a file next to the save."""
import os, tempfile, time, types
os.environ["HOME"] = tempfile.mkdtemp()
import tkinter as tk
import tierlist as T

WORDS = ["table", "freak", "freaks", "fuck", "box", "shit"] + [f"w{i:04d}" for i in range(60)]
folder = tempfile.mkdtemp()
s = T.Store(os.path.join(folder, "rev.db")); s.insert_words(WORDS)
s.set_def("freak", "• (noun) Someone markedly unusual.\n• (noun) (derogatory) An odd person.\n"
                   "• (noun) (slang) A sexually adventurous person.")
s.set_def("box", "• (noun) A container.\n• (verb) To fight with the fists.")
TSV = ("# word\tkind\tconfidence\tmeanings\tnote\tmodel\tsecond\n"
       "freak\tinsult\t75\tclean,insult,sexual\t\tm\tdouble:25\n"        # first meaning clean, word insult: check
       "freaks\tinsult\t75\t\tform of freak\tm\t\n"                     # a form: never checked itself
       "fuck\tsexual\t95\tsexual,swear\t\tm\t\n"                       # sure, and agreed: not checked
       "box\tslur\t70\tclean,clean\t\tm\t\n"                           # unsure, no second choice: check
       "shit\tswear\t60\tswear\t\tm\tcrude:40\n"                       # unsure, but either way smeared: not checked
       "nonword\tslur\t50\tslur\t\tm\t\n")                             # not in the list: not loaded

# ---- the store: loading, the words to check, answers, not sure, back, loading again --------------------------
from obscene import read_categories
path = os.path.join(folder, "word_categories.tsv")
with open(path, "w", encoding="utf-8") as f:
    f.write(TSV)
assert s.load_kinds(read_categories(path)) == 5                                    # (nonword is not in the list)
assert s.kinds_progress() == (0, 2) and s.kinds_next()["word"] == "freak"          # commonest first
assert s.kinds_of("freaks")["form_of"] == "freak" and s.kinds_of("fuck")["why"] is None
assert s.kinds_of("box")["why"] == "Claude was only 70% sure"
s.answer_kinds("freak", "insult", ["clean", "insult", "sexual"], whole=True)
assert s.kinds_progress() == (1, 2) and s.kinds_next()["word"] == "box"
s.answer_kinds("box", "clean", ["clean", "unsure"])                                # not sure: comes back last
assert s.kinds_progress() == (1, 2) and s.kinds_next()["word"] == "box" and s.kinds_of("box")["unsure"] == 1
assert s.load_kinds(read_categories(path)) == 5 and s.kinds_of("freak")["whole"] == 1   # answers stay
assert s.checked_kinds() == [("freak", "insult", ["clean", "insult", "sexual"], 1), ("box", "clean", ["clean", "unsure"], None)]
assert s.kinds_back() == "box" and s.kinds_back() == "freak" and s.kinds_back() is None
assert s.kinds_progress() == (0, 2) and s.kinds_of("freak")["meanings"] == "clean,insult,sexual"   # (as answered)
s.db.execute("DELETE FROM kinds"); s.db.commit()

# ---- the tab: only with the option; loads the file on start ------------------------------------------------
root = tk.Tk()
plain = T.App(root, T.Store(s.path), T.Definitions(s))
assert "review" not in plain.mode_switch.visible and plain.mode != "review"
assert s.kinds_progress() == (0, 0)                                                 # (not loaded without it)
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


def rows():
    return app.review_list.get("1.0", "end").strip().splitlines()


pump(15)
assert app.mode == "review" and "review" in app.mode_switch.visible
assert app.note.startswith("Loaded Claude's sorting: 5 words") and s.get_meta("kinds_file")
assert app._rv["word"] == "freak" and not app.review_card.censored and not app.review_card.find_withtag("find")
assert app.review_why.cget("text") == "Here because Claude calls the word Insult, but its first meaning is not rude"
r = rows()
assert len(r) == 3 and "noun" in r[0] and "Someone markedly unusual." in r[0] and "An odd person" in r[1], r
assert app.review_btns["review_insult"].cget("hint") == "5" and app.review_btns["review_back"].cget("hint") == "Bksp"
assert app.review_lbl.cget("text").startswith("0 of 2 checked (0%)") and app.review_bar["value"] == 0
assert not app.review_whole_v.get()                                                # first meaning clean
assert app.review_result.cget("text") == "With the usual settings: Shown; 2 of its 3 meanings smeared while censoring"
assert "choose a meaning" in app.hint_lbl.cget("text")
key("5", "5")                                                                       # meaning 1: Insult
assert app._rv["meanings"][0] == "insult" and app._rv["sel"] == 1 and app.review_whole_v.get()   # (now first is rude)
key("Up"); assert app._rv["sel"] == 0
key("1", "1"); key("Down"); key("Down"); assert app._rv["sel"] == 2                # back to clean; to meaning 3
key("Down"); assert app._rv["sel"] == 2                                             # (no further)
key("w"); assert app.review_whole_v.get() and app._rv["whole"] is True             # smear it all the same
assert app.review_result.cget("text").endswith("the whole word smeared while censoring")
app.review_select(1); pump(1); assert app._rv["sel"] == 1                         # (a click on a meaning)
key("Return")                                                                       # keep, next word
assert s.kinds_of("freak")["whole"] == 1 and s.kinds_of("freak")["meanings"] == "clean,insult,sexual"
assert app._rv["word"] == "box" and app.review_lbl.cget("text").startswith("1 of 2 checked (50%)")
assert len(rows()) == 3 and "Another use, not among these definitions" in rows()[2]   # its slur is not listed
key("Down"); key("Down"); key("8", "8")                                             # that use: not sure
app.review_btns["review_next"].invoke(); pump(2)
assert app._rv["word"] == "box" and s.kinds_of("box")["unsure"] == 1                 # it comes back (only one left)
key("BackSpace"); key("BackSpace")                                                  # back two words
assert app._rv["word"] == "freak" and app._rv["whole"] is True                     # as it was answered
app.review_btns["review_next"].invoke(); pump(2)
key("Down"); key("Down"); key("7", "7"); key("Return")                              # box: a slur after all
assert app._rv is None and app.review_empty.title == "Every word to check is checked"
assert not app.review_btns["review_next"].enabled and app.review_btns["review_back"].enabled
out = app.save_review()
lines = open(out, encoding="utf-8").read().splitlines()
assert lines[0].startswith("# word") and lines[1:] == ["freak\tinsult\tclean,insult,sexual\t1", "box\tslur\tclean,clean\t"], lines
assert os.path.dirname(out) == folder
# the review keys can be changed like any other (UI-48), and the tab is one more stop for Tab
app.keys.set("review_back", ["b"]); app.apply_keys()
assert app.review_btns["review_back"].cget("hint") == "B"
app.mode_var.set("place"); app.on_mode_change(); pump(2)
key("Tab"); assert app.mode != "place"
app.on_close()

# no sorting file: the tab says what to do
root = tk.Tk()
s3 = T.Store(os.path.join(tempfile.mkdtemp(), "none.db")); s3.insert_words(WORDS)
app = T.App(root, s3, T.Definitions(s3), review=True); pump(10)
assert app._rv is None and app.review_empty.title == "No sorting loaded"
app.on_close()
print("REVIEW OK")
