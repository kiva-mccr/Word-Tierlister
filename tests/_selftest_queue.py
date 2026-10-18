import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import os, sqlite3, tempfile, time
import tierlist as T

tmp = tempfile.mkdtemp()
quiet = lambda *_: None


def fresh(name, n, pen=None):
    s = T.Store(os.path.join(tmp, name))
    s.insert_words([f"w{i:07d}" for i in range(n)])
    if pen:
        s.db.executemany("UPDATE words SET pen=? WHERE word=?", [(pen(i), f"w{i:07d}") for i in range(n)])
        s.db.commit()
    return s


def first_ranks(s, k):
    return [r[0] for r in s.db.execute(
        "SELECT rank FROM words WHERE tier IS NULL ORDER BY skips, qkey LIMIT ?", (k,))]


# ---- 1. exponential decay: shape of the early picks -------------------------------------------
N, K, S = 200000, 2000, 20000
s = fresh("exp.db", N)
t = time.time()
s.reshuffle(seed=42, spread=S, shape="exp", compound=1.0)
print(f"reshuffle {N:,} words: {time.time() - t:.1f}s")
r = first_ranks(s, K)
mean = sum(r) / K
below = sum(x < S * 0.6931 for x in r) / K
far = sum(x > 5 * S for x in r) / K
print(f"exp: mean rank {mean:,.0f} (expect ~{S:,}), below median {below:.3f} (expect .5), beyond 5s {far:.4f} (expect ~.007)")
assert 17500 < mean < 22500, mean
assert 0.43 < below < 0.57, below
assert far < 0.02, far
assert r != sorted(r)                      # genuinely shuffled, not frequency order
assert sum(1 for x in r if x < 100) >= 1   # very common words still show up early sometimes
assert sum(1 for x in r if x > 2 * S) > 100  # ...and so do rarer ones, just less often

# ---- 2. gaussian: tighter tail ---------------------------------------------------------------------
s.reshuffle(seed=42, spread=S, shape="gauss", compound=1.0)
rg = first_ranks(s, K)
meang = sum(rg) / K
print(f"gauss: mean rank {meang:,.0f} (expect ~{0.798 * S:,.0f}), max {max(rg):,}")
assert 14000 < meang < 18000, meang
assert max(rg) < 5 * S
assert sum(x > 3 * S for x in rg) / K < 0.02

# ---- 3. seeds -----------------------------------------------------------------------------------------
s5 = fresh("seed.db", 5000)
def order(sd, **kw):
    sd.reshuffle(**kw)
    return [r[0] for r in sd.db.execute("SELECT word FROM words WHERE tier IS NULL ORDER BY skips, qkey")]
a = order(s5, seed=7, spread=2000, shape="exp")
b = order(s5, seed=7, spread=2000, shape="exp")
c = order(s5, seed=8, spread=2000, shape="exp")
assert a == b, "same seed must reproduce the same order"
assert a != c, "different seeds must differ"
assert s5.queue_settings()["seed"] == 8
# order is independent of which words are already placed
s5.reshuffle(seed=7)
for w in a[:50] + a[3000:3050]:
    s5.place(w, 2)
d = order(s5, seed=7)
assert d == [w for w in a if w not in set(a[:50] + a[3000:3050])]

# ---- 4. compound demotion ----------------------------------------------------------------------------------
sc = fresh("comp.db", 100000, pen=lambda i: 1 if i % 2 else 0)
for strength, lo, hi in ((1.0, 0.21, 0.33), (0.0, 0.45, 0.55), (3.0, 0.0, 0.05)):
    sc.reshuffle(seed=3, spread=20000, shape="exp", compound=strength)
    top = [int(w[1:]) for (w,) in sc.db.execute(
        "SELECT word FROM words WHERE tier IS NULL ORDER BY skips, qkey LIMIT 2000")]
    share = sum(i % 2 for i in top) / len(top)
    print(f"compound strength {strength}: compounds are {share:.3f} of early words")
    assert lo <= share <= hi, (strength, share)
sh = fresh("hyph.db", 100000, pen=lambda i: 2 if i % 2 else 0)
sh.reshuffle(seed=3, spread=20000, shape="exp", compound=1.0)
top = [int(w[1:]) for (w,) in sh.db.execute("SELECT word FROM words WHERE tier IS NULL ORDER BY qkey LIMIT 2000")]
share = sum(i % 2 for i in top) / len(top)
print(f"hyphenated share: {share:.3f} (expect ~.18)")
assert 0.13 <= share <= 0.23, share

# ---- 5. real compound detection --------------------------------------------------------------------------------
sd = T.Store(os.path.join(tmp, "detect.db"))
sd.insert_words(["bookshelf", "notebook", "something", "carpet", "table", "well-known",
                 "serendipity", "gristle", "baseball", "zymolytic"])
assert T.compute_penalties(sd, quiet)
pen = {r[0]: r[1] for r in sd.db.execute("SELECT word, pen FROM words")}
assert pen["bookshelf"] == 1 and pen["notebook"] == 1 and pen["well-known"] == 2, pen
assert all(pen[w] == 0 for w in ("something", "carpet", "table", "serendipity", "gristle", "baseball", "zymolytic")), pen

# ---- 6. prepare_queue + migration from an older save file ---------------------------------------------------------------
old = os.path.join(tmp, "old.db")
con = sqlite3.connect(old)
con.executescript("""
CREATE TABLE words(word TEXT PRIMARY KEY, rank INTEGER NOT NULL, tier INTEGER,
    rating REAL NOT NULL DEFAULT 1500, games INTEGER NOT NULL DEFAULT 0, skips INTEGER NOT NULL DEFAULT 0);
CREATE INDEX idx_words_queue ON words(tier, skips, rank);
""")
words = ["the", "of", "bookshelf", "table", "moist", "serendipity", "notebook", "gristle", "luminous",
         "bureaucracy", "well-known", "zymolytic"] + [f"zz{i:04d}" for i in range(500)]
con.executemany("INSERT INTO words(word, rank, tier, rating, games, skips) VALUES(?,?,?,?,?,?)",
                [(w, i, 2 if w in ("table", "the") else None, 1500.0, 3 if w == "table" else 0,
                  1 if w == "moist" else 0) for i, w in enumerate(words)])
con.commit(); con.close()
m = T.Store(old)
cols = {r[1] for r in m.db.execute("PRAGMA table_info(words)")}
assert {"qkey", "pen"} <= cols
assert m.get_word("table")["tier"] == 2 and m.get_word("table")["games"] == 3   # progress intact
assert m.get_word("moist")["skips"] == 1
T.prepare_queue(m, quiet)
assert m.db.execute("SELECT COUNT(*) FROM words WHERE tier IS NULL AND (qkey IS NULL OR qkey>=1e17)").fetchone()[0] == 0
assert m.get_meta("pen_done") == "1" and m.get_word("bookshelf")["pen"] == 1
nxt = m.next_unplaced()
assert nxt["tier"] is None and nxt["skips"] == 0     # skipped 'moist' is not next
q = [r[0] for r in m.db.execute("SELECT word FROM words WHERE tier IS NULL ORDER BY skips, qkey")]
assert q[-1] == "moist"                                # skipped words still go to the very back
seed_before = m.queue_settings()["seed"]
T.prepare_queue(m, quiet)                              # idempotent: no reshuffle when up to date
assert m.queue_settings()["seed"] == seed_before
a1 = [r[0] for r in m.db.execute("SELECT word FROM words WHERE tier IS NULL ORDER BY skips, qkey")]
T.prepare_queue(m, quiet)
a2 = [r[0] for r in m.db.execute("SELECT word FROM words WHERE tier IS NULL ORDER BY skips, qkey")]
assert a1 == a2
m.close()
m2 = T.Store(old)                                       # reopening keeps everything
assert m2.next_unplaced()["word"] == nxt["word"]

# ---- 7. unplace goes to the front and undo restores it; undo of history without qkey is safe ------------------------------
u = m2
first = u.next_unplaced()["word"]
u.place(first, 1)
u.unplace("table")
assert u.next_unplaced()["word"] == "table"
u.undo()
assert u.get_word("table")["tier"] == 2
u.undo()                                                # undo the place() of `first`
assert u.get_word(first)["tier"] is None
legacy = '{"before": [{"word": "table", "tier": 4, "rating": 1500.0, "games": 0, "skips": 0, "rank": 3}], "comp_ids": [], "conf_added": [], "comps_deleted": [], "conf_deleted": []}'
u.db.execute("INSERT INTO history(payload, ts) VALUES(?, 0)", (legacy,))
u.db.commit()
qk = u.get_word("table")["qkey"]
u.undo()
assert u.get_word("table")["tier"] == 4 and u.get_word("table")["qkey"] == qk

# ---- 8. paging beyond 1500 and sort options ------------------------------------------------------------------------------------
p = fresh("page.db", 9000)
p.reshuffle(seed=1)
for i in range(0, 7000):
    p.place(f"w{i:07d}", i % 6)
rows, total = p.list_words("", "All placed", limit=3000)
assert total == 7000 and len(rows) == 3000
seen = set(r["word"] for r in rows)
for off in (3000, 6000):
    page, tot = p.list_words("", "All placed", limit=3000, offset=off, with_total=False)
    assert tot is None
    assert not (seen & set(r["word"] for r in page))
    seen |= set(r["word"] for r in page)
assert len(seen) == 7000
az, _ = p.list_words("", "All placed", "A-Z", limit=5)
assert [r["word"] for r in az] == sorted(r["word"] for r in az) and az[0]["word"] == "w0000000"
fq, _ = p.list_words("", "Unplaced", "Frequency", limit=3)
assert [r["rank"] for r in fq] == [7000, 7001, 7002]
# M-7: every column can sort, either way round
za, _ = p.list_words("", "All placed", "A-Z", limit=5, reverse=True)
assert [r["word"] for r in za] == sorted((r["word"] for r in za), reverse=True) and za[0]["word"] > az[-1]["word"]
assert [r["rank"] for r in p.list_words("", "Unplaced", "Frequency", limit=3, reverse=True)[0]] == [8999, 8998, 8997]
for name, key in (("Rating", "rating"), ("Duels", "games")):
    hi, _ = p.list_words("", "All placed", name, limit=50)
    lo, _ = p.list_words("", "All placed", name, limit=50, reverse=True)
    assert [r[key] for r in hi] == sorted((r[key] for r in hi), reverse=True) and [r[key] for r in lo] == sorted(r[key] for r in lo)
    assert hi[0][key] >= lo[0][key]
back, _ = p.list_words("", "All placed", "Default", limit=5, reverse=True)
assert back[0]["tier"] == max(r["tier"] for r in p.list_words("", "All placed", limit=7000)[0])   # F first
dq, utotal = p.list_words("", "Unplaced", "Default", limit=2000)
assert utotal == 2000 and [r["word"] for r in dq] == [r[0] for r in p.db.execute(
    "SELECT word FROM words WHERE tier IS NULL ORDER BY skips, qkey, rank")]
assert dq[0]["rank"] != 7000 or dq[1]["rank"] != 7001      # unplaced default order is the shuffled queue
v = p.version
p.place("w0008000", 1)
assert p.version > v

# ---- 9. timing at scale: next word + stats must stay instant ------------------------------------------------------------------
big = fresh("big.db", 300000)
t = time.time(); big.reshuffle(seed=5); print(f"reshuffle 300k: {time.time() - t:.1f}s")
t = time.time()
for _ in range(50):
    big.next_unplaced(); big.stats()
per = (time.time() - t) / 50
print(f"next+stats at 300k: {per * 1000:.2f} ms")
assert per < 0.05

# ---- M-11: the duel pickers read indexes instead of sorting whole tiers
import random as _r
_r.seed(3)
rows = [(t % 6, 1300 + (i * 37) % 600 if i % 5 else 1500.0, i % 9, f"w{i:07d}") for t, i in enumerate(range(10, 300000, 7))]
big.db.executemany("UPDATE words SET tier=?, rating=?, games=? WHERE word=?", rows); big.db.commit()
assert big.tier_counts() == {t: n for t, n in big.db.execute(
    "SELECT tier, COUNT(*) FROM words WHERE tier IS NOT NULL GROUP BY tier")}     # a direct write is noticed
plan = " ".join(r[3] for r in big.db.execute("EXPLAIN QUERY PLAN SELECT * FROM words WHERE tier=2 AND rating>1500 "
                                             "ORDER BY rating LIMIT 80"))
assert "idx_words_tr" in plan and "TEMP B-TREE" not in plan, plan
for word in ("w0000017", "w0000010"):                                   # an ordinary rating; one of a big tie
    a = big.get_word(word)
    near = big._nearest(a, 80)
    every = sorted(abs(r[0] - a["rating"]) for r in big.db.execute(
        "SELECT rating FROM words WHERE tier=? AND word!=?", (a["tier"], word)))
    assert len(near) == 80 and word not in [r["word"] for r in near]
    assert sorted(abs(r["rating"] - a["rating"]) for r in near) == every[:80]     # exactly the 80 nearest
t = time.time()
for _ in range(20):
    assert big.pick_within() and big.pick_boundary()
per = (time.time() - t) / 20
print(f"pick_within + pick_boundary at 300k: {per * 1000:.1f} ms")
assert per < 0.04
# the least-dueled words have met everyone near them: words with more duels are tried too (never "no pair")
tiny = fresh("tiny.db", 5)
for i, w in enumerate(["w0000000", "w0000001", "w0000002", "w0000003"]):
    tiny.place(w, 0 if i < 2 else 1)
tiny.record_comparison("w0000000", "w0000001", "a", "within")
tiny.db.execute("UPDATE words SET games=5 WHERE tier=1"); tiny.db.commit()
assert set(tiny.pick_within()[:2]) == {"w0000002", "w0000003"}
print("QUEUE OK")
