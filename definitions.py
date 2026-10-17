"""Word definitions: offline WordNet, online dictionaryapi.dev fallback, cached in the save.

Lookups run on a background thread so the window never freezes. Usage: call request(word) when a
definition is wanted (it returns cached text or None), then poll drain() from the UI loop for
finished lookups. Results are cached in the save file by the caller (App) via Store.set_def().
"""
import json
import queue
import threading
import urllib.error
import urllib.parse
import urllib.request


# --------------------------------------------------------------------------
# Definitions (WordNet offline, dictionaryapi.dev online fallback, cached)
# --------------------------------------------------------------------------
POS_NAMES = {"n": "noun", "v": "verb", "a": "adj", "s": "adj", "r": "adv"}


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

    def _worker(self):
        """Thread body: load WordNet if installed, then answer requests forever (WordNet first, then online)."""
        wn = None
        try:
            from nltk.corpus import wordnet as _wn

            try:
                _wn.synsets("dog")
            except LookupError:                     # nltk is installed but not the dictionary data yet
                import nltk
                nltk.download("wordnet", quiet=True)
                _wn.synsets("dog")
            wn = _wn
        except Exception:
            wn = None
        while True:
            word = self.req.get()
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
