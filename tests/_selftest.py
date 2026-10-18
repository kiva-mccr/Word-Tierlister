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
# a big tier draws from at most BOUNDARY_POOL words a side (it built every pair of 5% of each tier: millions)
seen_sql = []
s.db.set_trace_callback(seen_sql.append)
s.pick_boundary(); s.db.set_trace_callback(None)
assert all(int(q.rsplit("LIMIT", 1)[1]) <= s.BOUNDARY_POOL for q in seen_sql if "ORDER BY rating" in q), seen_sql

# anchors follow their tier (UI-40): an anchor that moves hands its old tier's anchor to its neighbour there
an = s.get_anchors()
b_words = [r[0] for r in s.db.execute("SELECT word FROM words WHERE tier=2 ORDER BY rating, word")]
s.db.execute("UPDATE words SET rating=? WHERE word=?", (1500.0, an[2]))           # B's anchor sits mid-tier
others = [w for w in b_words if w != an[2]]
for i, w in enumerate(others):                                                       # neighbours above and below
    s.db.execute("UPDATE words SET rating=? WHERE word=?", (1490.0 - i if i % 2 else 1510.0 + i, w))
s.db.commit()
below = s.db.execute("SELECT word FROM words WHERE tier=2 AND word!=? AND rating<=1500 ORDER BY rating DESC", (an[2],)).fetchone()[0]
above = s.db.execute("SELECT word FROM words WHERE tier=2 AND word!=? AND rating>1500 ORDER BY rating ASC", (an[2],)).fetchone()[0]
changes = s.place(an[2], 4)                                                          # moved down: the one just below
assert changes == [(an[2], 2, 4, below)] and s.get_anchors()[2] == below and s.get_anchors()[4] == an[4]
s.undo(); assert s.get_anchors() == an and s.get_word(an[2])["tier"] == 2         # undo restores the anchors too
s.db.execute("UPDATE words SET rating=1500 WHERE word=?", (an[2],)); s.db.commit()
changes = s.place(an[2], 0)                                                          # moved up: the one just above
assert changes == [(an[2], 2, 0, above)] and s.get_anchors()[2] == above
s.undo()
assert s.place(an[2], 2) == [] and s.get_anchors() == an                            # same tier: nothing changes
assert s.place(b_words[0] if b_words[0] != an[2] else b_words[1], 3) == []           # not an anchor: nothing to do
s.undo(); s.undo()
# a tier with no other words keeps an empty slot
lone = T.Store(os.path.join(tempfile.mkdtemp(), "lone.db"))
lone.insert_words(["s1", "a1", "b1", "c1", "d1", "f1", "x"])
lone.set_anchors(["s1", "a1", "b1", "c1", "d1", "f1"])
assert lone.place("a1", 3) == [("a1", 1, 3, None)] and lone.get_anchors()[1] is None
lone.undo(); assert lone.get_anchors()[1] == "a1"
# a boundary swap moves an anchor too: the swap's info says so, and undo restores
lone.place("x", 2)
lone.db.execute("UPDATE words SET rating=? WHERE word='b1'", (1000.0,)); lone.db.commit()
info = lone.record_comparison("a1", "b1", "b", "boundary")                          # b1 (B) beats a1 (A): swap
assert info["swapped"] and lone.get_anchors()[1] == "b1", (info, lone.get_anchors())   # A passes to the word that came up
assert {c[0] for c in info["anchors"]} == {"a1", "b1"}                               # both were anchors
assert lone.get_anchors()[2] == "x"                                                  # B passes to its other word
lone.undo(); assert lone.get_anchors() == ["s1", "a1", "b1", "c1", "d1", "f1"] and lone.get_word("a1")["tier"] == 1
lone.close()

# progress (UI-14): segment tallies and coverage, kept up to date without recounting, always equal to a recount
def recount():
    s._prog = None
    return s.progress()
s.set_frequencies([(w, 1.0 / (i + 1)) for i, w in enumerate(words)])
assert s.get_meta("freq_done") == "1"
p0 = s.progress()
assert len(p0["segments"]) == 4 and sum(t for _p, t in p0["segments"]) == s.count_words()
assert sum(p for p, _t in p0["segments"]) == s.stats()["placed"] and 0 < p0["coverage"] < 1
fresh = s.next_unplaced()["word"]
s.place(fresh, 3); p1 = s.progress()
assert sum(p for p, _ in p1["segments"]) == sum(p for p, _ in p0["segments"]) + 1 and p1["coverage"] > p0["coverage"]
assert p1 == recount()
s.unplace(fresh); assert s.progress() == recount()
s.undo(); assert s.progress() == recount() and s.get_word(fresh)["tier"] == 3   # undo of the unplace: placed again
s.undo(); assert s.progress() == recount() == p0                                  # undo of the place
assert [T.Store.segment_of(r) for r in (0, 999, 1000, 9999, 10000, 99999, 100000, 10 ** 7)] == [0, 0, 1, 1, 2, 2, 3, 3]

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
