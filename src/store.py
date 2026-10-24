"""The save file: every read and write of the SQLite database goes through Store.

Nothing here imports tkinter, so the whole data layer is testable without a window.

Data model (see SCHEMA below)
    words        one row per dictionary word. tier is NULL while a word is unplaced, else 0..5
                 (S..F). rating/games are the Elo score and duel count used inside a tier.
                 skips counts "don't know / later" presses. qkey is the seeded queue key (lower =
                 comes up sooner); rank is the frequency rank (1 = most common); pen is the
                 compound-word class (0 normal, 1 closed compound, 2 hyphenated / multi-word).
                 kinds: its parts of speech (constants.KINDS bits; NULL = not known); rude: the kinds of its
                 meanings by the rules (rudeness.KIND_BITS: 1 clean, then one bit per rude kind; NULL = no
                 rude meaning found), obscene: 1 if the whole word is smeared while censoring (OB-6); out: 1
                 if "How words are dealt" leaves it out of the queue (ST-6; kept up to date by set_deal).
    comparisons  every answer ever given (winner, loser, tie, kind). Used to avoid repeating a
                 duel and to detect contradictions.
    conflicts    pairs whose answers contradict each other, waiting to be re-judged.
    swaps        boundary checks that swapped their two words (per boundary; still counted, UI-31).
    anchors      the one reference word per tier used by "compare to anchors".
    defs         cached definitions.        meta  small key/value settings (seed, mode, ...).
    rude         the meanings of the words Wiktionary has any sign of rudeness for (and their forms), kept
                 compact for the rules (rudeness.compact), and `smeared`: the keys (first rudeness.GLOSS_KEY
                 characters) of those smeared in the definitions while censoring (JSON, or NULL).
                 Its meta keys: rude_senses "1" once kept, rude_done what words.rude was scored from
                 (wordsource.rude_version), rude_tried when the background read last started; the dealing
                 ones: deal_kinds, deal_obscene, deal_rude (rudeness.KIND_BITS), censor.
    history      one JSON row per action, so Undo works and survives restarts.

Conventions
    * Every public method that changes data commits before returning (a crash loses nothing).
    * Store.version goes up on every change; open windows compare it to know when to refresh.
    * Methods starting with an underscore are internal helpers.
"""
import bisect
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import sqlite3
import time

from obscene import RUDE_KINDS, TICKED, on_list
from rudeness import KIND_BITS, LISTED
from constants import (ALL_KINDS, KINDS, PEN_UNITS, QUEUE_DEFAULTS, QUEUE_SHAPES, SHELF_SOFT, SHELF_SPINES, SHELF_ZIPF, SHELF_ZONE_RANKS,
                       SHELF_ZONES, TIERS, tier_base)

_RUDE_BITS = sum(KIND_BITS[k] for k in RUDE_KINDS)
_TICKED_BITS = sum(KIND_BITS[k] for k in TICKED)


# --------------------------------------------------------------------------
# Schema. All statements are IF NOT EXISTS, so opening an old save file is safe;
# columns added in later versions are migrated in Store.__init__.
# --------------------------------------------------------------------------
# The words table's indexes (name, what it indexes), made when a save opens. Big writes take them away and build them
# again afterwards (Store.bulk_write): updating a dozen and a half indexes row by row doubled the time.
WORD_INDEXES = (
    # the queue (next_unplaced): the words dealt (out=0) in order, even when nearly all are left out
    ("idx_words_q3", "words(tier, out, skips, qkey)"),
    ("idx_words_obscene", "words(word) WHERE obscene=1"),
    ("idx_words_tg", "words(tier, games)"),                     # settled_shares
    ("idx_words_shelf", "words(rank, tier, freq)"),             # shelf_layout(), the shelf's totals
    # nearest ratings in a tier (pick_within), a tier's weakest / strongest (pick_boundary), Browse's order
    ("idx_words_tr", "words(tier, rating)"),
    # Browse's A-Z / Z-A and Frequency over the placed words only: with a few thousand placed out of a million,
    # walking every word in order to find them took ~200 ms (and froze the sort arrow's fill). The shelf counts its
    # placed words per spine from idx_placed_shelf too (a few thousand placed: a few ms, not a pass over a million)
    ("idx_placed_word", "words(word) WHERE tier IS NOT NULL"),
    ("idx_placed_shelf", "words(rank, tier, freq) WHERE tier IS NOT NULL"),
    # Browse's sorts, read in order from an index instead of sorting every row (0.2-0.9 s with 300k placed of a
    # million; built once on the first open of a big save, ~2 s): the placed words' Default (tier, best first;
    # turned round, the index read backwards), Rating and Duels; the unplaced words' queue and frequency order
    ("idx_placed_order", "words(tier, rating DESC, games DESC, rank) WHERE tier IS NOT NULL"),
    ("idx_placed_rating", "words(rating DESC, rank) WHERE tier IS NOT NULL"),
    ("idx_placed_games", "words(games DESC, rank) WHERE tier IS NOT NULL"),
    ("idx_unplaced_queue", "words(skips, qkey, rank) WHERE tier IS NULL"),
    ("idx_unplaced_rank", "words(rank) WHERE tier IS NULL"),
    ("idx_unplaced_word", "words(word) WHERE tier IS NULL"),
    # How words are dealt's counts per kind (kind_counts), over every word
    ("idx_words_kinds", "words(kinds, rude)"),
    # (a kind's or the obscene words' count among the placed ones, read from the index, not every row)
    ("idx_placed_kinds", "words(kinds, rude) WHERE tier IS NOT NULL"),
    # the header's "N skipped": counting them among a million unplaced words took 60 ms on every refresh
    ("idx_words_skipped", "words(word) WHERE tier IS NULL AND skips > 0"),
)
BULK_ROWS = 100000      # a write of more rows than this goes through bulk_write

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
    out INTEGER NOT NULL DEFAULT 0,
    rude INTEGER,
    rude_main INTEGER
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
CREATE TABLE IF NOT EXISTS rude(word TEXT PRIMARY KEY, senses TEXT NOT NULL, smeared TEXT);
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
        if "rude" not in cols:                   # OB-6: the kinds of its meanings, by the rules (rudeness.py)
            self.db.execute("ALTER TABLE words ADD COLUMN rude INTEGER")
            self.db.execute("UPDATE words SET rude=? WHERE obscene=1", (KIND_BITS["swear"],))   # (until scored)
        if "rude_main" not in cols:              # what a word smeared whole mostly is (rudeness.main_kind), a bit
            self.db.execute("ALTER TABLE words ADD COLUMN rude_main INTEGER")
        self.db.execute("DROP INDEX IF EXISTS idx_words_queue")
        self.db.execute("DROP INDEX IF EXISTS idx_words_q2")
        self.db.execute("DROP INDEX IF EXISTS idx_placed_rank")      # (now idx_placed_shelf, which also counts the shelf)
        for name, spec in WORD_INDEXES:
            self.db.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {spec}")
        self.db.commit()
        self.version = 0  # bumps on every change; lets open windows know when to refresh
        self._total = None
        self._prog = None    # the shelf's tallies (shelf()), counted once, then kept up to date by each change
        self._counts = None  # placed words per tier (tier_counts()), the same way
        self._obscene = None     # the obscene words (obscene_words()), read once
        self._bulk = set()       # the indexes a bulk_write has taken away for now

    def close(self):
        """Flush and close the database; safe to call twice."""
        try:
            self.db.commit()
            self.db.close()
        except sqlite3.Error:
            pass

    @contextlib.contextmanager
    def bulk_write(self, names=None):
        """For a write of many rows (over BULK_ROWS): the words table's indexes (`names`, else every one) are taken
        away while it runs and built again once at the end, which commits (a million new words: 19 s -> 10 s). A
        failed write is rolled back first. Nests: an inner one leaves alone what an outer one took. If the program
        stops in between, opening the save builds the missing indexes again (Store.__init__)."""
        gone = [(n, spec) for n, spec in WORD_INDEXES if (names is None or n in names) and n not in self._bulk]
        self._bulk.update(n for n, _ in gone)
        for n, _ in gone:
            self.db.execute(f"DROP INDEX IF EXISTS {n}")
        try:
            yield
        except BaseException:
            self.db.rollback()
            raise
        finally:
            for n, spec in gone:
                self.db.execute(f"CREATE INDEX IF NOT EXISTS {n} ON {spec}")
            self._bulk.difference_update(n for n, _ in gone)
            self.db.commit()

    # ---- meta / defs ----------------------------------------------------
    def get_meta(self, key, default=None):
        """Read a setting from the meta table (always returned as text), or `default`."""
        r = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def meta_number(self, key, default, cast=float, lo=None, hi=None):
        """A numeric setting: `cast` of its text (float or int), kept within lo..hi; `default` when it is unset or
        not a number (a hand-edited or damaged save)."""
        try:
            value = cast(self.get_meta(key, default))
        except (TypeError, ValueError):
            value = cast(default)
        if lo is not None:
            value = max(lo, value)
        return min(hi, value) if hi is not None else value

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
        words = list(words)
        with self.bulk_write() if len(words) > BULK_ROWS else contextlib.nullcontext():
            self.db.executemany(
                "INSERT INTO words(word, rank, rating, qkey) VALUES (?, ?, 1500, ?)"
                " ON CONFLICT(word) DO UPDATE SET rank=excluded.rank",
                ((w, i, 1e18 + i) for i, w in enumerate(words)),
            )
        self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('pen_done', '0')")
        self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('freq_done', '0')")
        self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('rude_done', '0')")   # (new words: OB-6)
        self._forget_shelf_totals()
        self.db.commit()
        self._total = None
        self._forget_tallies()
        self.version += 1

    def add_word(self, word):
        """Add one word the list did not have (UI-51: looked up and added by hand), at the very end of it: the
        rarest rank, the back of the queue. Unlike insert_words, nothing else is re-ranked or redone."""
        rank = self.db.execute("SELECT COALESCE(MAX(rank), -1) + 1 FROM words").fetchone()[0]
        self.db.execute("INSERT OR IGNORE INTO words(word, rank, rating, qkey) VALUES (?, ?, 1500, 1e18)", (word, rank))
        listed = on_list(word)                       # (no meanings to read for it: the hand-picked list)
        self.db.execute("UPDATE words SET rude=?, obscene=?, rude_main=? WHERE word=?",
                        (LISTED[0] if listed else None, int(listed), KIND_BITS[LISTED[3]] if listed else None, word))
        sql, args = self._out_sql()
        self.db.execute(f"UPDATE words SET out = {sql} WHERE word=?", (*args, word))
        self._obscene = None
        self._forget_shelf_totals()
        self.db.commit()
        self._total = None
        self._forget_tallies()
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
        spread = self.meta_number("qspread", QUEUE_DEFAULTS["qspread"], lo=100.0)
        comp = self.meta_number("qcompound", QUEUE_DEFAULTS["qcompound"], lo=0.0, hi=10.0)
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
        # (the two indexes holding qkey are built again afterwards: much faster than updating them row by row)
        with self.bulk_write(("idx_words_q3", "idx_unplaced_queue")) if total > BULK_ROWS else contextlib.nullcontext():
            batch = []
            for n, (word, rank, pen) in enumerate(rows, 1):
                if strict:
                    batch.append((float(rank), word))
                else:
                    x = int.from_bytes(hashlib.blake2b(word.encode("utf-8"), digest_size=8, key=salt).digest(), "big")
                    u = ((x >> 12) + 0.5) / 4503599627370496.0  # strictly inside (0, 1)
                    e = -math.log(u) or 1e-300
                    z = (rank + PEN_UNITS.get(pen, 0.0) * comp * spread) / spread
                    batch.append((math.log(e) + (0.5 * z * z if gauss else z), word))
                if len(batch) >= 50000 or n == total:
                    self.db.executemany("UPDATE words SET qkey=? WHERE word=?", batch)
                    batch = []
        self.db.commit()
        self.version += 1

    # ---- how words are dealt (ST-6): kinds of words, rude ones (OB-5, OB-6) ---------------------------------
    def deal_settings(self):
        """{"kinds": the ticked kinds (constants.KINDS bits), "obscene": "Obscene words" ticked, "rude": the ticked
        rude kinds under it (rudeness.KIND_BITS), "censor": censored words shown smeared}. Every kind of word is
        ticked to start with; "Obscene words" is not (with obscene.TICKED ticked under it for when it is), and
        nothing is censored."""
        kinds = self.meta_number("deal_kinds", ALL_KINDS, int) & ALL_KINDS
        rude = self.meta_number("deal_rude", _TICKED_BITS, int) & _RUDE_BITS
        return {"kinds": kinds, "obscene": self.get_meta("deal_obscene", "0") == "1", "rude": rude,
                "censor": self.get_meta("censor", "0") == "1"}

    def _out_sql(self):
        """(SQL for words.out, its arguments): a word with a meaning of a ticked rude kind is dealt; one with no clean
        meaning (only rude ones) is left out otherwise; any other word is dealt while one of its kinds of word is
        (unknown kinds count as "other")."""
        d = self.deal_settings()
        ticked = d["rude"] if d["obscene"] else 0
        return ("CASE WHEN (COALESCE(rude, 1) & ?) != 0 THEN 0 WHEN (COALESCE(rude, 1) & 1) = 0 THEN 1"
                " WHEN (COALESCE(kinds, 16) & ?) != 0 THEN 0 ELSE 1 END"), (ticked, d["kinds"])

    def set_deal(self, kinds=None, obscene=None, rude=None):
        """Save which words are dealt and mark the rest out of the queue (one pass over the list: ~1 s with a
        million words, so the dialog runs it on a worker thread). Nothing is deleted or unplaced."""
        if kinds is not None:
            self.set_meta("deal_kinds", int(kinds) & ALL_KINDS)
        if obscene is not None:
            self.set_meta("deal_obscene", "1" if obscene else "0")
        if rude is not None:
            self.set_meta("deal_rude", int(rude) & _RUDE_BITS)
        sql, args = self._out_sql()
        self.db.execute(f"UPDATE words SET out = {sql} WHERE out != {sql}", args * 2)
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

    @staticmethod
    def _stepped(steps, chunk):
        """A writer's steps as a generator to step through (`chunk`: App writes a background result a little at a
        time, between frames), or all of them at once."""
        if chunk:
            return steps
        for _ in steps:
            pass

    def save_rude_senses(self, saved, chunk=None):
        """Keep {word: its meanings as compact JSON (rudeness.compact)} for the rules (the words the Wiktionary
        download had any sign of rudeness for, and their forms), in place of what was kept before. `chunk`: see
        _stepped."""
        def steps():
            items = list(saved.items())
            self.db.execute("DELETE FROM rude")
            for i in range(0, len(items), chunk or len(items) or 1):
                self.db.executemany("INSERT OR REPLACE INTO rude(word, senses) VALUES(?, ?)", items[i:i + (chunk or len(items))])
                self.db.commit()
                yield
            self.set_meta("rude_senses", "1")
        return self._stepped(steps(), chunk)

    def rude_senses(self):
        """{word: compact JSON} as save_rude_senses kept them, for the words in the list."""
        return dict(self.db.execute("SELECT r.word, r.senses FROM rude r JOIN words w ON w.word = r.word"))

    def set_rude(self, found, chunk=None):
        """Save what the rules found: {word: (rudeness.KIND_BITS of its meanings, smeared whole while censoring,
        [the keys of its meanings smeared in the definitions], its main kind (rudeness.main_kind) or None)}; every
        other word is clean (NULL). Each word's place in the queue follows at once. `chunk`: see _stepped."""
        def steps():
            old = [r[0] for r in self.db.execute("SELECT word FROM words WHERE rude IS NOT NULL OR obscene=1")]
            rows = [(w, None, False, None, None) for w in old if w not in found]
            rows += [(w, v[0], v[1], v[3] if len(v) > 3 else None, json.dumps(v[2]) if v[2] else None)
                     for w, v in found.items()]
            for i in range(0, len(rows), chunk or len(rows) or 1):
                part = rows[i:i + (chunk or len(rows))]
                sql, args = self._out_sql()          # (read each time: the settings may change between steps)
                self.db.executemany("UPDATE words SET rude=?, obscene=?, rude_main=? WHERE word=?",
                                    ((b, int(bool(wh)), KIND_BITS.get(k), w) for w, b, wh, k, _m in part))
                self.db.executemany(f"UPDATE words SET out = {sql} WHERE word=?", ((*args, w) for w, *_ in part))
                self.db.executemany("UPDATE rude SET smeared=NULL WHERE word=?", ((w,) for w, *_r, m in part if not m))
                self.db.executemany("INSERT INTO rude(word, senses, smeared) VALUES(?, '[]', ?) ON CONFLICT(word)"
                                    " DO UPDATE SET smeared=excluded.smeared", ((w, m) for w, *_r, m in part if m))
                self.db.commit()
                self._obscene = None
                self.version += 1
                yield
        return self._stepped(steps(), chunk)

    def rude_kind(self, word):
        """What a word smeared whole mostly is ("sexual", rudeness.main_kind), or None: the card shows it faintly
        above the word (asked for)."""
        r = self.db.execute("SELECT rude_main FROM words WHERE word=? AND obscene=1", (word,)).fetchone()
        return next((k for k, bit in KIND_BITS.items() if r and r[0] == bit), None)

    def smeared_meanings(self, word):
        """The keys (rudeness.GLOSS_KEY characters) of `word`'s meanings smeared while censoring, or []."""
        r = self.db.execute("SELECT smeared FROM rude WHERE word=?", (word,)).fetchone()
        return json.loads(r[0]) if r and r[0] else []

    def obscene_words(self):
        """The words smeared whole while censoring (a few thousand), read once (partial index)."""
        if self._obscene is None:
            self._obscene = {r[0] for r in self.db.execute("SELECT word FROM words WHERE obscene=1")}
        return self._obscene

    def censored(self, word):
        """True if `word` is to be shown smeared or masked (Censor obscene words is on and it is smeared whole)."""
        return bool(word) and self.get_meta("censor", "0") == "1" and word in self.obscene_words()

    def kind_counts(self):
        """{kind of word: words of that kind with a clean meaning (the ones its tick deals), "obscene": words with
        only rude meanings, each rude kind: words with a meaning of that kind}, over the whole list. One pass:
        counted again only after a change."""
        mark = self.db.total_changes
        if getattr(self, "_kc", (None,))[0] != mark:
            counts = {k: 0 for k, _, _ in KINDS}
            counts.update({k: 0 for k in RUDE_KINDS}, obscene=0)
            for kinds, rude, n in self.db.execute(    # (bare columns: read in order from idx_words_kinds, 84 ms
                    "SELECT kinds, rude, COUNT(*) FROM words GROUP BY kinds, rude"):   # in a million; 0.5-0.8 s
                kinds = 16 if kinds is None else kinds              # with the defaults filled in by SQL)
                rude = 1 if rude is None else rude
                for k in RUDE_KINDS:
                    if rude & KIND_BITS[k]:
                        counts[k] += n
                if not rude & 1:
                    counts["obscene"] += n
                    continue
                for key, _, bit in KINDS:
                    if kinds & bit:
                        counts[key] += n
            self._kc = (mark, counts)
        return dict(self._kc[1])

    def tier_counts(self):
        """{tier index: number of placed words}. Tiers with no words are absent. Counted once (25 ms with 300k
        placed), then kept up to date by every change of a word's tier (_tier_moved), as the shelf is: counting
        again on every placement made each one 25 ms slower."""
        if self._counts is None:
            self._counts = {r[0]: r[1] for r in self.db.execute(
                "SELECT tier, COUNT(*) FROM words WHERE tier IS NOT NULL GROUP BY tier")}
        return dict(self._counts)

    def _forget_tallies(self):
        """After a change the running tallies cannot follow (a bulk write, a rollback): count them again."""
        self._prog = None
        self._counts = None

    def stats(self):
        """Numbers for the header: total, placed, skipped, per-tier counts, duels, conflicts."""
        # Index-friendly queries: with ~1M words, a full scan per refresh would make the UI laggy.
        if self._total is None:
            self._total = self.count_words()
        tiers = self.tier_counts()
        skipped = self.db.execute(           # (named: SQLite's planner preferred idx_words_q3, a 60 ms walk)
            f"SELECT COUNT(*) FROM words{self._hint('idx_words_skipped')} WHERE tier IS NULL AND skips > 0"
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
            totals = self._shelf_totals()
            layout = totals["layout"]
            spines, starts = [], []
            for name, edges in layout:
                for lo in edges[:-1]:
                    starts.append(lo)
                    spines.append({"zone": name, "words": 0, "placed": 0, "tiers": [0] * len(TIERS)})
            p = {"layout": [(name, len(edges) - 1) for name, edges in layout], "spines": spines, "starts": starts,
                 "fp": 0.0, "ft": totals["ft"]}
            ends = starts[1:] + [layout[-1][1][-1]] if layout else []
            for sp, lo, hi, n in zip(spines, starts, ends, totals["words"]):
                sp["words"] = n                    # (the placed ones: one range per spine of idx_placed_shelf)
                for tier, k, fq in self.db.execute(f"SELECT tier, COUNT(*), TOTAL(freq) FROM words"
                                                   f"{self._hint('idx_placed_shelf')} WHERE tier IS NOT NULL AND "
                                                   "rank >= ? AND rank < ? GROUP BY tier", (lo, hi)):
                    sp["placed"] += k
                    sp["tiers"][tier] += k
                    p["fp"] += fq
            self._prog = p
        p = self._prog
        return {"zones": p["layout"], "spines": [dict(sp, tiers=list(sp["tiers"])) for sp in p["spines"]],
                "coverage": p["fp"] / p["ft"] if p["ft"] > 0 else None}

    def _shelf_totals(self):
        """{"n": words in the list, "layout": shelf_layout(), "words": words per spine, "ft": their total frequency}.
        They change only when words come in or their frequencies change (_forget_shelf_totals), so they are counted
        once (a pass over the list, ~0.4 s at a million words on every start) and kept in the save."""
        n = self.count_words()
        try:
            t = json.loads(self.get_meta("shelf_totals") or "null")
        except ValueError:
            t = None
        if not isinstance(t, dict) or t.get("n") != n:
            layout = self.shelf_layout()
            bounds = [(lo, hi) for _name, edges in layout for lo, hi in zip(edges, edges[1:])]
            counts = [self.db.execute("SELECT COUNT(*), TOTAL(freq) FROM words WHERE rank >= ? AND rank < ?",
                                      b).fetchone() for b in bounds]          # (idx_words_shelf)
            ft = (sum(c[1] for c in counts) if counts
                  else self.db.execute("SELECT TOTAL(freq) FROM words").fetchone()[0])
            t = {"n": n, "layout": layout, "words": [c[0] for c in counts], "ft": ft}
            self.set_meta("shelf_totals", json.dumps(t))
        return t

    def _forget_shelf_totals(self):
        """Words came in, or their frequencies or ranks changed: the shelf's totals are counted again."""
        self.db.execute("DELETE FROM meta WHERE key='shelf_totals'")
        self._prog = None

    def _hint(self, index):
        """" INDEXED BY index" for a query that names its index, or "" while a bulk_write has it away."""
        return "" if index in self._bulk else f" INDEXED BY {index}"

    def spine_of(self, word):
        """Which spine of the progress shelf `word` belongs to (its index in shelf()["spines"]), or None."""
        self.shelf()
        row = self.get_word(word)
        starts = self._prog["starts"]
        if row is None or not starts:
            return None
        return bisect.bisect_right(starts, row["rank"]) - 1

    def _tier_moved(self, row, old, new):
        """Keep the tallies current (tier_counts, the shelf's): the word in `row` (with rank and freq) went from
        tier `old` to `new` (None = not placed). Every change of a word's tier calls this, or _forget_tallies."""
        c = self._counts
        if c is not None and old != new:
            for t, sign in ((old, -1), (new, 1)):
                if t is not None:
                    c[t] = c.get(t, 0) + sign
                    if c[t] <= 0:
                        del c[t]
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
        self._forget_shelf_totals()
        self.db.commit()
        self._forget_tallies()
        self.version += 1

    def settled_shares(self, min_games, totals=None):
        """Per tier, the share of its words with at least `min_games` duels (how settled its order is, UI-31);
        None for an empty tier. `totals` is tier_counts() if the caller has it already. Index-only
        (idx_words_tg), and per tier it counts the smaller side, the settled or the unsettled words, as the last
        answer says (counting every settled word took ~30 ms a duel with 300k placed, most of them settled)."""
        total = totals if totals is not None else self.tier_counts()
        last = getattr(self, "_settled_last", {})
        shares = []
        for t in range(len(TIERS)):
            n = total.get(t, 0)
            if not n:
                shares.append(None)
                continue
            if last.get((t, min_games), 0.0) > 0.5:
                done = n - self.db.execute("SELECT COUNT(*) FROM words WHERE tier=? AND games < ?",
                                           (t, min_games)).fetchone()[0]
            else:
                done = self.db.execute("SELECT COUNT(*) FROM words WHERE tier=? AND games >= ?",
                                       (t, min_games)).fetchone()[0]
            last[(t, min_games)] = done / n
            shares.append(done / n)
        self._settled_last = last
        return shares

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
        self._forget_tallies()
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
        front = self.db.execute(              # (the front of the dealt words: one step down idx_words_q3; without
            "SELECT MIN(qkey) FROM words WHERE tier IS NULL AND out=0 AND skips=0 AND qkey < 1e17"   # out=0 it
        ).fetchone()[0]                       # walked every unplaced word, 75 ms in a million)
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
                seeds += self._least_dueled(t, 40)
            seeds.sort(key=lambda r: (r["games"], random.random()))
            seeds = seeds[:40]
            random.shuffle(seeds)
        for a in seeds:
            faced = self._faced_set(a["word"])
            for c in self._nearest(a, 80):
                if c["word"] not in faced:
                    return a["word"], c["word"], a["tier"]
        return None

    def _least_dueled(self, t, k):
        """Up to k of tier t's words with the fewest duels, from a random point among those with as few (ORDER BY
        games, RANDOM() sorted every such word: tens of thousands in a big tier, ~50 ms a duel)."""
        least = self.db.execute("SELECT MIN(games) FROM words WHERE tier=?", (t,)).fetchone()[0]
        if least is None:
            return []
        same = self.db.execute("SELECT COUNT(*) FROM words WHERE tier=? AND games=?", (t, least)).fetchone()[0]
        rows = self.db.execute("SELECT * FROM words WHERE tier=? AND games=? LIMIT ? OFFSET ?",
                               (t, least, k, random.randrange(same - k) if same > k else 0)).fetchall()
        if len(rows) < k:                     # (a few with the fewest: the next fewest after them)
            rows += self.db.execute("SELECT * FROM words WHERE tier=? AND games>? ORDER BY games LIMIT ?",
                                    (t, least, k - len(rows))).fetchall()
        return rows

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
    SEARCH_WINDOW, SEARCH_WINDOW_MAX = 20, 200_000     # (a broad search reads this many words in order per row asked)
    _PLACED_INDEX = {"Default": "idx_placed_order", "Rating": "idx_placed_rating", "Duels": "idx_placed_games",
                     "A-Z": "idx_placed_word", "Frequency": "idx_placed_shelf"}
    _UNPLACED_INDEX = {"Default": "idx_unplaced_queue", "Frequency": "idx_unplaced_rank", "A-Z": "idx_unplaced_word"}

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
            elif tier_filter == "Obscene words":               # ST-6: a kind of word (placed ones): only rude meanings
                where.append("(COALESCE(rude, 1) & 1) = 0")
            elif tier_filter in self.KIND_FILTERS:
                where.append("(COALESCE(kinds, 16) & ?) != 0")
                args.append(self.KIND_FILTERS[tier_filter])
        if tier_filter == "Unplaced" and sort in ("Rating", "Duels"):
            sort = "Frequency"          # (an unplaced word is always at 1500 with no duels: the order is by rank, from
                                        # idx_unplaced_rank, not a sort of every unplaced word: 0.9 s in a million)
        order = self._ORDERS.get(sort, default_order)
        if reverse:
            order = ", ".join(part.replace(" ASC", " DESC") if part.endswith(" ASC") else part.replace(" DESC", " ASC")
                              for part in order.split(", "))
        if text:
            where.append("word LIKE ?")
            args.append("%" + text.replace("%", "").replace("_", "") + "%")
        clause = " AND ".join(where)
        # the index each order is read from, named (without fresh statistics SQLite's planner sometimes sorted every
        # row instead: 0.2-0.9 s in a million)
        placed = tier_filter != "Unplaced"
        if text:                        # (a search: the few words that match, found in the words' own index, sorted)
            index = "idx_placed_word" if placed else "idx_unplaced_word"
        elif tier_filter == "Obscene words":                   # (a few among the placed: found, then sorted)
            index = "idx_placed_kinds"
        elif tier_filter.startswith("Tier "):
            index = None                # (the tier's own words: idx_words_tr, the planner's choice)
        else:
            index = (self._PLACED_INDEX if placed else self._UNPLACED_INDEX).get(sort)
        hint = self._hint(index) if index else ""
        cols = "word, tier, rating, games, skips, rank, pen"
        rows = None
        ordered = (self._PLACED_INDEX if placed else self._UNPLACED_INDEX).get(sort)
        window = (offset + limit) * self.SEARCH_WINDOW
        broad = tier_filter in ("All placed", "Unplaced") or (tier_filter.startswith("Tier ") and sort == "Default")
        if text and ordered and broad and window <= self.SEARCH_WINDOW_MAX:
            # a search that matches many words (one letter): read the sort's own index from the top and stop once
            # a page of matches is found, instead of sorting every match (0.25 s in a million). The first `window`
            # words in order hold the first matches in order; too few there (a rarer search), the usual way below.
            # Only where that index leads straight to the rows (a kind of word, or a small tier in another order,
            # could be spread through all of it)
            rows = self.db.execute(
                f"SELECT {cols} FROM (SELECT {cols}, qkey FROM words{self._hint(ordered)} WHERE {' AND '.join(where[:-1])}"
                f" ORDER BY {order} LIMIT ?) WHERE word LIKE ? ORDER BY {order} LIMIT ? OFFSET ?",
                args[:-1] + [window, args[-1], limit, offset]).fetchall()
            if len(rows) < limit:
                rows = None
        if rows is None:
            rows = self.db.execute(
                f"SELECT {cols} FROM words{hint} WHERE {clause} ORDER BY {order} LIMIT ? OFFSET ?",
                args + [limit, offset],
            ).fetchall()
        total = None
        if with_total:
            if offset == 0 and len(rows) < limit:
                total = len(rows)  # a short first page is everything: skip the extra full scan
            else:
                counted = self._hint("idx_placed_kinds") if tier_filter in self.KIND_FILTERS or \
                    tier_filter == "Obscene words" else ""
                if text and not counted:      # (a search counts in the words' own index, as it lists: without it the
                    counted = hint            # count read the whole table, 0.9 s of a 1 s search in a million)
                total = self.db.execute(f"SELECT COUNT(*) FROM words{counted} WHERE {clause}", args).fetchone()[0]
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
            if res["added"]:
                self._forget_shelf_totals()
            self.db.commit()
        except Exception:
            self.db.rollback()
            self._forget_tallies()            # (the rolled-back rows had moved them)
            raise
        self._total = None
        self._forget_tallies()
        self.version += 1
        return res
