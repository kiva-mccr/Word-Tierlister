import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""The review of rude meanings by hand (OB-9: --review-rude): the rules' guesses filled in, keys from the keymap,
answers saved after every word beside the review file, Back, starting again where it stopped, and its keys shown
in Keyboard shortcuts only while it is open."""
import json, os, tempfile, time, types
os.environ["HOME"] = tempfile.mkdtemp()
os.environ["USERPROFILE"] = os.environ["HOME"]           # (Windows reads home from USERPROFILE)
import tkinter as tk
import tierlist as T
import review as R
from constants import review_answers_path

WORDS = [f"w{i:04d}" for i in range(60)]
folder = tempfile.mkdtemp()
s = T.Store(os.path.join(folder, "review.db")); s.insert_words(WORDS); s.set_anchors(WORDS[:6])
path = os.path.join(folder, "rude_review.jsonl")
ITEMS = [
    {"w": "tail", "why": "the rules say clinical", "whole": False, "senses": [
        {"key": "The appendage at the back of an animal", "pos": "noun", "labels": [],
         "gloss": "The appendage at the back of an animal.", "guess": "clinical"},
        {"key": "The buttocks.", "pos": "noun", "labels": ["slang"], "gloss": "The buttocks.", "guess": "crude"},
        {"key": "Sexual intercourse.", "pos": "noun", "labels": ["vulgar", "slang"], "gloss": "Sexual intercourse.",
         "guess": "sexual"}]},
    {"w": "idiot", "why": "the rules say insult", "whole": False, "senses": [
        {"key": "A person of low intelligence.", "pos": "noun", "labels": ["offensive"],
         "gloss": "A person of low intelligence.", "guess": "insult"}]},
    {"w": "shitload", "why": "the rules say swear", "whole": True, "senses": [
        {"key": "A large amount.", "pos": "noun", "labels": ["vulgar"], "gloss": "A large amount.", "guess": "swear"}]},
]
with open(path, "w", encoding="utf-8") as f:
    f.write("not json\n")                                  # (skipped)
    for it in ITEMS:
        f.write(json.dumps(it) + "\n")
answers = review_answers_path(path)
assert answers.endswith("rude_review_answers.jsonl")

root = tk.Tk(); app = T.App(root, s, T.Definitions(s))
app.anim.reduce_motion = True


def pump(n=6):
    for _ in range(n):
        root.update(); time.sleep(0.02)


def key(rv, ks):
    return rv.on_key(types.SimpleNamespace(keysym=ks, state=0, keycode=None))


def saved():
    with open(answers, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


pump(6)
rv = app.open_review(path); pump(4)
assert rv.alive() and app.review is rv and len(rv.items) == 3 and rv.item["w"] == "tail"
assert rv.word.cget("text") == "tail" and len(rv.row_parts) == 3
assert rv.kinds == ["clinical", "crude", "sexual"] and rv.whole is False          # the rules' guesses
assert rv.kind_btns["clean"].cget("hint") == "1" and rv.next_btn.cget("hint") == "Enter"
assert "0 of 3" in rv.count.cget("text")
# 1 sets the first meaning Clean, which stays selected (its button lit, as its tag says); Down / Up move; S toggles
assert key(rv, "1") == "break" and rv.kinds[0] == "clean" and rv.sel == 0
lit = [k for k, b in rv.kind_btns.items() if b.cget("bg") != T.PALETTE["surface"]]
assert lit == ["clean"] and rv.row_parts[0][2].cget("text") == "Clean"
key(rv, "Down"); key(rv, "Down"); assert rv.sel == 2
key(rv, "Down"); assert rv.sel == 2                       # (stays on the last)
key(rv, "Up"); key(rv, "3"); assert rv.kinds[1] == "crude" and rv.sel == 1
key(rv, "s"); assert rv.whole is True and "yes" in rv.whole_btn.cget("text")
assert key(rv, "x") is None                               # a key of no review action passes
rv.select(0); pump(1); assert rv.sel == 0                 # (a click on a meaning)
key(rv, "Return"); pump(2)
assert rv.item["w"] == "idiot" and saved() == [{"w": "tail", "keys": [x["key"] for x in ITEMS[0]["senses"]],
                                                 "kinds": ["clean", "crude", "sexual"], "whole": True}]
assert "1 of 3" in rv.count.cget("text")
key(rv, "Return"); pump(2)                                # Enter accepts the guesses as they are
assert rv.item["w"] == "shitload" and saved()[1]["kinds"] == ["insult"]
# Back: the last word, as it was answered; answering it again replaces its answer
key(rv, "BackSpace"); pump(2)
assert rv.item["w"] == "idiot" and rv.kinds == ["insult"]
key(rv, "5"); key(rv, "6"); assert rv.kinds == ["sexual"]
key(rv, "Return"); pump(2)
assert rv.item["w"] == "shitload" and [a["w"] for a in saved()] == ["tail", "idiot"]
assert saved()[1]["kinds"] == ["sexual"]
# the keys follow the keymap: a changed key shows on its button and works
app.keys.set("review_whole", ["w"]); app.apply_keys(); pump(1)
assert rv.whole_btn.cget("hint") == "W" and rv.whole is True
key(rv, "s"); assert rv.whole is True
key(rv, "w"); assert rv.whole is False
# Keyboard shortcuts shows the review's keys while it is open
d = app.edit_keys(); pump(2)
assert ("review_next", 0) in d.caps
d.dlg.close(); pump(1)
key(rv, "Return"); pump(2)
assert rv.item is None and "Every word is answered" in rv.word.cget("text") and "3 of 3" in rv.count.cget("text")
assert not rv.next_btn.enabled and saved()[2] == {"w": "shitload", "keys": ["A large amount."], "kinds": ["swear"],
                                                  "whole": False}
rv.close(); pump(1)
assert app.review is None
d = app.edit_keys(); pump(2)
assert ("review_next", 0) not in d.caps                   # (and only then)
d.dlg.close(); pump(1)

# starting again carries on at the first word not answered, with the earlier answers kept
lines = saved()
with open(answers, "w", encoding="utf-8") as f:
    for a in lines[:1]:
        f.write(json.dumps(a) + "\n")
rv = app.open_review(path); pump(3)
assert rv.item["w"] == "idiot" and "1 of 3" in rv.count.cget("text")
key(rv, "BackSpace"); pump(2)
assert rv.item["w"] == "tail" and rv.kinds == ["clean", "crude", "sexual"] and rv.whole is True   # (as answered)
rv.close(); pump(1)

# a review file with no words says how to make one
empty = os.path.join(folder, "empty.jsonl")
open(empty, "w").close()
rv = app.open_review(empty); pump(3)
assert rv.item is None and "Nothing to review" in rv.word.cget("text") and "measure_rudeness" in rv.why.cget("text")
rv.close(); pump(1)
assert R.kind_colour("clean") and R.kind_colour("slur") == T.TIER_COLORS[3]
root.destroy()

# tools/measure_rudeness.py: a review file's words (the meanings asked about, the rules' guesses) and the answers
import sys
sys.path.insert(0, os.path.join(_paths.ROOT, "tools"))
import measure_rudeness as M
import rudeness
senses = [{"glosses": ["The appendage at the back of an animal."]},
          {"glosses": ["plural of tails"], "tags": ["form-of"]},
          {"glosses": ["The buttocks."], "tags": ["slang"]},
          {"glosses": ["To follow closely."]},
          {"glosses": ["Sexual intercourse."], "tags": ["vulgar", "slang"]}]
scored = [rudeness.score_sense(x, "noun", "tail") for x in senses]
assert M.shown_meanings(senses, scored) == [0, 2, 4]                  # (the main one, then those with a sign)
item = M.review_item("tail", senses, scored, "a test", ["noun"] * 5)
assert [x["key"] for x in item["senses"]] == ["The appendage at the back of an animal.", "The buttocks.",
                                               "Sexual intercourse."]
assert item["senses"][2]["guess"] == "sexual" and item["senses"][1]["labels"] == ["slang"]
assert item["senses"][0]["pos"] == "noun" and item["w"] == "tail" and item["why"] == "a test"
ans = os.path.join(folder, "a.jsonl")
R.write_answers(ans, {"tail": {"w": "tail", "keys": [x["key"] for x in item["senses"]],
                               "kinds": ["clean", "crude", "sexual"], "whole": False}}, ["tail"])
R.write_answers(ans, {**R.read_answers(ans), "idiot": {"w": "idiot", "keys": ["x"], "kinds": ["insult"],
                                                       "whole": False}}, ["idiot"])
assert [a["w"] for a in map(json.loads, open(ans))] == ["idiot", "tail"]    # (a word not in this review is kept)
got = M.read_answers(ans)
assert got["tail"]["kinds"]["The buttocks."] == "crude" and got["tail"]["whole"] is False
share = M.score_answers(got, {"tail": senses}, {"tail": scored}, log=lambda *a: None)
assert 0 <= share <= 1
print("review self-test passed")
