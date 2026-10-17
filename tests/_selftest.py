import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import os, random, sys, tempfile
import tierlist as T

random.seed(1)
tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "t.db")
s = T.Store(path)
words = [f"w{i:03d}" for i in range(200)] + ["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist"]
s.insert_words(words)
assert s.count_words() == 206

# anchors
s.set_anchors(["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist"])
assert s.get_anchors()[0] == "serendipity"
assert s.get_word("moist")["tier"] == 5

# queue order: fresh by rank, skipped to the back
n = s.next_unplaced()
assert n["word"] == "w000", n["word"]
s.skip("w000")
assert s.next_unplaced()["word"] == "w001"

# place with anchor comparisons, then undo restores everything
s.place("w001", 2, comps=[("table", "tie")])
assert s.get_word("w001")["tier"] == 2
assert s.db.execute("SELECT COUNT(*) FROM comparisons").fetchone()[0] == 1
assert s.undo() == "w001"
assert s.get_word("w001")["tier"] is None
assert s.db.execute("SELECT COUNT(*) FROM comparisons").fetchone()[0] == 0

# queue: all fresh first, skipped ones last
for i in range(1, 200):
    s.place(f"w{i:03d}", random.randrange(6))
assert s.next_unplaced()["word"] == "w000"  # only the skipped word remains
assert s.stats()["placed"] == 205

# within-tier duels move Elo
tier_words = [r["word"] for r in s.db.execute("SELECT word FROM words WHERE tier=2 LIMIT 2")]
a, b = tier_words
s.record_comparison(a, b, "a", "within")
ra, rb = s.get_word(a), s.get_word(b)
assert ra["rating"] > rb["rating"] and ra["games"] == 1 and rb["games"] == 1

# pick_within never repeats a faced pair for these two when others exist
seen = set()
for _ in range(30):
    p = s.pick_within(2)
    assert p is not None
    x, y, t = p
    assert not s._faced(x, y)
    s.record_comparison(x, y, random.choice(["a", "b", "tie"]), "within")

# conflict detection: a>b, b>c, then c>a
c = "wxyz1"; d = "wxyz2"; e = "wxyz3"
s.insert_words([c, d, e])
for w in (c, d, e):
    s.place(w, 1)
s.record_comparison(c, d, "a", "within")   # c>d
s.record_comparison(d, e, "a", "within")   # d>e
info = s.record_comparison(e, c, "a", "within")  # e>c  -> contradicts
assert info["conflict"], info
assert s.stats()["conflicts"] == 1
pair = s.pick_conflict()
assert set(pair) == {c, e}
# re-judge resolves it
info = s.record_comparison(pair[0], pair[1], "a" if pair[0] == c else "b", "conflict")
assert not info["conflict"] and s.stats()["conflicts"] == 0
# undo restores the flagged conflict and old comparison
s.undo()
assert s.stats()["conflicts"] == 1

# boundary swap: lower-tier word wins -> swap
hi = s.db.execute("SELECT word FROM words WHERE tier=0 AND word NOT IN (SELECT word FROM anchors) LIMIT 1").fetchone()[0]
lo = s.db.execute("SELECT word FROM words WHERE tier=1 AND word NOT IN (SELECT word FROM anchors) LIMIT 1").fetchone()[0]
assert s.swap_counts() == [0, 0, 0, 0, 0]
info = s.record_comparison(hi, lo, "b", "boundary")
assert info["swapped"], info
assert s.get_word(lo)["tier"] == 0 and s.get_word(hi)["tier"] == 1
assert s.swap_counts() == [1, 0, 0, 0, 0]                                       # counted at S|A (UI-31)
s.undo()
assert s.get_word(lo)["tier"] == 1 and s.get_word(hi)["tier"] == 0
assert s.swap_counts() == [0, 0, 0, 0, 0]                                       # undo takes it back off
s.record_comparison(hi, lo, "a", "boundary"); assert s.swap_counts() == [0] * 5   # no swap: not counted
s.undo()
# how settled each tier's order is (UI-31): the share of its words with at least N duels
shares = s.settled_shares(1)
assert len(shares) == 6 and all(x is None or 0 <= x <= 1 for x in shares)
s.db.execute("UPDATE words SET games=0 WHERE tier=0"); s.db.commit()
w0 = s.db.execute("SELECT word FROM words WHERE tier=0 LIMIT 1").fetchone()[0]
n0 = s.tier_counts()[0]
s.db.execute("UPDATE words SET games=3 WHERE word=?", (w0,)); s.db.commit()
assert abs(s.settled_shares(3)[0] - 1 / n0) < 1e-9 and s.settled_shares(4)[0] == 0
bp = s.pick_boundary()
assert bp and s.get_word(bp[0])["tier"] + 1 == s.get_word(bp[1])["tier"]

# unplace puts word back at the front of the queue
s.unplace("w050")
assert s.next_unplaced()["word"] == "w050"

# list / search / export
rows, total = s.list_words("w05", "All placed")
assert total >= 1
assert len(s.export_rows()) > 100

# resumable: close, reopen, state intact
placed = s.stats()["placed"]
s.close()
s2 = T.Store(path)
assert s2.stats()["placed"] == placed
assert s2.get_anchors()[2] == "table"
assert s2.undo() is not None  # undo history persists across restarts
s2.close()

# ---- "+N today" counts saved actions since a time; undone ones drop out (UI-15)
import time as _t
st = T.Store(os.path.join(tempfile.mkdtemp(), "today.db")); st.insert_words(["a1", "a2", "a3"])
t0 = _t.time() - 1
assert st.actions_since(t0) == 0
st.place("a1", 0); st.place("a2", 3); assert st.actions_since(t0) == 2 and st.actions_since(_t.time() + 60) == 0
st.undo(); assert st.actions_since(t0) == 1
st.close()

# ---- definition text split into senses for the drawer (UI-12)
from definitions import parse_definition
senses = parse_definition('1. (noun) a round fruit\n      e.g. "an apple a day"\n2. (verb) to do a thing\n'
                          '3. (adj) red')
assert [x["num"] for x in senses] == ["1", "2", "3"] and senses[0]["pos"] == "noun"
assert senses[0]["text"] == "a round fruit" and senses[0]["example"] == "an apple a day"
assert senses[1]["example"] is None and senses[2]["pos"] == "adj"
assert parse_definition("(No definition found.)") == [{"num": "", "pos": "", "text": "(No definition found.)", "example": None}]
assert parse_definition("") == [] and parse_definition(None) == []
assert parse_definition("1. no part of speech")[0] == {"num": "1", "pos": "", "text": "no part of speech", "example": None}
print("CORE OK")
