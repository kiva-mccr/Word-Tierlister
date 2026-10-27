"""Word definitions: offline WordNet, online dictionaryapi.dev fallback, cached in the save.

Lookups run on a background thread so the window never freezes. Usage: call request(word) when a
definition is wanted (it returns cached text or None), then poll drain() from the UI loop for
finished lookups. Results are cached in the save file by the caller (App) via Store.set_def().
"""
import json
import os
import queue
import re
import threading
import urllib.error
import urllib.parse
import urllib.request

from constants import OFFLINE_ENV


# --------------------------------------------------------------------------
# The word's page on Wiktionary (asked for: a link on the definition, for its etymology and the rest), shown only
# while Wiktionary can be reached
# --------------------------------------------------------------------------
WIKTIONARY_PAGE = "https://en.wiktionary.org/wiki/"
ONLINE_CHECK = "https://en.wiktionary.org/wiki/Special:BlankPage"


def wiktionary_url(word):
    """The English section of `word`'s Wiktionary page."""
    return WIKTIONARY_PAGE + urllib.parse.quote(word.replace(" ", "_")) + "#English"


class Online:
    """Whether Wiktionary can be reached, checked on a worker thread now and every EVERY seconds (never from the
    window: it only reads `online`). Never online with WORD_TIERLISTER_OFFLINE (the tests). `probe() -> bool`: tests."""
    EVERY = 60

    def __init__(self, probe=None):
        self.online = False
        self._probe = probe or self._reach
        self._stop = threading.Event()
        self._thread = None

    @staticmethod
    def _reach():
        try:
            req = urllib.request.Request(ONLINE_CHECK, method="HEAD", headers={"User-Agent": "word-tierlister"})
            with urllib.request.urlopen(req, timeout=5):
                return True
        except urllib.error.HTTPError:
            return True                                  # (an answer, even a refusal, means it is reachable)
        except Exception:
            return False

    def start(self):
        if os.environ.get(OFFLINE_ENV) or self._thread is not None:
            return self
        def run():
            while not self._stop.is_set():
                self.online = bool(self._probe())
                self._stop.wait(self.EVERY)
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()


# --------------------------------------------------------------------------
# Definitions (WordNet offline, dictionaryapi.dev online fallback, cached)
# --------------------------------------------------------------------------
POS_NAMES = {"n": "noun", "v": "verb", "a": "adj", "s": "adj", "r": "adv"}
_SENSE = re.compile(r"^\s*(\d+)\.\s*(?:\(([^)]*)\)\s*)?(.*)$")
_BULLET = re.compile(r"^\s*\u2022\s*(?:\(([^)]*)\)\s*)?(.*)$")          # the Wiktionary build's "• (noun) text"
_LABELS = re.compile(r"^\(([^()]*)\)\s*")                                # "(vulgar, slang) text"
_EXAMPLE = re.compile(r'^\s*e\.g\.\s*"?(.*?)"?\s*$')


def _sense(num, pos, text, bullet=False):
    """One sense: its labels are the parenthesis it starts with ("(vulgar, slang) ..."), its gloss the rest (a
    censored pane smears the gloss of a meaning the rules found rude, by its first rudeness.GLOSS_KEY characters)."""
    m = _LABELS.match(text)
    labels = [x.strip() for x in m.group(1).split(",")] if m else []
    return {"num": num, "pos": pos, "text": text, "example": None, "labels": labels,
            "gloss": text[m.end():] if m else text, "bullet": bullet}


def parse_definition(text):
    """Split stored definition text into senses for display (UI-12):
    [{"num": "1", "pos": "noun", "text": "...", "example": "..." or None, "labels": [...], "gloss": "..."}, ...].

    Understands the formats written by _wordnet / _online ('1. (noun) text' lines, each optionally followed
    by an indented 'e.g. "..."' line) and by the Wiktionary build ('\u2022 (noun) (vulgar) text' lines, one sense
    each). Anything else becomes one sense with no number or part of speech, so odd or old cached text still shows.
    """
    senses = []
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        ex = _EXAMPLE.match(line)
        if ex and senses and senses[-1]["example"] is None:
            senses[-1]["example"] = ex.group(1)
            continue
        m, b = _SENSE.match(line), _BULLET.match(line)
        if m:
            senses.append(_sense(m.group(1), m.group(2) or "", m.group(3).strip()))
        elif b:
            senses.append(_sense("", b.group(1) or "", b.group(2).strip(), bullet=True))
        elif senses and not senses[-1]["num"] and not senses[-1]["bullet"]:
            senses[-1]["text"] += " " + line.strip()
        else:
            senses.append(_sense("", "", line.strip()))
    return senses


# a meaning that only names another word ("Alternative form of bull dyke.", "plural of dog", "Clipping of homosexual."):
# the pane shows that word's own first meaning under it (F-3)
_FORM_OF = re.compile(r"^(?:(?:alternative|obsolete|archaic|dated|nonstandard|rare|informal|eye|dialect|pronunciation|"
                      r"letter-case|simple|past|present|third-person|first-person|second-person|singular|plural|"
                      r"indicative|and|participle|gerund|superlative|comparative|form|spelling|misspelling|clipping|"
                      r"abbreviation|initialism|acronym|contraction|ellipsis|synonym|feminine|masculine|tense)[\s,-]+)+"
                      r"of\s+([^\s,;:()\u201c\"]+(?: [^\s,;:()\u201c\"]+){0,3}?)\s*(?:\(|[.,;:]|$)", re.I)


def form_target(gloss):
    """The word a meaning only names ("Alternative form of bull dyke." -> "bull dyke"), or None."""
    m = _FORM_OF.match(gloss.strip())
    return m.group(1).rstrip(".") if m else None


def main_sense(text):
    """A definition's first sense that is not itself only a form of another word (parse_definition), or None."""
    return next((s for s in parse_definition(text) if not form_target(s["gloss"])), None)


class Definitions:
    """Threaded definition lookup. One worker thread; requests and results travel through queues."""
    def __init__(self, store):
        """Start the worker thread. `store` is only read here (the cached-definition check)."""
        self.store = store
        self.req = queue.Queue()
        self.res = queue.Queue()
        self.pending = set()
        threading.Thread(target=self._worker, daemon=True).start()

    def request(self, word):
        """Cached text, or None (a lookup is then queued; poll drain())."""
        cached = self.store.get_def(word)
        if cached is not None:
            return cached
        if word not in self.pending:
            self.pending.add(word)
            self.req.put(word)
        return None

    def drain(self):
        """Finished lookups since the last call, as a list of (word, text, found). Never blocks."""
        out = []
        while True:
            try:
                word, text, found = self.res.get_nowait()
            except queue.Empty:
                return out
            self.pending.discard(word)
            out.append((word, text, found))

    @staticmethod
    def _load_wordnet():
        """nltk's WordNet, read in (downloading its data once if needed and allowed), or None."""
        try:
            from nltk.corpus import wordnet as _wn

            try:
                _wn.synsets("dog")
            except LookupError:                     # nltk is installed but not the dictionary data yet
                if os.environ.get(OFFLINE_ENV):
                    raise
                import nltk
                nltk.download("wordnet", quiet=True)
                _wn.synsets("dog")
            return _wn
        except Exception:
            return None

    def _worker(self):
        """Thread body: answer requests forever (WordNet first, then online). WordNet is read in at the first word
        not cached in the save, not at start: reading it takes seconds of Python, which slowed opening the main
        window by as much (a Wiktionary save caches its definitions, so it is often never needed)."""
        wn, loaded = None, False
        while True:
            word = self.req.get()
            if not loaded:
                wn, loaded = self._load_wordnet(), True
            text = None
            try:
                if wn is not None:
                    text = self._wordnet(wn, word)
                if not text:
                    text = self._online(word)
            except Exception:
                text = None
            if text:
                self.res.put((word, text, True))
            else:
                self.res.put((word, "(No definition found.)", False))

    @staticmethod
    def _wordnet(wn, word):
        """Up to 10 numbered senses from WordNet with one example each, or None if the word is not in it."""
        syns = wn.synsets(word)
        if not syns:
            return None
        lines = []
        for i, s in enumerate(syns[:10], 1):
            line = f"{i}. ({POS_NAMES.get(s.pos(), s.pos())}) {s.definition()}"
            ex = s.examples()
            if ex:
                line += f'\n      e.g. "{ex[0]}"'
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _online(word):
        """Definitions from dictionaryapi.dev (up to 3 per part of speech, 10 in all), or None when offline/unknown."""
        if os.environ.get(OFFLINE_ENV):
            return None
        url = "https://api.dictionaryapi.dev/api/v2/entries/en/" + urllib.parse.quote(word)
        try:
            with urllib.request.urlopen(url, timeout=6) as r:
                data = json.load(r)
        except Exception:
            return None
        lines = []
        for entry in data if isinstance(data, list) else []:
            for m in entry.get("meanings", []):
                for d in m.get("definitions", [])[:3]:
                    lines.append(f"{len(lines) + 1}. ({m.get('partOfSpeech', '')}) {d.get('definition', '')}")
                    if len(lines) >= 10:
                        return "\n".join(lines)
        return "\n".join(lines) or None
