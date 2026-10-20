"""The save file: every read and write of the SQLite database goes through Store.

Nothing here imports tkinter, so the whole data layer is testable without a window.

Data model (see SCHEMA below)
    words        one row per dictionary word. tier is NULL while a word is unplaced, else 0..5
                 (S..F). rating/games are the Elo score and duel count used inside a tier.
                 skips counts "don't know / later" presses. qkey is the seeded queue key (lower =
                 comes up sooner); rank is the frequency rank (1 = most common); pen is the
                 compound-word class (0 normal, 1 closed compound, 2 hyphenated / multi-word).
                 kinds: its parts of speech (constants.KINDS bits; NULL = not known), obscene: 1 if any
                 sense is vulgar / offensive / derogatory / a slur, out: 1 if "How words are dealt" leaves
                 it out of the queue (ST-6; kept up to date by set_deal).
    comparisons  every answer ever given (winner, loser, tie, kind). Used to avoid repeating a
                 duel and to detect contradictions.
    conflicts    pairs whose answers contradict each other, waiting to be re-judged.
    anchors      the one reference word per tier used by "compare to anchors".
    defs         cached definitions.        meta  small key/value settings (seed, mode, ...).
    history      one JSON row per action, so Undo works and survives restarts.

Conventions
    * Every public method that changes data commits before returning (a crash loses nothing).
    * Store.version goes up on every change; open windows compare it to know when to refresh.
    * Methods starting with an underscore are internal helpers.
"""
import bisect
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import sqlite3
import time

from constants import (ALL_KINDS, KINDS, PEN_UNITS, QUEUE_DEFAULTS, QUEUE_SHAPES, SHELF_SOFT, SHELF_SPINES, SHELF_ZIPF, SHELF_ZONE_RANKS,
                       SHELF_ZONES, TIERS, tier_base)


# --------------------------------------------------------------------------
# Schema. All statements are IF NOT EXISTS, so opening an old save file is safe;
# columns added in later versions are migrated in Store.__init__.
# --------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS words(
    word TEXT PRIMARY KEY,
    rank INTEGER NOT NULL,
    tier INTEGER,
    rating REAL NOT NULL DEFAULT 1500,
    games INTEGER NOT NULL DEFAULT 0,
    skips INTEGER NOT NULL DEFAULT 0,
    qkey REAL,
    pen INTEGER NOT NULL DEFAULT 0,
    freq REAL NOT NULL DEFAULT 0,
    kinds INTEGER,
    obscene INTEGER NOT NULL DEFAULT 0,
    out INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS comparisons(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    winner TEXT NOT NULL,
    loser TEXT NOT NULL,
    tie INTEGER NOT NULL DEFAULT 0,
    kind TEXT NOT NULL,
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cmp_w ON comparisons(winner, loser);
CREATE INDEX IF NOT EXISTS idx_cmp_l ON comparisons(loser, winner);
CREATE TABLE IF NOT EXISTS conflicts(a TEXT NOT NULL, b TEXT NOT NULL, PRIMARY KEY(a, b));
CREATE TABLE IF NOT EXISTS swaps(comp_id INTEGER PRIMARY KEY, boundary INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS anchors(tier INTEGER PRIMARY KEY, word TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS defs(word TEXT PRIMARY KEY, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload TEXT NOT NULL,
    ts REAL NOT NULL
);
"""


class Store:
    """All persistence and ranking logic. Every public mutator commits.

    Sections, in file order: meta/defs -> word list -> seeded queue order -> stats -> anchors
    -> history/undo -> placement -> comparisons (Elo, conflicts) -> pair selection ->
    listing/export -> merging earlier progress.
    """

    def __init__(self, path):
        """Open (or create) the save file at `path`, migrate old layouts, and enable WAL mode."""
        self.path = path
        # check_same_thread=False: the first-run window (startup.py) lets a worker thread build the
        # word list while the UI thread only shows progress. Never two threads at the same moment.
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(SCHEMA)
        # Migrate save files made by earlier versions (they lack the queue-order columns).
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(words)")}
        if "qkey" not in cols:
            self.db.execute("ALTER TABLE words ADD COLUMN qkey REAL")
        if "pen" not in cols:
            self.db.execute("ALTER TABLE words ADD COLUMN pen INTEGER NOT NULL DEFAULT 0")
        if "freq" not in cols:                   # word frequency (wordfreq), for the coverage tag (UI-14)
            self.db.execute("ALTER TABLE words ADD COLUMN freq REAL NOT NULL DEFAULT 0")
        if "kinds" not in cols:                  # ST-6: kinds of words, obscene ones, left out of the queue
            self.db.execute("ALTER TABLE words ADD COLUMN kinds INTEGER")
            self.db.execute("ALTER TABLE words ADD COLUMN obscene INTEGER NOT NULL DEFAULT 0")
            self.db.execute("ALTER TABLE words ADD COLUMN out INTEGER NOT NULL DEFAULT 0")
        self.db.execute("DROP INDEX IF EXISTS idx_words_queue")
        self.db.execute("DROP INDEX IF EXISTS idx_words_q2")
        # the queue (next_unplaced): the words dealt (out=0) in order, even when nearly all are left out
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_words_q3 ON words(tier, out, skips, qkey)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_words_obscene ON words(word) WHERE obscene=1")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_words_tg ON words(tier, games)")   # settled_shares
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_words_shelf ON words(rank, tier, freq)")   # shelf()
        # nearest ratings in a tier (pick_within), a tier's weakest / strongest (pick_boundary), Browse's order
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_words_tr ON words(tier, rating)")
        # Browse's A-Z / Z-A and Frequency over the placed words only: with a few thousand placed out of a
        # million, walking every word in order to find them took ~200 ms (and froze the sort arrow's fill)
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_placed_word ON words(word) WHERE tier IS NOT NULL")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_placed_rank ON words(rank) WHERE tier IS NOT NULL")
        self.db.commit()
        self.version = 0  # bumps on every change; lets open windows know when to refresh
        self._total = None
        self._prog = None    # the shelf's tallies (shelf()), counted once, then kept up to date by each change
        self._obscene = None     # the obscene words (obscene_words()), read once

    def close(self):
        """Flush and close the database; safe to call twice."""
        try:
            self.db.commit()
            self.db.close()
        except sqlite3.Error:
            pass

    # ---- meta / defs ----------------------------------------------------
    def get_meta(self, key, default=None):
        """Read a setting from the meta table (always returned as text), or `default`."""
        r = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def set_meta(self, key, value):
        """Save a setting (stored as text) and commit."""
        self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (key, str(value)))
        self.db.commit()

    def get_def(self, word):
        """Cached definition text for `word`, or None if not looked up yet."""
        r = self.db.execute("SELECT text FROM defs WHERE word=?", (word,)).fetchone()
        return r["text"] if r else None

    def set_def(self, word, text):
        """Cache a definition so it never has to be looked up again."""
        self.db.execute("INSERT OR REPLACE INTO defs(word, text) VALUES(?, ?)", (word, text))
        self.db.commit()

    # ---- word list --------------------------------------------------------
    def count_words(self):
        """Total number of words in the list (a full count; stats() caches it)."""
        return self.db.execute("SELECT COUNT(*) FROM words").fetchone()[0]

    def insert_words(self, words):
        """Add words in presentation order. Existing words keep their tier/ratings and are only re-ranked."""
        # New words get a placeholder queue key (the back of the line) until reshuffle() runs.
        self.db.executemany(
            "INSERT INTO words(word, rank, rating, qkey) VALUES (?, ?, 1500, ?)"
            " ON CONFLICT(word) DO UPDATE SET rank=excluded.rank",
            ((w, i, 1e18 + i) for i, w in enumerate(words)),
        )
        self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('pen_done', '0')")
        self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('freq_done', '0')")
        self.db.commit()
        self._total = None
        self._prog = None
        self.version += 1

    def add_word(self, word):
        """Add one word the list did not have (UI-51: looked up and added by hand), at the very end of it: the
        rarest rank, the back of the queue. Unlike insert_words, nothing else is re-ranked or redone."""
        rank = self.db.execute("SELECT COALESCE(MAX(rank), -1) + 1 FROM words").fetchone()[0]
        self.db.execute("INSERT OR IGNORE INTO words(word, rank, rating, qkey) VALUES (?, ?, 1500, 1e18)", (word, rank))
        self.db.execute("UPDATE words SET out=? WHERE word=?", (self._out_value(None, 0), word))
        self.db.commit()
        self._total = None
        self._prog = None
        self.version += 1

    def has_word(self, word):
        """True if `word` is in the list."""
        return self.db.execute("SELECT 1 FROM words WHERE word=?", (word,)).fetchone() is not None

    def get_word(self, word):
        """The full row for `word` (sqlite3.Row), or None."""
        return self.db.execute("SELECT * FROM words WHERE word=?", (word,)).fetchone()

    def next_unplaced(self):
        """The word to show next in Place mode, or None when nothing is left."""
        # Fresh words first (skips=0), then skipped words; within each, the seeded queue order. Only the words
        # "How words are dealt" deals (out=0).
        return self.db.execute(
            "SELECT * FROM words WHERE tier IS NULL AND out=0 ORDER BY skips, qkey, rank LIMIT 1"
        ).fetchone()

    def left_out(self):
        """How many unplaced words "How words are dealt" leaves out (they never come up while it does)."""
        return self.db.execute("SELECT COUNT(*) FROM words WHERE tier IS NULL AND out=1").fetchone()[0]

    # ---- seeded queue order ---------------------------------------------------
    def queue_settings(self):
        """Seed + decay settings (a random seed is chosen once and then stored)."""
        seed = self.get_meta("qseed")
        if seed is None:
            seed = random.SystemRandom().randrange(1, 2 ** 31)
            self.set_meta("qseed", seed)
        shape = self.get_meta("qshape", QUEUE_DEFAULTS["qshape"])
        try:
            spread = max(100.0, float(self.get_meta("qspread", QUEUE_DEFAULTS["qspread"])))
            comp = min(10.0, max(0.0, float(self.get_meta("qcompound", QUEUE_DEFAULTS["qcompound"]))))
        except ValueError:
            spread, comp = float(QUEUE_DEFAULTS["qspread"]), float(QUEUE_DEFAULTS["qcompound"])
        return {"seed": int(seed), "spread": spread,
                "shape": shape if shape in QUEUE_SHAPES else "exp", "compound": comp}

    def reshuffle(self, seed=None, spread=None, shape=None, compound=None):
        """Give every unplaced word a random queue key whose odds fall off with frequency rank.

        Each word draws E ~ Exp(1) from a hash of (seed, word) and sorts by  E * exp(pos/spread)
        (exponential shape) or  E * exp((pos/spread)^2 / 2)  (gaussian shape). That is weighted
        sampling without replacement with weight exp(-pos/spread): a word `spread` ranks further
        back is e times less likely to come up early. pos = frequency rank, plus a push-back for
        compound words. Keys are stored as logs so they never overflow. The same seed always gives
        the same relative order, whichever words are already placed. The "rank" shape (Most common first,
        ST-6) is no randomness at all: the key is the rank.
        """
        for key, val in (("qseed", seed), ("qspread", spread), ("qshape", shape), ("qcompound", compound)):
            if val is not None:
                self.set_meta(key, val)
        cfg = self.queue_settings()
        spread, comp, gauss, strict = cfg["spread"], cfg["compound"], cfg["shape"] == "gauss", cfg["shape"] == "rank"
        salt = str(cfg["seed"]).encode()
        rows = self.db.execute("SELECT word, rank, pen FROM words WHERE tier IS NULL").fetchall()
        total = len(rows)
        rebuild_index = total > 100000  # much faster to rebuild the index than to update it row by row
        if rebuild_index:
            self.db.execute("DROP INDEX IF EXISTS idx_words_q3")
        batch = []
        for n, (word, rank, pen) in enumerate(rows, 1):
            if strict:
                batch.append((float(rank), word))
                if len(batch) >= 50000 or n == total:
                    self.db.executemany("UPDATE words SET qkey=? WHERE word=?", batch)
                    batch = []
                continue
            x = int.from_bytes(hashlib.blake2b(word.encode("utf-8"), digest_size=8, key=salt).digest(), "big")
            u = ((x >> 12) + 0.5) / 4503599627370496.0  # strictly inside (0, 1)
            e = -math.log(u) or 1e-300
            z = (rank + PEN_UNITS.get(pen, 0.0) * comp * spread) / spread
            batch.append((math.log(e) + (0.5 * z * z if gauss else z), word))
            if len(batch) >= 50000 or n == total:
                self.db.executemany("UPDATE words SET qkey=? WHERE word=?", batch)
                batch = []
        if rebuild_index:
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_words_q3 ON words(tier, out, skips, qkey)")
        self.db.commit()
        self.version += 1

    # ---- how words are dealt (ST-6): kinds of words, obscene ones -------------------------------------------
    def deal_settings(self):
        """{"kinds": the ticked kinds (constants.KINDS bits), "obscene": obscene words ticked, "censor": shown
        smeared}. Everything is ticked and nothing censored to start with."""
        try:
            kinds = int(self.get_meta("deal_kinds", ALL_KINDS)) & ALL_KINDS
        except ValueError:
            kinds = ALL_KINDS
        return {"kinds": kinds, "obscene": self.get_meta("deal_obscene", "1") == "1",
                "censor": self.get_meta("censor", "0") == "1"}

    def _out_value(self, kinds, obscene):
        """words.out for a word: an obscene word is dealt only while obscene words are ticked, any other word
        while one of its kinds is (a word whose kinds are not known counts as "other")."""
        d = self.deal_settings()
        if obscene:
            return 0 if d["obscene"] else 1
        return 0 if (kinds if kinds is not None else 16) & d["kinds"] else 1

    def set_deal(self, kinds=None, obscene=None):
        """Save which words are dealt and mark the rest out of the queue (one pass over the list: ~1 s with a
        million words, so the dialog runs it on a worker thread). Nothing is deleted or unplaced."""
        if kinds is not None:
            self.set_meta("deal_kinds", int(kinds) & ALL_KINDS)
        if obscene is not None:
            self.set_meta("deal_obscene", "1" if obscene else "0")
        d = self.deal_settings()
        self.db.execute(
            "UPDATE words SET out = CASE WHEN obscene=1 THEN ? WHEN (COALESCE(kinds, 16) & ?) != 0 THEN 0 ELSE 1 END"
            " WHERE out != CASE WHEN obscene=1 THEN ? WHEN (COALESCE(kinds, 16) & ?) != 0 THEN 0 ELSE 1 END",
            (0 if d["obscene"] else 1, d["kinds"]) * 2)
        self.db.commit()
        self.version += 1

    def set_censor(self, on):
        self.set_meta("censor", "1" if on else "0")
        self.version += 1

    def set_kinds(self, pairs):
        """[(word, kinds bits)] from the word source (wordsource.fill_kinds / build_wiktionary)."""
        self.db.executemany("UPDATE words SET kinds=? WHERE word=?", ((k, w) for w, k in pairs))
        self.db.commit()
        self.version += 1

    OBSCENE_VERSION = "2"   # bumped when what counts as obscene changes (2: no longer "derogatory"), to look again
    COMMON_ZIPF = 5.0       # the ~3,000 commonest words ("come", "head", "ball") are obscene only as swear words

    def set_obscene(self, words, swear=(), replace=False, zipf=None):
        """Mark `words` (those in the list) obscene; `replace`: and only those. A common word (Zipf COMMON_ZIPF and
        up: by `zipf` {word: value}, else the stored frequency) only if it is in `swear` too: one vulgar sense
        does not make "come" or "head" an obscene word, while "shit" and "fuck" are as common."""
        swear = set(swear)
        if zipf is not None:
            words = [w for w in words if w in swear or zipf.get(w, 0.0) < self.COMMON_ZIPF]
        if replace:
            self.db.execute("UPDATE words SET obscene=0 WHERE obscene=1")
        self.db.executemany("UPDATE words SET obscene=1 WHERE word=? AND obscene=0", ((w,) for w in words))
        if zipf is None:
            common = [r[0] for r in self.db.execute("SELECT word FROM words WHERE obscene=1 AND freq >= ?",
                                                    (10 ** (self.COMMON_ZIPF - 9),))]
            self.db.executemany("UPDATE words SET obscene=0 WHERE word=?", ((w,) for w in common if w not in swear))
        self.db.commit()
        self._obscene = None
        self.version += 1

    def obscene_words(self):
        """The set of obscene words (a few thousand), read once (partial index)."""
        if self._obscene is None:
            self._obscene = {r[0] for r in self.db.execute("SELECT word FROM words WHERE obscene=1")}
        return self._obscene

    def censored(self, word):
        """True if `word` is to be shown smeared or masked (Censor obscene words is on and it is obscene)."""
        return bool(word) and self.get_meta("censor", "0") == "1" and word in self.obscene_words()

    def kind_counts(self):
        """{kind key: number of words of that kind, "obscene": number of obscene words}, over the whole list
        (an obscene word counts only as obscene, as it is dealt). One pass: counted again only after a change."""
        mark = self.db.total_changes
        if getattr(self, "_kc", (None,))[0] != mark:
            counts = {k: 0 for k, _, _ in KINDS}
            counts["obscene"] = 0
            for kinds, obscene, n in self.db.execute(
                    "SELECT COALESCE(kinds, 16), obscene, COUNT(*) FROM words GROUP BY 1, 2"):
                if obscene:
                    counts["obscene"] += n
                    continue
                for key, _, bit in KINDS:
                    if kinds & bit:
                        counts[key] += n
            self._kc = (mark, counts)
        return dict(self._kc[1])

    def tier_counts(self):
        """{tier index: number of placed words}. Tiers with no words are absent. Counted again only after a
        change to the save (any write, the connection's total_changes): a duel asked for it twice."""
        mark = self.db.total_changes
        if getattr(self, "_tc", (None,))[0] != mark:
            self._tc = (mark, {r[0]: r[1] for r in self.db.execute(
                "SELECT tier, COUNT(*) FROM words WHERE tier IS NOT NULL GROUP BY tier")})
        return dict(self._tc[1])

    def stats(self):
        """Numbers for the header: total, placed, skipped, per-tier counts, duels, conflicts."""
        # Index-friendly queries: with ~1M words, a full scan per refresh would make the UI laggy.
        if self._total is None:
            self._total = self.count_words()
        tiers = self.tier_counts()
        skipped = self.db.execute(
            "SELECT COUNT(*) FROM words WHERE tier IS NULL AND skips > 0"
        ).fetchone()[0]
        return {
            "total": self._total,
            "placed": sum(tiers.values()),
            "skipped": skipped,
            "tiers": tiers,
            "comparisons": self.db.execute("SELECT COUNT(*) FROM comparisons").fetchone()[0],
            "conflicts": self.db.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0],
        }

    # ---- progress: the shelf (UI-14) ---------------------------------------------------------
    def shelf_layout(self):
        """The shelf's zones and spines: [(zone name, [rank bounds of its spines])]. Zones end where wordfreq's
        Zipf value drops below 6, 5, 4, 3 (SHELF_ZIPF); the spines are equal steps of log(rank + SHELF_SOFT), so a
        spine near the start holds a few words and one near the end thousands (a log ruler of commonness). A zone
        with no words in this list is left out."""
        n = self.count_words()
        ends = list(SHELF_ZONE_RANKS)
        if self.get_meta("freq_done") in ("1", self.FREQ_VERSION):
            for i, z in enumerate(SHELF_ZIPF):
                # the first known word below the threshold (a word with no frequency at all says nothing here:
                # one near the top, which a version-1 fill could leave, used to collapse every zone)
                r = self.db.execute("SELECT MIN(rank) FROM words WHERE freq > 0 AND freq < ?",
                                    (10 ** (z - 9),)).fetchone()[0]
                ends[i] = r if r is not None else n
        lg = lambda r: math.log10(r + SHELF_SOFT)
        bounds = [0] + [min(e, n) for e in ends] + [n]
        span = lg(n) - lg(0) if n else 1.0
        zones = []
        for name, lo, hi in zip(SHELF_ZONES, bounds, bounds[1:]):
            if hi <= lo:
                continue
            k = max(2, round(SHELF_SPINES * (lg(hi) - lg(lo)) / span))
            edges = sorted({lo, hi} | {min(hi, max(lo, round(10 ** (lg(lo) + (lg(hi) - lg(lo)) * j / k) - SHELF_SOFT)))
                                        for j in range(1, k)})   # (a tiny list can round two edges together)
            zones.append((name, edges))
        return zones

    def shelf(self):
        """The progress shelf: {"zones": [(name, number of spines)], "spines": [{"zone", "words", "placed",
        "tiers": placed per tier}], "coverage": share of the list's word frequency that is placed (0..1, None
        before the frequencies are known)}. Counted from the save once (a pass over the list), then kept up to
        date by every change of a word's tier, so a refresh never rescans."""
        if self._prog is None:
            layout = self.shelf_layout()
            spines, starts = [], []
            for name, edges in layout:
                for lo in edges[:-1]:
                    starts.append(lo)
                    spines.append({"zone": name, "words": 0, "placed": 0, "tiers": [0] * len(TIERS)})
            p = {"layout": [(name, len(edges) - 1) for name, edges in layout], "spines": spines, "starts": starts,
                 "fp": 0.0, "ft": 0.0}
            ends = starts[1:] + [layout[-1][1][-1]] if layout else []
            for sp, lo, hi in zip(spines, starts, ends):   # one range per spine, counted by SQLite (idx_words_shelf)
                for tier, n, fq in self.db.execute("SELECT tier, COUNT(*), SUM(freq) FROM words WHERE rank >= ? AND "
                                                   "rank < ? GROUP BY tier", (lo, hi)):
                    sp["words"] += n
                    p["ft"] += fq or 0.0
                    if tier is not None:
                        sp["placed"] += n
                        sp["tiers"][tier] += n
                        p["fp"] += fq or 0.0
            if not spines:
                p["ft"] = self.db.execute("SELECT TOTAL(freq) FROM words").fetchone()[0]
            self._prog = p
        p = self._prog
        return {"zones": p["layout"], "spines": [dict(sp, tiers=list(sp["tiers"])) for sp in p["spines"]],
                "coverage": p["fp"] / p["ft"] if p["ft"] > 0 else None}

    def spine_of(self, word):
        """Which spine of the progress shelf `word` belongs to (its index in shelf()["spines"]), or None."""
        self.shelf()
        row = self.get_word(word)
        starts = self._prog["starts"]
        if row is None or not starts:
            return None
        return bisect.bisect_right(starts, row["rank"]) - 1

    def _tier_moved(self, row, old, new):
        """Keep the shelf's tallies current: the word in `row` (with rank and freq) went from tier `old` to `new`
        (None = not placed)."""
        p = self._prog
        if p is None or old == new or not p["spines"]:
            return
        sp = p["spines"][bisect.bisect_right(p["starts"], row["rank"]) - 1]
        for t, sign in ((old, -1), (new, 1)):
            if t is not None:
                sp["placed"] += sign
                sp["tiers"][t] += sign
                p["fp"] += sign * (row["freq"] or 0.0)

    FREQ_VERSION = "2"     # bumped when fill_frequencies changes, so saves filled by an older one refill once
                           # (2: hyphenated / spaced forms estimated like the ranking; 1 left them at 0)

    def set_frequencies(self, pairs):
        """Store each word's frequency [(word, freq)] (for the coverage tag; filled once by wordsource)."""
        self.db.executemany("UPDATE words SET freq=? WHERE word=?", ((f, w) for w, f in pairs))
        self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('freq_done', ?)", (self.FREQ_VERSION,))
        self.db.commit()
        self._prog = None
        self.version += 1

    def settled_shares(self, min_games, totals=None):
        """Per tier, the share of its words with at least `min_games` duels (how settled its order is, UI-31);
        None for an empty tier. `totals` is tier_counts() if the caller has it already. Index-only
        (idx_words_tg): ~50 ms with a million placed words."""
        total = totals if totals is not None else self.tier_counts()
        done = dict(self.db.execute("SELECT tier, COUNT(*) FROM words WHERE tier IS NOT NULL AND games >= ? "
                                    "GROUP BY tier", (min_games,)).fetchall())
        return [done.get(t, 0) / total[t] if total.get(t) else None for t in range(len(TIERS))]

    def swap_counts(self):
        """Per boundary (0 = S|A ... 4 = D|F), how many boundary checks swapped the two words (UI-31; counted
        from when this was added, and undo takes a swap back off)."""
        got = dict(self.db.execute("SELECT boundary, COUNT(*) FROM swaps GROUP BY boundary").fetchall())
        return [got.get(b, 0) for b in range(len(TIERS) - 1)]

    def actions_since(self, ts):
        """How many actions (placements, skips, duels, edits) were saved since time `ts`; undone ones do not
        count (undo removes them). For the quiet "+N today" in the status line (UI-15)."""
        return self.db.execute("SELECT COUNT(*) FROM history WHERE ts >= ?", (ts,)).fetchone()[0]

    # ---- anchors ------------------------------------------------------------
    def get_anchors(self):
        """The six anchor words as a list indexed by tier; an entry is None until it is set."""
        out = [None] * len(TIERS)
        for r in self.db.execute("SELECT tier, word FROM anchors"):
            out[r["tier"]] = r["word"]
        return out

    def set_anchors(self, words):
        """Replace the anchors (one word per tier) and move each anchor word into its tier."""
        self.db.execute("DELETE FROM anchors")
        for t, w in enumerate(words):
            self.db.execute("INSERT INTO anchors(tier, word) VALUES(?, ?)", (t, w))
            self.db.execute(
                "UPDATE words SET tier=?, rating=?, games=0 WHERE word=? AND (tier IS NULL OR tier!=?)",
                (t, tier_base(t), w, t),
            )
        self.db.commit()
        self._prog = None
        self.version += 1

    def _follow_anchors(self, before):
        """After a move (UI-40): an anchor word that left its tier hands the job to its neighbour there, the
        word ranked just below it if it moved down (or out of the tiers), just above if it moved up (the other
        side if there is none). A tier left with no other words keeps an empty slot. `before` are the moved
        words' rows from before the move. Returns (changes, anchors before) with changes as
        [(word, old tier, new tier, new anchor or None)], or ([], None) when no anchor moved."""
        anchors = self.get_anchors()
        changes = []
        for r in before:
            t = r["tier"]
            if t is None or anchors[t] != r["word"]:
                continue
            now = self.db.execute("SELECT tier FROM words WHERE word=?", (r["word"],)).fetchone()[0]
            if now == t:
                continue
            below = ("rating<=? ORDER BY rating DESC", "rating>? ORDER BY rating ASC")
            for cond in (below if now is None or now > t else below[::-1]):
                row = self.db.execute(f"SELECT word FROM words WHERE tier=? AND word!=? AND {cond} LIMIT 1",
                                      (t, r["word"], r["rating"])).fetchone()
                if row:
                    break
            new = row[0] if row else None
            changes.append((r["word"], t, now, new))
        if not changes:
            return [], None
        for _w, t, _now, new in changes:
            self.db.execute("DELETE FROM anchors WHERE tier=?", (t,))
            if new is not None:
                self.db.execute("INSERT INTO anchors(tier, word) VALUES(?, ?)", (t, new))
        return changes, anchors

    # ---- history / undo -------------------------------------------------------
    def _snap(self, words):
        """Copy the current rows of `words` (dicts) so an action can be undone later."""
        q = ",".join("?" * len(words))
        return [dict(r) for r in self.db.execute(f"SELECT * FROM words WHERE word IN ({q})", list(words))]

    def _push(self, before, comp_ids=(), conf_added=(), comps_deleted=(), conf_deleted=(), anchors=None):
        """Record one undoable action: the rows as they were, plus which comparisons/conflicts it added or removed
        and, when it changed them (UI-40), the anchors as they were."""
        payload = {
            "anchors": anchors,
            "before": before,
            "comp_ids": list(comp_ids),
            "conf_added": [list(p) for p in conf_added],
            "comps_deleted": list(comps_deleted),
            "conf_deleted": [list(p) for p in conf_deleted],
        }
        cur = self.db.execute(
            "INSERT INTO history(payload, ts) VALUES(?, ?)", (json.dumps(payload), time.time())
        )
        hid = cur.lastrowid
        if hid % 250 == 0:  # keep the most recent 5000 undo steps
            self.db.execute("DELETE FROM history WHERE id <= ?", (hid - 5000,))
        self.version += 1

    def undo(self):
        """Revert the most recent action. Returns the main word affected, or None."""
        row = self.db.execute("SELECT id, payload FROM history ORDER BY id DESC LIMIT 1").fetchone()
        if row is None:
            return None
        p = json.loads(row["payload"])
        now = {r["word"]: r for r in self._snap([r["word"] for r in p["before"]])} if p["before"] else {}
        for r in p["before"]:
            cur = now.get(r["word"])
            if cur is not None:
                self._tier_moved(cur, cur["tier"], r["tier"])
            # qkey is missing from history written by older versions; COALESCE keeps the current one.
            self.db.execute(
                "UPDATE words SET tier=?, rating=?, games=?, skips=?, qkey=COALESCE(?, qkey) WHERE word=?",
                (r["tier"], r["rating"], r["games"], r["skips"], r.get("qkey"), r["word"]),
            )
        for cid in p["comp_ids"]:
            self.db.execute("DELETE FROM comparisons WHERE id=?", (cid,))
            self.db.execute("DELETE FROM swaps WHERE comp_id=?", (cid,))
        for a, b in p["conf_added"]:
            self.db.execute("DELETE FROM conflicts WHERE a=? AND b=?", (a, b))
        for r in p["comps_deleted"]:
            self.db.execute(
                "INSERT OR REPLACE INTO comparisons(id, winner, loser, tie, kind, ts) VALUES(?,?,?,?,?,?)",
                (r["id"], r["winner"], r["loser"], r["tie"], r["kind"], r["ts"]),
            )
        for a, b in p["conf_deleted"]:
            self.db.execute("INSERT OR IGNORE INTO conflicts(a, b) VALUES(?, ?)", (a, b))
        if p.get("anchors") is not None:                 # an anchor had followed its tier: put them back
            self.db.execute("DELETE FROM anchors")
            for t, w in enumerate(p["anchors"]):
                if w is not None:
                    self.db.execute("INSERT INTO anchors(tier, word) VALUES(?, ?)", (t, w))
        self.db.execute("DELETE FROM history WHERE id=?", (row["id"],))
        self.db.commit()
        self.version += 1
        return p["before"][0]["word"] if p["before"] else ""

    # ---- placement ----------------------------------------------------------------
    def place(self, word, tier, comps=()):
        """Put `word` in `tier`. comps = [(anchor_word, 'a'|'b'|'tie')] where 'a' means word won. Moving an anchor
        word hands its old tier's anchor on (UI-40); returns those changes (see _follow_anchors)."""
        before = self._snap([word])
        ids = []
        now = time.time()
        for anchor, res in comps:
            if res == "a":
                w, l, tie = word, anchor, 0
            elif res == "b":
                w, l, tie = anchor, word, 0
            else:
                w, l, tie = word, anchor, 1
            cur = self.db.execute(
                "INSERT INTO comparisons(winner, loser, tie, kind, ts) VALUES(?,?,?,?,?)",
                (w, l, tie, "anchor", now),
            )
            ids.append(cur.lastrowid)
        self.db.execute(
            "UPDATE words SET tier=?, rating=?, games=0 WHERE word=?", (tier, tier_base(tier), word)
        )
        if before:
            self._tier_moved(before[0], before[0]["tier"], tier)
        changes, anchors = self._follow_anchors(before)
        self._push(before, comp_ids=ids, anchors=anchors)
        self.db.commit()
        return changes

    def unplace(self, word):
        """Send a placed word back to the front of the queue so it is judged again next."""
        before = self._snap([word])
        # Back to the front of the queue so the word is re-judged next.
        front = self.db.execute(
            "SELECT MIN(qkey) FROM words WHERE tier IS NULL AND skips=0 AND qkey < 1e17").fetchone()[0]
        front = (front if front is not None else 0.0) - 1.0
        self.db.execute(
            "UPDATE words SET tier=NULL, rating=1500, games=0, skips=0, qkey=? WHERE word=?", (front, word))
        if before:
            self._tier_moved(before[0], before[0]["tier"], None)
        self._push(before)
        self.db.commit()

    def skip(self, word):
        """"Don't know / later": count a skip, which moves the word behind every fresh word."""
        before = self._snap([word])
        self.db.execute("UPDATE words SET skips = skips + 1 WHERE word=?", (word,))
        self._push(before)
        self.db.commit()

    # ---- comparisons ----------------------------------------------------------------
    def _contradicts(self, w, l):
        """True if earlier decisive answers already say l beats w (directly or via one word)."""
        if self.db.execute(
            "SELECT 1 FROM comparisons WHERE winner=? AND loser=? AND tie=0 LIMIT 1", (l, w)
        ).fetchone():
            return True
        return (
            self.db.execute(
                "SELECT 1 FROM comparisons c1 JOIN comparisons c2 ON c1.loser = c2.winner"
                " WHERE c1.winner=? AND c2.loser=? AND c1.tie=0 AND c2.tie=0 LIMIT 1",
                (l, w),
            ).fetchone()
            is not None
        )

    @staticmethod
    def _k(games):
        """Elo K-factor: big steps for new words, shrinking to 10 as a word accumulates duels."""
        return max(10.0, 40.0 / (1.0 + games / 6.0))

    def record_comparison(self, a, b, result, kind):
        """result: 'a' (a wins) | 'b' (b wins) | 'tie'. kind: within | boundary | conflict."""
        ra, rb = self.get_word(a), self.get_word(b)
        before = [dict(ra), dict(rb)]
        if result == "b":
            w, l, tie = b, a, 0
        elif result == "a":
            w, l, tie = a, b, 0
        else:
            w, l, tie = a, b, 1
        info = {"conflict": False, "swapped": None}
        comps_deleted, conf_deleted, conf_added = [], [], []
        pair_clause = "(winner=? AND loser=?) OR (winner=? AND loser=?)"

        if kind == "conflict":
            # Re-judging: the new answer replaces earlier direct answers for this pair.
            rows = self.db.execute(f"SELECT * FROM comparisons WHERE {pair_clause}", (a, b, b, a)).fetchall()
            comps_deleted = [dict(r) for r in rows]
            self.db.execute(f"DELETE FROM comparisons WHERE {pair_clause}", (a, b, b, a))
            for r in self.db.execute(
                "SELECT a, b FROM conflicts WHERE (a=? AND b=?) OR (a=? AND b=?)", (a, b, b, a)
            ).fetchall():
                conf_deleted.append([r["a"], r["b"]])
            self.db.execute(
                "DELETE FROM conflicts WHERE (a=? AND b=?) OR (a=? AND b=?)", (a, b, b, a)
            )
        elif not tie and self._contradicts(w, l):
            pair = sorted([a, b])
            if not self.db.execute("SELECT 1 FROM conflicts WHERE a=? AND b=?", pair).fetchone():
                self.db.execute("INSERT INTO conflicts(a, b) VALUES(?, ?)", pair)
                conf_added.append(pair)
            info["conflict"] = True

        cur = self.db.execute(
            "INSERT INTO comparisons(winner, loser, tie, kind, ts) VALUES(?,?,?,?,?)",
            (w, l, tie, kind, time.time()),
        )
        comp_id = cur.lastrowid

        if ra["tier"] is not None and ra["tier"] == rb["tier"]:
            # Same tier: Elo update (shrinking K as a word accumulates duels).
            ea = 1.0 / (1.0 + 10 ** ((rb["rating"] - ra["rating"]) / 400.0))
            sa = 1.0 if result == "a" else 0.0 if result == "b" else 0.5
            na = ra["rating"] + self._k(ra["games"]) * (sa - ea)
            nb = rb["rating"] + self._k(rb["games"]) * ((1.0 - sa) - (1.0 - ea))
            self.db.execute("UPDATE words SET rating=?, games=games+1 WHERE word=?", (na, a))
            self.db.execute("UPDATE words SET rating=?, games=games+1 WHERE word=?", (nb, b))
        elif (
            kind == "boundary"
            and not tie
            and ra["tier"] is not None
            and rb["tier"] is not None
        ):
            rw, rl = (ra, rb) if w == a else (rb, ra)
            if rw["tier"] > rl["tier"]:  # winner lives in the lower tier -> swap tiers
                self.db.execute(
                    "UPDATE words SET tier=?, rating=?, games=games+1 WHERE word=?",
                    (rl["tier"], rl["rating"] + 1.0, w),
                )
                self.db.execute(
                    "UPDATE words SET tier=?, rating=?, games=games+1 WHERE word=?",
                    (rw["tier"], rw["rating"] - 1.0, l),
                )
                info["swapped"] = (w, rl["tier"], l, rw["tier"])
                self._tier_moved(rw, rw["tier"], rl["tier"])
                self._tier_moved(rl, rl["tier"], rw["tier"])
                self.db.execute("INSERT INTO swaps(comp_id, boundary) VALUES(?, ?)", (comp_id, rl["tier"]))
            else:
                self.db.execute("UPDATE words SET games=games+1 WHERE word IN (?, ?)", (a, b))

        info["anchors"], anchors = self._follow_anchors(before)
        self._push(
            before,
            comp_ids=[comp_id],
            conf_added=conf_added,
            comps_deleted=comps_deleted,
            conf_deleted=conf_deleted,
            anchors=anchors,
        )
        self.db.commit()
        return info

    # ---- pair selection ---------------------------------------------------------------
    def _faced_set(self, word):
        """Every word that `word` has already been compared with (either side of a duel)."""
        return {
            r[0]
            for r in self.db.execute(
                "SELECT loser FROM comparisons WHERE winner=? UNION SELECT winner FROM comparisons WHERE loser=?",
                (word, word),
            )
        }

    def _faced(self, a, b):
        """True if a and b have already been compared, in either order."""
        return (
            self.db.execute(
                "SELECT 1 FROM comparisons WHERE (winner=? AND loser=?) OR (winner=? AND loser=?) LIMIT 1",
                (a, b, b, a),
            ).fetchone()
            is not None
        )

    def pick_within(self, tier=None, focus=None):
        """Adaptive pairing: least-dueled word vs nearest-rated opponent it hasn't faced."""
        counts = self.tier_counts()
        eligible = [t for t, n in counts.items() if n >= 2]
        if not eligible or (tier is not None and tier not in eligible):
            return None
        if focus:
            r = self.get_word(focus)
            if r is None or r["tier"] is None or r["tier"] not in eligible:
                return None
            seeds = [r]
        else:
            # the least-dueled words, from the tiers that have them: tier by tier, so the (tier, games) index
            # answers it (over all tiers at once it sorted every placed word, ~15 ms at 300k)
            seeds = []
            for t in ([tier] if tier is not None else eligible):
                seeds += self.db.execute("SELECT * FROM words WHERE tier=? ORDER BY games ASC, RANDOM() LIMIT 40",
                                         (t,)).fetchall()
            seeds.sort(key=lambda r: (r["games"], random.random()))
            seeds = seeds[:40]
            random.shuffle(seeds)
        for a in seeds:
            faced = self._faced_set(a["word"])
            for c in self._nearest(a, 80):
                if c["word"] not in faced:
                    return a["word"], c["word"], a["tier"]
        return None

    def _nearest(self, a, k):
        """Up to k words of a's tier with the ratings nearest to a's, nearest first, ties in random order.
        Read from the (tier, rating) index up and down from a's rating (sorting the whole tier by distance
        took ~25 ms at 300k words). A big run of equal ratings (new words all start alike) is entered at a
        random point, so the same few words are not always first."""
        t, r, w = a["tier"], a["rating"], a["word"]
        same = self.db.execute("SELECT COUNT(*) FROM words WHERE tier=? AND rating=?", (t, r)).fetchone()[0]
        skip = random.randrange(same - k) if same > k else 0
        rows = self.db.execute("SELECT * FROM words WHERE tier=? AND rating=? AND word!=? LIMIT ? OFFSET ?",
                               (t, r, w, k, skip)).fetchall()
        if len(rows) < k:
            rows += self.db.execute("SELECT * FROM words WHERE tier=? AND rating>? ORDER BY rating LIMIT ?",
                                    (t, r, k)).fetchall()
            rows += self.db.execute("SELECT * FROM words WHERE tier=? AND rating<? ORDER BY rating DESC LIMIT ?",
                                    (t, r, k)).fetchall()
        rows.sort(key=lambda c: (abs(c["rating"] - r), random.random()))
        return rows[:k]

    BOUNDARY_POOL = 30      # words per side a boundary pair is drawn from (at most 900 pairs)

    def pick_boundary(self, boundary=None):
        """Weakest words of tier t vs strongest of tier t+1. Returns (higher, lower, t)."""
        order = [boundary] if boundary is not None else random.sample(range(len(TIERS) - 1), len(TIERS) - 1)
        counts = self.tier_counts()
        for t in order:
            n_hi, n_lo = counts.get(t, 0), counts.get(t + 1, 0)
            if n_hi < 1 or n_lo < 1:
                continue
            # the weakest few of the upper tier against the strongest few of the lower one. Capped: 5% of a
            # big tier was 5,000 words a side, 25 million pairs held in memory (gigabytes, ~40 s) to try 60
            k = min(self.BOUNDARY_POOL, max(5, int(0.05 * min(n_hi, n_lo))))
            hi = [r[0] for r in self.db.execute(
                "SELECT word FROM words WHERE tier=? ORDER BY rating ASC, RANDOM() LIMIT ?", (t, k))]
            lo = [r[0] for r in self.db.execute(
                "SELECT word FROM words WHERE tier=? ORDER BY rating DESC, RANDOM() LIMIT ?", (t + 1, k))]
            pairs = [(x, y) for x in hi for y in lo]
            random.shuffle(pairs)
            for x, y in pairs[:60]:
                if not self._faced(x, y):
                    return x, y, t
        return None

    def pick_conflict(self):
        """A random flagged pair (a, b) to re-judge, or None when there are no conflicts."""
        r = self.db.execute("SELECT a, b FROM conflicts ORDER BY RANDOM() LIMIT 1").fetchone()
        return (r["a"], r["b"]) if r else None

    # ---- listing / export ------------------------------------------------------------------
    SORTS = ("Default", "A-Z", "Frequency", "Rating", "Duels")
    # each sort's natural order (reverse=True flips every part of it); Default is per filter, below
    _ORDERS = {"A-Z": "word ASC", "Frequency": "rank ASC", "Rating": "rating DESC, rank ASC",
               "Duels": "games DESC, rank ASC"}

    KIND_FILTERS = {label: bit for _, label, bit in KINDS}

    def list_words(self, text="", tier_filter="All placed", sort="Default", limit=3000, offset=0,
                   with_total=True, reverse=False):
        """One page of words. Default order = tier/rating for placed words, queue order for unplaced; A-Z,
        Frequency (commonest first), Rating and Duels (highest first); `reverse` turns the order round (M-7)."""
        where, args = [], []
        if tier_filter == "Unplaced":
            where.append("tier IS NULL")
            default_order = "skips ASC, qkey ASC, rank ASC"
        else:
            where.append("tier IS NOT NULL")
            default_order = "tier ASC, rating DESC, games DESC, rank ASC"
            if tier_filter.startswith("Tier "):
                where.append("tier=?")
                args.append(TIERS.index(tier_filter[5:]))
            elif tier_filter == "Obscene words":               # ST-6: a kind of word (placed ones)
                where.append("obscene=1")
            elif tier_filter in self.KIND_FILTERS:
                where.append("(COALESCE(kinds, 16) & ?) != 0")
                args.append(self.KIND_FILTERS[tier_filter])
        order = self._ORDERS.get(sort, default_order)
        if reverse:
            order = ", ".join(part.replace(" ASC", " DESC") if part.endswith(" ASC") else part.replace(" DESC", " ASC")
                              for part in order.split(", "))
        if text:
            where.append("word LIKE ?")
            args.append("%" + text.replace("%", "").replace("_", "") + "%")
        clause = " AND ".join(where)
        rows = self.db.execute(
            f"SELECT word, tier, rating, games, skips, rank, pen FROM words WHERE {clause}"
            f" ORDER BY {order} LIMIT ? OFFSET ?",
            args + [limit, offset],
        ).fetchall()
        total = None
        if with_total:
            if offset == 0 and len(rows) < limit:
                total = len(rows)  # a short first page is everything: skip the extra full scan
            else:
                total = self.db.execute(f"SELECT COUNT(*) FROM words WHERE {clause}", args).fetchone()[0]
        return rows, total

    def export_rows(self):
        """Placed words, best first within each tier, for File > Export."""
        return self.db.execute(
            "SELECT word, tier, rating, games FROM words WHERE tier IS NOT NULL"
            " ORDER BY tier, rating DESC, games DESC, rank"
        ).fetchall()

    def skipped_words(self):
        """Words that were skipped and are still unplaced, in frequency order."""
        return [r[0] for r in self.db.execute(
            "SELECT word FROM words WHERE tier IS NULL AND skips > 0 ORDER BY rank")]

    # ---- bringing in earlier progress ---------------------------------------------------------
    def backup(self, tag="backup"):
        """Consistent copy of this save file next to it (.bak, so it is never mistaken for a save)."""
        self.db.commit()
        dest = f"{self.path}.{tag}-{time.strftime('%Y%m%d-%H%M%S')}.bak"
        out = sqlite3.connect(dest)
        try:
            self.db.backup(out)
        finally:
            out.close()
        return dest

    @staticmethod
    def _read_save(path):
        """(progress rows, past comparisons) from another save file, opened read-only."""
        con = sqlite3.connect(Path(os.path.abspath(path)).as_uri() + "?mode=ro", uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        try:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "words" not in tables:
                raise ValueError("that file is not a tier list save file")
            rows = [dict(r) for r in con.execute(
                "SELECT word, tier, rating, games, skips, rank FROM words WHERE tier IS NOT NULL OR skips > 0")]
            comps = ([tuple(r) for r in con.execute("SELECT winner, loser, tie, kind, ts FROM comparisons")]
                     if "comparisons" in tables else [])
        finally:
            con.close()
        return rows, comps

    @staticmethod
    def parse_export(path):
        """Progress rows from a file made by File > Export (.csv, or the .txt/.md listing)."""
        rows = []

        def row(word, tier, rating=None, games=0, skips=0):
            return {"word": word, "tier": tier, "rating": rating, "games": games, "skips": skips, "rank": 0}

        if path.lower().endswith(".csv"):
            import csv

            def num(r, key, cast, default=None):
                try:
                    return cast(r.get(key))
                except (TypeError, ValueError):
                    return default

            with open(path, newline="", encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    word, t = (r.get("word") or "").strip().lower(), (r.get("tier") or "").strip().upper()
                    if not word:
                        continue
                    if t == "?":
                        rows.append(row(word, None, skips=1))
                    elif t in TIERS:
                        rows.append(row(word, TIERS.index(t), num(r, "rating", float), num(r, "duels", int, 0)))
            return rows
        tier, in_skipped = None, False
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                m = re.match(r"^(?:#+\s*)?([SABCDF]) tier\b", line)
                if m:
                    tier, in_skipped = TIERS.index(m.group(1)), False
                    continue
                if re.match(r"^(?:#+\s*)?Skipped\b", line):
                    tier, in_skipped = None, True
                    continue
                if in_skipped:
                    rows += [row(w.strip().lower(), None, skips=1) for w in line.split(",") if w.strip()]
                    continue
                m = re.match(r"^\d+\.\s+(.+)$", line)
                if m and tier is not None:
                    rows.append(row(m.group(1).strip().lower(), tier))
        # The listing is best-first within each tier: turn that order back into ratings.
        for t in range(len(TIERS)):
            grp = [r for r in rows if r["tier"] == t]
            for i, r in enumerate(grp):
                r["rating"] = tier_base(t) + 60.0 * (1.0 - 2.0 * i / max(len(grp) - 1, 1))
        return rows

    def _merge_row(self, r, res):
        """Fold one incoming progress row into this list and update the tallies in `res`. Never overwrites a placed word."""
        word, tier = r["word"], r["tier"]
        cur = self.get_word(word)
        if tier is not None and 0 <= tier < len(TIERS):
            rating = tier_base(tier) if r.get("rating") is None else float(r["rating"])
            games = int(r.get("games") or 0)
            if cur is None:        # a word this list does not have (e.g. from an older, smaller word list)
                self.db.execute(
                    "INSERT INTO words(word, rank, tier, rating, games, qkey) VALUES(?,?,?,?,?,1e18)",
                    (word, 10_000_000 + int(r.get("rank") or 0), tier, rating, games))
                res["added"] += 1
                res["placed"] += 1
            elif cur["tier"] is None:
                self.db.execute("UPDATE words SET tier=?, rating=?, games=? WHERE word=?",
                                (tier, rating, games, word))
                res["placed"] += 1
            elif cur["tier"] == tier:
                res["same"] += 1
            else:
                res["differs"] += 1
        elif tier is None and int(r.get("skips") or 0) > 0 and cur is not None \
                and cur["tier"] is None and cur["skips"] == 0:
            self.db.execute("UPDATE words SET skips=? WHERE word=?", (int(r["skips"]), word))
            res["skipped"] += 1

    def merge(self, path, backup=True):
        """Bring progress from another save file, or from an Export, into this list.

        Only fills in what is still undecided here: a word already placed in this list keeps its
        tier, so nothing done here is overwritten, and the other file is never changed. Words
        placed there but missing here are added. Returns a summary dict.
        """
        if os.path.realpath(path) == os.path.realpath(self.path):
            raise ValueError("that is the save file you are already using")
        with open(path, "rb") as f:
            is_db = f.read(16).startswith(b"SQLite format 3")
        rows, comps = self._read_save(path) if is_db else (self.parse_export(path), [])
        res = {"placed": 0, "skipped": 0, "added": 0, "same": 0, "differs": 0, "comparisons": 0, "backup": None}
        if backup:
            res["backup"] = self.backup("before-merge")
        try:
            for r in rows:
                self._merge_row(r, res)
            have = {(w, l) for w, l in self.db.execute("SELECT winner, loser FROM comparisons")}
            for w, l, tie, kind, ts in comps:
                if (w, l) not in have and self.has_word(w) and self.has_word(l):
                    self.db.execute(
                        "INSERT INTO comparisons(winner, loser, tie, kind, ts) VALUES(?,?,?,?,?)",
                        (w, l, tie, kind, ts))
                    have.add((w, l))
                    res["comparisons"] += 1
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self._total = None
        self._prog = None
        self.version += 1
        return res
