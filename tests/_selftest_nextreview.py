import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""The next review (active review: tools/measure_rudeness.py next): candidate signals mined from Wiktionary's own
rude labels, the groups a word is in (like your misses, a candidate signal, signals that disagree, near the line, no
sign at all), the groups weighted by where the rules were wrong, the words picked (one-part, none answered already, a
few per candidate) and the review file refreshed: the answered words first, as they were, the unanswered ones replaced
by the new ones; the meaning a word was picked for always asked about."""
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
why = M.next_reasons("x", one, [{"sexual": 3.2, "expletive": 2.4}], {}, {})
assert why["signals disagree"][:2] == ("signals disagree: sexual 3.2, expletive 2.4", 0) and "near the line" in why
why = M.next_reasons("x", one, [{"sexual": 3.2, "expletive": 1.0}], {}, {})
assert "signals disagree" not in why and why["near the line"][:2] == ("near the line: 3.2 points, 3 counts", 0)
assert M.next_reasons("x", one, [{"expletive": 5.0}], {}, {}) == {}            # (sure of it: nothing to learn)
why = M.next_reasons("table", words["table"], scored["table"], topics, lean)
assert why == {"no sign at all": ("no sign at all (to count what the rules miss)", None)}, why
assert "no sign at all" not in M.next_reasons("plain1", words["plain1"], scored["plain1"], topics, lean)  # (rare)
assert "a candidate signal" not in M.next_reasons("x", words["rude1"], [{"expletive": 4.0}], topics, lean)  # (found rude)

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

# learning from the answers: groups weighted by where the rules were wrong, and the signs on the misses
def item(w, why, senses, whole=False):
    return {"w": w, "why": why, "whole": whole, "senses": [{"key": g, "pos": "noun", "labels": labs, "gloss": g,
                                                            "guess": guess} for g, labs, guess in senses]}


done = [item("a", "near the line: 2.6 points, 3 counts", [("A zibbly fellow.", ["slang"], "clean")]),
        item("b", "near the line: 3.1 points, 3 counts", [("A zibbly sort.", [], "clean")]),
        item("c", "no sign at all (to count what the rules miss)", [("A pot.", [], "clean")]),
        item("d", "the rules say sexual", [("Sex.", ["vulgar"], "sexual")])]        # (the first sample: no group)
said = {"a": {"kinds": {"A zibbly fellow.": "expletive"}, "whole": False},
        "b": {"kinds": {"A zibbly sort.": "expletive"}, "whole": False},
        "c": {"kinds": {"A pot.": "clean"}, "whole": False}, "d": {"kinds": {"Sex.": "sexual"}, "whole": True}}
assert M.group_of(done[0]["why"]) == "near the line" and M.group_of(done[3]["why"]) is None
assert M.group_of("near the line for the whole word: 2.8 points, 3.5 smears it") == "near the line"
shares = M.group_shares(done, said)
assert abs(sum(shares.values()) - 1) < 1e-9 and set(shares) == set(dict(M.NEXT_SHARES))
base = dict(M.NEXT_SHARES)
assert shares["near the line"] / base["near the line"] > shares["no sign at all"] / base["no sign at all"]   # (3/4
assert abs(shares["no sign at all"] / shares["a candidate signal"] - (1 / 3) / (1 / 2) * 0.03 / 0.28) < 1e-9  # vs 1/3)
signs = M.miss_signs(done, said)
assert signs == {"zibbly": 1.0}, signs                         # (in two misses; "slang" and "fellow" in one only)
zib = [rudeness.expand(sense("A box.")), rudeness.expand(sense("A zibbly person."))]
why = M.next_reasons("zib", zib, [{}, {}], {}, {}, misses=signs)
assert why["like your misses"] == ('like your misses: "zibbly" (you answered 100% of its meanings differently)', 1,
                                   "zibbly"), why
assert "like your misses" not in M.next_reasons("zib", zib, [{}, {}], {}, {})

# the refresh: the answered words stay first, in their order (Back walks them), the unanswered give way to new ones
review = os.path.join(folder, "rude_review.jsonl")
lines = [json.dumps(M.review_item(w, words[w], scored[w], "a test", poses[w])) for w in ("chair", "plain3", "plain5")]
with open(review, "w", encoding="utf-8") as f:
    f.write(lines[0] + "\n" + lines[1] + "\n" + lines[2] + "\n")
with open(review_answers_path(review), "w", encoding="utf-8") as f:
    for w, key in (("plain5", "A tool for work number 5."), ("seen", "A thing.")):   # (seen: from an older list)
        f.write(json.dumps({"w": w, "keys": [key], "kinds": ["clean"], "whole": False}) + "\n")
told = []
M.make_next(entries, review, size=20, log=told.append)
got = open(review, encoding="utf-8").read().splitlines()
assert got[0] == lines[2], got[:2]                               # (plain5 answered: kept first, as it was)
items = [json.loads(line) for line in got]
ws = [it["w"] for it in items]
assert ws[0] == "plain5" and "plain3" not in ws and "seen" not in ws and len(set(ws)) == len(ws)
assert "chair" in ws[1:]                                         # (unanswered: dropped, then picked again)
flag = next(it for it in items if it["w"] == "flagword")
assert [s["key"] for s in flag["senses"]] == ["A banner.", "A flag of pride."] and flag["why"].startswith("a candid")
assert told and told[0].startswith(f"{len(ws) - 1} new words to review (after the 1 answered; 2 unanswered replaced)")
assert not os.path.exists(review + ".part")
M.make_next(entries, review, size=20, log=told.append)          # (again: the same answered word first, no repeats)
again = [json.loads(line)["w"] for line in open(review, encoding="utf-8")]
assert again[0] == "plain5" and len(set(again)) == len(again)
print("next review self-test passed")
