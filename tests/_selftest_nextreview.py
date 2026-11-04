import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""The next review (active review: tools/measure_rudeness.py next): candidate signals mined from Wiktionary's own
rude labels, the groups a word is in (a candidate signal, signals that disagree, near the line, no sign at all), the
words picked (none reviewed already, a few per candidate) and added to the end of the review file, the meaning they
were picked for always asked about."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(_paths.ROOT, "tools"))
import measure_rudeness as M
import rudeness
from constants import review_answers_path

M.CANDIDATE_MIN, M.CANDIDATE_Z = 3, 2.0     # (a small made-up dictionary)


def sense(gloss, tags=(), topics=(), pos="noun"):
    return {"g": gloss, **({"t": list(tags)} if tags else {}), **({"p": list(topics)} if topics else {}), "pos": pos}


ENTRIES = {
    **{f"rude{i}": [sense("A stupid zorbish fellow.", tags=["derogatory"], topics=["LGBT"])] for i in range(12)},
    **{f"plain{i}": [sense(f"A tool for work number {i}.")] for i in range(40)},
    "flagword": [sense("A banner."), sense("To wave."), sense("A flag of pride.", topics=["LGBT"])],
    "zorby": [sense("A zorbish thing."), sense("A box.")],
    "ice-cream": [sense("A frozen dessert.")], "ice cream": [sense("A frozen dessert.")],   # (compounds: never asked)
    "table": [sense("A piece of furniture with a flat top.")],
    "chair": [sense("A seat for one person.")],
    "seen": [sense("A thing.")],
}
folder = tempfile.mkdtemp()
entries = os.path.join(folder, "entries.jsonl")
with open(entries, "w", encoding="utf-8") as f:
    for w, cs in ENTRIES.items():
        f.write(json.dumps({"w": w, "senses": cs}) + "\n")
words, poses, family = M.load(entries)
scored = rudeness.score_words(words, poses, None, family)

# candidates: a topic the rules never read, and a gloss word leaning to rude meanings
topics, lean = M.candidates(words)
assert topics == {"lgbt": 12 / 13}, topics              # (flagword's pride flag is the 13th)
assert "zorbish" in lean and "tool" not in lean and "stupid" in lean
assert "lgbtq" in rudeness.TOPIC_POINTS and "lgbt" not in rudeness.TOPIC_POINTS   # (why "lgbt" is a candidate)

# the groups a word is in
why = M.next_reasons("flagword", words["flagword"], scored["flagword"], topics, lean)
assert why["a candidate signal"][:3] == ('a candidate signal: the topic "lgbt"', 2, "lgbt"), why
assert "no sign at all" not in why
why = M.next_reasons("zorby", words["zorby"], scored["zorby"], topics, lean)
assert why["a candidate signal"][0] == 'a candidate signal: "zorbish" in the meaning'
one = [rudeness.expand(sense("Something."))]
why = M.next_reasons("x", one, [{"sexual": 3.2, "insult": 2.4}], {}, {})
assert why["signals disagree"][:2] == ("signals disagree: sexual 3.2, insult 2.4", 0) and "near the line" in why
why = M.next_reasons("x", one, [{"sexual": 3.2, "insult": 1.0}], {}, {})
assert "signals disagree" not in why and why["near the line"][:2] == ("near the line: 3.2 points, 3 counts", 0)
assert M.next_reasons("x", one, [{"crude": 5.0}], {}, {}) == {}            # (sure of it: nothing to learn)
why = M.next_reasons("table", words["table"], scored["table"], topics, lean)
assert why == {"no sign at all": ("no sign at all (to count what the rules miss)", None)}, why
assert "no sign at all" not in M.next_reasons("plain1", words["plain1"], scored["plain1"], topics, lean)  # (rare)
assert "a candidate signal" not in M.next_reasons("x", words["rude1"], [{"insult": 4.0}], topics, lean)  # (found rude)

assert M.next_reasons("of", one, [{}], {}, {}) == {} == M.next_reasons("i", one, [{}], {}, {}) and M.next_reasons("an-", one, [{}], {}, {}) == {}   # (common,
assert "no sign at all" not in M.next_reasons("one-way", one, [{}], {}, {})    # an affix, or a compound: one-part
assert "no sign at all" in M.next_reasons("don't", one, [{}], {}, {})           # words only, contractions kept)

# each group spread over what its words share, a group short of words handing its share on
import random
by = {"woman": [f"w{i}" for i in range(50)], "idiot": ["i1", "i2"], "lgbt": ["l1"]}
got = M._spread(by, 6, 4, random.Random(1))
assert len(got) == 6 and {"i1", "i2", "l1"} <= set(got) and sum(w.startswith("w") for w in got) == 3
assert len(M._spread(by, 99, 4, random.Random(1))) == 4 + 2 + 1             # (at most `cap` of each)

# the meaning a word was picked for is asked about, even with no sign the rules read
assert M.shown_meanings(words["flagword"], scored["flagword"]) == [0]
assert M.shown_meanings(words["flagword"], scored["flagword"], also=[2]) == [0, 2]

# the pick: none reviewed already, the candidate signals spread out
picked = M.pick_next(words, scored, size=20, skip={"chair"})
assert "chair" not in picked and {"flagword", "zorby", "table"} <= set(picked), picked
assert not {"ice-cream", "ice cream"} & set(picked) and not {"ice-cream", "ice cream"} & set(M.pick_sample(
    words, scored, size=40, weak_words=["ice-cream"]))
assert picked["flagword"] == ('a candidate signal: the topic "lgbt"', [2]) and picked["table"][1] == []
assert len(M.pick_next(words, scored, size=10)) == 5     # (all 5: no sign at all takes the shares left over)

# added to the end of a review file, after the words already there; answered words are skipped too
review = os.path.join(folder, "rude_review.jsonl")
old = M.review_item("chair", words["chair"], scored["chair"], "a test", poses["chair"])
with open(review, "w", encoding="utf-8") as f:
    f.write(json.dumps(old) + "\n")
with open(review_answers_path(review), "w", encoding="utf-8") as f:
    f.write(json.dumps({"w": "seen", "keys": ["A thing."], "kinds": ["clean"], "whole": False}) + "\n")
assert M.reviewed(review) == {"chair", "seen"}
said = []
M.make_next(entries, review, size=20, log=said.append)
items = [json.loads(line) for line in open(review, encoding="utf-8")]
assert items[0]["w"] == "chair" and len({it["w"] for it in items}) == len(items)
assert "seen" not in {it["w"] for it in items[1:]}
flag = next(it for it in items if it["w"] == "flagword")
assert [s["key"] for s in flag["senses"]] == ["A banner.", "A flag of pride."] and flag["why"].startswith("a candid")
assert said and said[0].startswith(f"Added {len(items) - 1} words") and "no sign at all 1" in said[0], said
M.make_next(entries, review, size=20, log=said.append)              # (again: nothing picked twice)
again = [json.loads(line)["w"] for line in open(review, encoding="utf-8")]
assert len(set(again)) == len(again)
print("next review self-test passed")
