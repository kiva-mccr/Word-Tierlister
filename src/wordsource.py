"""Where the words come from: WordNet, Wiktionary download/parse, compound detection, queue prep.

Flow on a first run (driven by main() in tierlist.py):
    build_word_list() or build_wiktionary()   fill the `words` table, most common first
    prepare_queue()                           look up word frequencies once (fill_frequencies), flag
                                              compounds (compute_penalties), then give every
                                              unplaced word a seeded queue key (Store.reshuffle)

The Wiktionary path is resumable at every stage: the 3 GB download continues from its .part file,
the parsed entries sit in a temporary `wk` table (flag meta.wk_done), and existing progress in the
save is never touched. Needs `wordfreq` (frequency data); `nltk` is only used for the small WordNet list.
"""
import gzip
import http.client
import json
import math
import os
import re
import time
import urllib.error
import urllib.request

from problems import SetupError


# --------------------------------------------------------------------------
# Small word lists: a custom text file, or the ~77k WordNet dictionary words
# --------------------------------------------------------------------------
def build_word_list(custom_path=None):
    """Return dictionary words, most common first.

    With `custom_path`: that file's lines, in file order, de-duplicated and lower-cased.
    Otherwise WordNet's lemma names (ASCII lowercase letters only) ordered by wordfreq frequency;
    if WordNet cannot be loaded, wordfreq's own top 60,000 words (which include names).
    """
    if custom_path:
        seen, out = set(), []
        with open(custom_path, encoding="utf-8") as f:
            for line in f:
                w = line.strip().lower()
                if w and w not in seen:
                    seen.add(w)
                    out.append(w)
        return out

    try:
        from wordfreq import top_n_list, zipf_frequency
    except ImportError:
        raise SetupError("A required package is missing.\n\nOpen a terminal and run:\n    pip install wordfreq nltk\n\nthen start the program again.")

    def ok(w):
        # plain lowercase ASCII words only; single letters other than "a" and "i" are noise
        return w.isalpha() and w.isascii() and w.islower() and (len(w) > 1 or w in ("a", "i"))

    lemmas = None
    try:
        import nltk
        from nltk.corpus import wordnet as wn

        try:
            wn.synsets("dog")
        except LookupError:
            print("Downloading the WordNet dictionary (one time)...")
            nltk.download("wordnet", quiet=True)
            wn.synsets("dog")
        lemmas = {n for n in wn.all_lemma_names() if ok(n)}
    except Exception as exc:  # nltk missing, offline, etc.
        print("WordNet unavailable; falling back to wordfreq's top 60,000 words (this includes names).\n"
              "To use the real dictionary list, run:  python -m nltk.downloader wordnet\n"
              "then delete the .db file and start again. Details: " + str(exc).strip().splitlines()[0])

    if lemmas:
        print(f"Ordering {len(lemmas):,} dictionary words by frequency...")
        return sorted(lemmas, key=lambda w: (-zipf_frequency(w, "en"), w))
    return [w for w in top_n_list("en", 60000) if ok(w)]


# --------------------------------------------------------------------------
# Wiktionary word source (kaikki.org's extract of English Wiktionary)
# --------------------------------------------------------------------------
WIKT_URL = "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl"
WIKT_FILENAME = "kaikki-English.jsonl"
# Wiktionary entry types (the "pos" field) that are not standalone words, so they are left out.
SKIP_POS = {"name", "symbol", "character", "punct", "romanization", "prefix", "suffix", "infix",
            "interfix", "affix", "circumfix", "proverb", "phrase", "prep_phrase"}
# Senses carrying only these labels count as "dead": such words are pushed further back.
DEAD_TAGS = {"obsolete", "archaic", "rare", "dialectal"}
# A word is letters, optionally joined by single hyphens/apostrophes ("well-known", "don't").
# _PHRASE_RE additionally allows spaces ("ice cream"); it is used only with --include-phrases.
_WORD_RE = re.compile(r"^[^\W\d_]+(?:[-'’][^\W\d_]+)*$")
_PHRASE_RE = re.compile(r"^[^\W\d_]+(?:[-' ’][^\W\d_]+)*$")
# Insert a parsed entry into the staging table, or merge it with an earlier entry for the same word
# (a word often has several parts of speech): add the senses, keep the definition text (capped).
_WK_UPSERT = (
    "INSERT INTO wk(word, senses, lemma, live, text) VALUES(?,?,?,?,?) "
    "ON CONFLICT(word) DO UPDATE SET senses=senses+excluded.senses, "
    "lemma=MAX(lemma, excluded.lemma), live=MAX(live, excluded.live), "
    "text=CASE WHEN length(text) < 800 THEN text || char(10) || excluded.text ELSE text END"
)


def download_resumable(url, dest, log=print, retries=8):
    """Download `url` to `dest`, resuming a partial `.part` file after interruptions."""
    part = dest + ".part"
    log("  connecting to the server (1%)")      # stand-in so the progress bar has something to show at once
    for attempt in range(1, retries + 1):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        headers = {"User-Agent": "tierlist/1.0"}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            try:
                resp = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60)
            except urllib.error.HTTPError as exc:
                if exc.code == 416 and have:  # the partial file is already complete
                    os.replace(part, dest)
                    return
                raise
            with resp:
                resuming = have > 0 and resp.status == 206
                if not resuming:
                    have = 0
                length = resp.headers.get("Content-Length")
                total = have + int(length) if length else None
                last = time.time()
                with open(part, "ab" if resuming else "wb") as f:
                    while True:
                        chunk = resp.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        have += len(chunk)
                        if time.time() - last > 1:
                            last = time.time()
                            pct = f" ({100.0 * have / total:.0f}%)" if total else ""
                            log(f"  downloaded {have / 1e9:.2f} GB{pct}")
                if total and have < total:
                    raise OSError("connection closed early")
            os.replace(part, dest)
            return
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403, 404, 410):
                raise RuntimeError(f"the server answered HTTP {exc.code} for {url}")
            log(f"Download interrupted (HTTP {exc.code}); retry {attempt}/{retries}...")
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            log(f"Download interrupted ({exc}); retry {attempt}/{retries}...")
        time.sleep(3)
    raise RuntimeError("the download kept failing")


def _open_text(path):
    """Open a .jsonl or .jsonl.gz file for reading as text."""
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def _summarize(entry):
    """-> (sense count, has_lemma_sense, has_live_sense, up to 4 definition lines)."""
    pos = entry.get("pos", "")
    lines, n, lemma, live = [], 0, False, False
    for s in entry.get("senses", []):
        glosses = s.get("glosses") or []
        if not glosses:
            continue
        n += 1
        if not (s.get("form_of") or s.get("alt_of")):
            lemma = True
        dead = set(s.get("tags", [])) & DEAD_TAGS
        if not dead:
            live = True
        if len(lines) < 4:
            label = f"({', '.join(sorted(dead))}) " if dead else ""
            lines.append(f"• ({pos}) {label}{str(glosses[-1])[:220]}")
    return n, lemma, live, "\n".join(lines)


def _parse_wiktionary(db, path, include_phrases, log):
    """Stream the kaikki.org JSONL dump into the staging table `wk`, one row per word (committed in batches).

    Keeps English entries whose headword is lowercase, word-shaped, not an affix/name/symbol and has
    at least one gloss. Memory use stays flat because lines are read one at a time.
    """
    shape = _PHRASE_RE if include_phrases else _WORD_RE
    batch, lines, kept = [], 0, 0
    # Progress = characters read / file size. Close enough for a progress bar on the plain .jsonl
    # (almost all ASCII); for a .gz the sizes are not comparable, so no percentage is reported.
    total = 0 if path.endswith(".gz") else os.path.getsize(path)
    chars = 0
    log("  opening the file (1%)" if total else "  opening the file...")   # stand-in until the first update
    with _open_text(path) as f:
        for line in f:
            lines += 1
            chars += len(line)
            if lines % 50000 == 0:
                pct = f" ({min(99, int(100 * chars / total))}%)" if total else ""
                log(f"  parsed {lines:,} entries, kept {kept:,}{pct}")
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("lang_code", "en") != "en":
                continue
            word = entry.get("word")
            if (not word or entry.get("pos") in SKIP_POS or word != word.lower()
                    or not shape.match(word)):
                continue
            n, lemma, live, text = _summarize(entry)
            if n == 0:
                continue
            batch.append((word, n, int(lemma), int(live), text))
            kept += 1
            if len(batch) >= 20000:
                db.executemany(_WK_UPSERT, batch)
                db.commit()
                batch = []
    if batch:
        db.executemany(_WK_UPSERT, batch)
        db.commit()
    log(f"  parsed {lines:,} entries, kept {kept:,}")


def build_wiktionary(store, path=None, include_phrases=False, keep_download=False, log=print):
    """Load every English Wiktionary word into `store`, most common first.

    Order = wordfreq frequency; words with no frequency data are ordered by how "real" they look
    (live senses before obsolete/rare-only, headwords before inflected forms, more senses first,
    shorter first). Definitions are cached into the save file. Existing progress is kept.
    """
    try:
        from wordfreq import get_frequency_dict, zipf_frequency
    except ImportError:
        raise SetupError("A required package is missing.\n\nOpen a terminal and run:\n    pip install wordfreq\n\nthen start the program again.")
    db = store.db
    default_path = os.path.join(os.path.dirname(os.path.abspath(store.path)), WIKT_FILENAME)
    ours = path is None
    path = path or default_path
    db.execute("CREATE TABLE IF NOT EXISTS wk("
               "word TEXT PRIMARY KEY, senses INTEGER, lemma INTEGER, live INTEGER, text TEXT)")
    if store.get_meta("wk_done") != "1":
        db.execute("DELETE FROM wk")
        db.commit()
        if ours and not os.path.exists(path):
            log("Downloading English Wiktionary (about 3 GB)...")
            log(f"  saving to {path}")
            log("  if it stops, just run the program again and it resumes")
            download_resumable(WIKT_URL, path, log)
        log("Reading entries...")
        _parse_wiktionary(db, path, include_phrases, log)
        store.set_meta("wk_done", "1")

    log("Ranking words by frequency...")
    log("  loading the word-frequency data (about a minute)...")
    fd = get_frequency_dict("en")

    def zipf(w):
        # Zipf scale (log10 of frequency per billion words). Hyphenated/spaced forms are not in the
        # single-word dictionary, so ask wordfreq to estimate them; everything else unknown is 0.
        f = fd.get(w)
        if f:
            return math.log10(f) + 9.0
        if "-" in w or " " in w:
            return zipf_frequency(w, "en")
        return 0.0

    log("  ordering the words by how common they are...")
    rows = db.execute("SELECT word, senses, lemma, live FROM wk").fetchall()
    rows.sort(key=lambda r: (-zipf(r[0]), 0 if r[3] else 1, 0 if r[2] else 1,
                             -min(r[1], 12), len(r[0]), r[0]))
    ordered = [r[0] for r in rows]
    if not ordered:
        store.set_meta("wk_done", "0")
        raise RuntimeError("no usable entries were found in the Wiktionary file")
    if store.count_words():
        # Words already in the save that Wiktionary lacks go behind everything else.
        db.execute("UPDATE words SET rank = rank + ?", (len(ordered),))
    log(f"  saving {len(ordered):,} words and their definitions to your save file...")
    store.insert_words(ordered)
    db.execute("INSERT OR REPLACE INTO defs(word, text) SELECT word, text FROM wk")
    db.execute("DROP TABLE wk")
    db.commit()
    store.set_meta("source", "wiktionary")
    store.set_meta("wk_done", "0")
    if ours and not keep_download and os.path.exists(path):
        try:
            os.remove(path)
            log("Removed the downloaded dump (use --keep-download to keep it).")
        except OSError:
            pass
    log(f"Word list ready: {len(ordered):,} words.")
    return len(ordered)


# --------------------------------------------------------------------------
# Compound-word detection + queue preparation
# --------------------------------------------------------------------------
def compute_penalties(store, log=print):
    """Flag compounds so they are demoted in the queue (pen: 1 = closed compound, 2 = hyphenated).

    A closed compound is an uncommon word (zipf < 4) that splits into two common words of at
    least four letters each ("book" + "shelf"). Very common words ("something") are never flagged.
    """
    try:
        from wordfreq import get_frequency_dict
    except ImportError:
        log("wordfreq is not installed, so compound words cannot be detected (pip install wordfreq).")
        return False
    log("  loading the word-frequency data...")
    fd = get_frequency_dict("en")
    parts = {w for w, f in fd.items() if len(w) >= 4 and w.isalpha() and math.log10(f) + 9.0 >= 3.5}

    def zipf(w):
        # Zipf-scale frequency (about 3 = rare, 5 = common, 7 = "the"); 0 if wordfreq has never seen it.
        f = fd.get(w)
        return math.log10(f) + 9.0 if f else 0.0

    log("  checking every word for compounds like 'bookshelf'...")
    flagged = []
    for (word,) in store.db.execute("SELECT word FROM words").fetchall():
        if "-" in word or " " in word:
            if zipf(word) < 4.0:
                flagged.append((2, word))
        elif (len(word) >= 8 and word.isalpha() and zipf(word) < 4.0
              and any(word[:i] in parts and word[i:] in parts for i in range(4, len(word) - 3))):
            flagged.append((1, word))
    store.db.execute("UPDATE words SET pen=0 WHERE pen!=0")
    store.db.executemany("UPDATE words SET pen=? WHERE word=?", flagged)
    store.db.commit()
    log(f"  flagged {len(flagged):,} compound words.")
    return True


def fill_frequencies(store, log=print):
    """Store each word's wordfreq frequency (for the progress bar's coverage tag, UI-14). Words wordfreq has never
    seen keep 0: they add nothing to how much of everyday English is covered."""
    try:
        from wordfreq import get_frequency_dict
    except ImportError:
        log("wordfreq is not installed, so the coverage figure is not available (pip install wordfreq).")
        return
    fd = get_frequency_dict("en")
    words = [r[0] for r in store.db.execute("SELECT word FROM words")]
    store.set_frequencies((w, fd[w]) for w in words if w in fd)


def prepare_queue(store, log=print):
    """Make sure every unplaced word has a queue position. Runs at startup; cheap when up to date."""
    if not store.count_words():
        return
    changed = False
    if store.get_meta("pen_done") != "1":
        log("Detecting compound words (one time, can take a minute on a large list)...")
        if compute_penalties(store, log):
            store.set_meta("pen_done", "1")
            changed = True
    if store.get_meta("freq_done") != "1":
        log("Looking up how common each word is (one time, a few seconds)...")
        fill_frequencies(store, log)
    stale = store.db.execute(
        "SELECT 1 FROM words WHERE tier IS NULL AND (qkey IS NULL OR qkey >= 1e17) LIMIT 1").fetchone()
    if stale or changed:
        log("Shuffling the queue (seeded; one time, can take a minute on a large list)...")
        log("  giving every unplaced word its random place in the queue...")
        store.reshuffle()
