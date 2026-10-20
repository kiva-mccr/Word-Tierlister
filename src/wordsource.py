"""Where the words come from: WordNet, Wiktionary download/parse, compound detection, queue prep.

Flow on a first run (driven by main() in tierlist.py):
    build_word_list() or build_wiktionary()   fill the `words` table, most common first
    prepare_queue()                           look up word frequencies once (fill_frequencies), flag
                                              compounds (compute_penalties), sort words into kinds and
                                              find the obscene ones (fill_kinds, fill_obscene: ST-6; a
                                              Wiktionary build records the kinds itself), then give every
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
import urllib.parse
import urllib.request

from constants import kind_bits
from obscene import decide, obscene_in, page_marks, tag_marks
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
    "INSERT INTO wk(word, senses, lemma, live, text, kinds, marks) VALUES(?,?,?,?,?,?,?) "
    "ON CONFLICT(word) DO UPDATE SET senses=senses+excluded.senses, "
    "lemma=MAX(lemma, excluded.lemma), live=MAX(live, excluded.live), "
    "kinds=kinds | excluded.kinds, marks=marks || ' ' || excluded.marks, "
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
    """-> (sense count, has_lemma_sense, has_live_sense, up to 4 definition lines, the senses' obscene.tag_marks)."""
    pos = entry.get("pos", "")
    lines, n, lemma, live, marks = [], 0, False, False, []
    for s in entry.get("senses", []):
        glosses = s.get("glosses") or []
        if not glosses:
            continue
        n += 1
        marks.append(tag_marks(s))
        if not (s.get("form_of") or s.get("alt_of")):
            lemma = True
        dead = set(s.get("tags", [])) & DEAD_TAGS
        if not dead:
            live = True
        if len(lines) < 4:
            label = f"({', '.join(sorted(dead))}) " if dead else ""
            lines.append(f"• ({pos}) {label}{str(glosses[-1])[:220]}")
    return n, lemma, live, "\n".join(lines), " ".join(m.replace(" ", "_") for m in marks)


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
            n, lemma, live, text, marks = _summarize(entry)
            if n == 0:
                continue
            batch.append((word, n, int(lemma), int(live), text, kind_bits(entry.get("pos")), marks))
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
    if store.get_meta("wk_done") == "1" and "marks" not in {r[1] for r in db.execute("PRAGMA table_info(wk)")}:
        store.set_meta("wk_done", "0")          # a half-done build from before ST-6 has no kinds: read the file again
    if store.get_meta("wk_done") != "1":
        db.execute("DROP TABLE IF EXISTS wk")
        db.execute("CREATE TABLE wk(word TEXT PRIMARY KEY, senses INTEGER, lemma INTEGER, live INTEGER, text TEXT, "
                   "kinds INTEGER, marks TEXT)")
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
    db.execute("UPDATE words SET kinds=(SELECT kinds FROM wk WHERE wk.word=words.word)")
    store.set_meta("kinds_done", "1")
    log("  finding the obscene words (most or first of their meanings rude)...")
    marks = {w: m.split() for w, m in db.execute("SELECT word, marks FROM wk WHERE marks LIKE '%r%' OR marks LIKE '%f:%'")}
    store.set_obscene(decide({w: [x.replace("_", " ") for x in m] for w, m in marks.items()}), replace=True)
    store.set_meta("obscene_done", store.OBSCENE_VERSION)
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
        from wordfreq import get_frequency_dict, word_frequency
    except ImportError:
        log("wordfreq is not installed, so the coverage figure is not available (pip install wordfreq).")
        return
    fd = get_frequency_dict("en")

    def freq(w):        # the same as the ranking (build_wiktionary's zipf): hyphenated / spaced forms are estimated
        f = fd.get(w)
        if f:
            return f
        return word_frequency(w, "en") if ("-" in w or " " in w) else 0.0
    words = [r[0] for r in store.db.execute("SELECT word FROM words")]
    store.set_frequencies((w, f) for w, f in ((w, freq(w)) for w in words) if f)


# --------------------------------------------------------------------------
# Kinds of words (for a save made before ST-6: a Wiktionary build records them itself) and obscene words
# --------------------------------------------------------------------------
_DEF_POS = re.compile(r"^\s*(?:\u2022|\d+\.)\s*\(([a-z ]+)\)", re.M)


def fill_kinds(store, log=print):
    """Each word's kinds from its stored definition (every source writes "(noun) ..." lines: the Wiktionary
    build's, WordNet's, dictionaryapi.dev's), else from WordNet (nltk) if it is installed, else "other"."""
    log("  reading the parts of speech from the stored definitions...")
    kinds = {}
    for word, text in store.db.execute("SELECT word, text FROM defs"):
        bits = 0
        for pos in _DEF_POS.findall(text or ""):
            bits |= kind_bits(pos)
        if bits:
            kinds[word] = bits
    rest = [r[0] for r in store.db.execute("SELECT word FROM words WHERE kinds IS NULL") if r[0] not in kinds]
    wn = None
    if rest:
        try:
            from nltk.corpus import wordnet as wn
            wn.synsets("dog")
        except Exception:               # nltk or its data missing: those words count as "other"
            wn = None
    if wn is not None:
        log(f"  asking WordNet about {len(rest):,} more words...")
        letters = {"n": 1, "v": 2, "a": 4, "s": 4, "r": 8}
        for w in rest:
            bits = 0
            for syn in wn.synsets(w.replace(" ", "_")):
                bits |= letters.get(syn.pos(), 16)
            if bits:
                kinds[w] = bits
    store.set_kinds(kinds.items())
    store.db.execute("UPDATE words SET kinds=16 WHERE kinds IS NULL")
    store.db.commit()
    log(f"  sorted {len(kinds):,} words into kinds.")


# Wiktionary's categories of rude words, for a save whose download is gone: only their members can have a rude
# meaning (the labels file a word there), so only their pages are read (fill_obscene)
OBSCENE_CATEGORIES = ("English vulgarities", "English offensive terms", "English derogatory terms",
                      "English ethnic slurs", "English swear words")
WIKT_API = "https://en.wiktionary.org/w/api.php"
OBSCENE_RETRY_S = 6 * 3600          # offline: ask Wiktionary again after this long (each start would wait on it)
_FORM_GLOSS = re.compile(r"\b(?:plural|participle|tense|form|spelling|singular|comparative|superlative|gerund|"
                         r"inflection|misspelling)\b.*\bof ([^\s,;:()]+)\s*$")


OFFLINE_ENV = "WORD_TIERLIST_OFFLINE"   # set (the self-tests do): never ask Wiktionary, as if offline


def _fetch_json(url):
    if os.environ.get(OFFLINE_ENV):
        raise OSError("offline (" + OFFLINE_ENV + ")")
    req = urllib.request.Request(url, headers={"User-Agent": "word-tierlist/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _category_members(title, fetch, limit=200):
    """Every page title in one Wiktionary category (500 per request)."""
    out, cont = [], None
    for _ in range(limit):
        q = {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + title, "cmnamespace": "0",
             "cmlimit": "500", "format": "json"}
        if cont:
            q["cmcontinue"] = cont
        data = fetch(WIKT_API + "?" + urllib.parse.urlencode(q))
        out += [m["title"] for m in data.get("query", {}).get("categorymembers", [])]
        cont = data.get("continue", {}).get("cmcontinue")
        if not cont:
            break
    return out


def _page_texts(titles, fetch):
    """{title: wikitext} for up to 50 pages, following the API's "continue" when the answer is cut short."""
    q = {"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "format": "json",
         "formatversion": "2", "titles": "|".join(titles)}
    out, cont = {}, {}
    for _ in range(60):
        data = fetch(WIKT_API + "?" + urllib.parse.urlencode(dict(q, **cont)))
        for page in data.get("query", {}).get("pages", []):
            revs = page.get("revisions") or []
            if revs:
                out[page["title"]] = revs[0].get("slots", {}).get("main", {}).get("content", "")
        cont = data.get("continue") or {}
        if not cont:
            break
    return out


def fill_obscene(store, log=print, fetch=None):
    """Mark the obscene words of a save whose Wiktionary download is gone (obscene.decide: most or the first of a
    word's meanings rude): the words Wiktionary files under rude categories are read from their pages (50 a
    request), and their plural / past tense ... forms from the save's own definitions ("plural of bitch"). Needs
    the internet; returns False when it could not (tried again on a later start; the words marked before stay)."""
    fetch = fetch or _fetch_json
    have = {r[0] for r in store.db.execute("SELECT word FROM words")}
    try:
        cands = set()
        for title in OBSCENE_CATEGORIES:
            log(f"  {title}...")
            cands.update(w for w in _category_members(title, fetch) if w in have)
        cands = sorted(cands)
        marks = {}
        for i in range(0, len(cands), 50):
            log(f"  reading their meanings: {i:,} of {len(cands):,} words ({100 * i // max(1, len(cands))}%)")
            for title, text in _page_texts(cands[i:i + 50], fetch).items():
                marks[title] = page_marks(text)
    except (OSError, ValueError, http.client.HTTPException) as exc:
        log(f"  could not reach Wiktionary ({exc}); trying again next time.")
        return False
    for word, text in store.db.execute("SELECT word, text FROM defs WHERE text LIKE '% of %'"):
        if word not in marks:                       # (forms of the rude words: "bitches", "fucking")
            lines = [ln.split(") ", 1)[-1] for ln in (text or "").splitlines() if ln.strip()]
            m = [("f:" + g.group(1)) if (g := _FORM_GLOSS.search(ln)) else "p" for ln in lines]
            if any(x.startswith("f:") for x in m):
                marks[word] = m
    store.set_obscene(decide(marks), replace=True)
    log(f"  found {len(store.obscene_words()):,} obscene words in your list.")
    return True


def _wants_obscene(store):
    """True if the obscene words still need finding (with Wiktionary's labels), and it is time to try (offline: the
    hand-picked list stands in until then, OBSCENE_RETRY_S between tries)."""
    done = store.get_meta("obscene_done")
    if done == store.OBSCENE_VERSION:
        return False
    if done != "list":
        return True
    try:
        last = float(store.get_meta("obscene_tried", "0"))
    except ValueError:
        last = 0.0
    return time.time() - last > OBSCENE_RETRY_S


def wiktionary_steps(store, path=None):
    """The main steps build_wiktionary will report, for the progress window's "Step 2 of 5" (plan_line)."""
    steps = []
    if store.get_meta("wk_done") != "1":
        default = os.path.join(os.path.dirname(os.path.abspath(store.path)), WIKT_FILENAME)
        if path is None and not os.path.exists(default):
            steps.append("Downloading English Wiktionary")
        steps.append("Reading entries")
    return steps + ["Ranking words"]


def queue_steps(store, adds_words=False, records_kinds=False):
    """The main steps prepare_queue will report (see wiktionary_steps). `adds_words`: words are about to be
    added first, which makes it redo all three (adding words resets pen_done and freq_done); `records_kinds`:
    by a Wiktionary build, which records the kinds and the obscene words itself."""
    if not adds_words and not store.count_words():
        return []
    pen = adds_words or store.get_meta("pen_done") != "1"
    freq = adds_words or store.get_meta("freq_done") != store.FREQ_VERSION
    kinds = not records_kinds and store.get_meta("kinds_done") != "1"
    obscene = not records_kinds and (adds_words or _wants_obscene(store))
    shuffle = pen or store.db.execute(
        "SELECT 1 FROM words WHERE tier IS NULL AND (qkey IS NULL OR qkey >= 1e17) LIMIT 1").fetchone() is not None
    return ((["Detecting compound words"] if pen else []) + (["Looking up how common"] if freq else [])
            + (["Sorting words into kinds"] if kinds else [])
            + (["Finding obscene words"] if obscene else [])
            + (["Shuffling the queue"] if shuffle else []))


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
    if store.get_meta("freq_done") != store.FREQ_VERSION:
        log("Looking up how common each word is (one time, a few seconds)...")
        fill_frequencies(store, log)
    dealt = False
    if store.get_meta("kinds_done") != "1":
        log("Sorting words into kinds (nouns, verbs...; one time, a few seconds)...")
        fill_kinds(store, log)
        store.set_meta("kinds_done", "1")
        dealt = True
    if _wants_obscene(store):
        log("Finding obscene words (one time, asks Wiktionary)...")
        store.set_meta("obscene_tried", time.time())
        if fill_obscene(store, log):
            store.set_meta("obscene_done", store.OBSCENE_VERSION)
        elif store.get_meta("obscene_done") != "list":    # offline: the hand-picked list until it can ask
            store.set_obscene(obscene_in(r[0] for r in store.db.execute("SELECT word FROM words")), replace=True)
            store.set_meta("obscene_done", "list")
        dealt = True
    if dealt or store.get_meta("deal_done") != "2":     # the words left out follow the new kinds (2: obscene words
        store.set_deal()                                 # unticked by default)
        store.set_meta("deal_done", "2")
    stale = store.db.execute(
        "SELECT 1 FROM words WHERE tier IS NULL AND (qkey IS NULL OR qkey >= 1e17) LIMIT 1").fetchone()
    if stale or changed:
        log("Shuffling the queue (seeded; one time, can take a minute on a large list)...")
        log("  giving every unplaced word its random place in the queue...")
        store.reshuffle()
