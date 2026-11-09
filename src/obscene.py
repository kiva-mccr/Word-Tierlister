"""Obscene words: the words on Surge AI's published profanity list (src/wordlists/profanity_en.csv, MIT), less the
ordinary words it catches (src/wordlists/not_obscene.txt). A listed word is obscene whole, in every meaning (asked
for: one list, no kinds, no rules). No tkinter, no internet.

    is_obscene("motherfucker") -> True
    LIST_VERSION                              changes with either file: every save marks its words again

Also Wiktionary's labels for a rude meaning (RUDE, with their hedges), which the stored definitions show.
"""

import csv
import hashlib
import os

WORDLISTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wordlists")   # (packed as "wordlists")
LIST_FILE = os.path.join(WORDLISTS, "profanity_en.csv")
NOT_OBSCENE_FILE = os.path.join(WORDLISTS, "not_obscene.txt")

# Wiktionary's labels for a rude meaning, and the hedges that go with them ("sometimes offensive"): shown before a
# meaning in the stored definitions (wordsource._summarize)
RUDE = {"vulgar", "offensive", "derogatory", "pejorative", "slur", "ethnic slur", "racial slur", "swear word",
        "profane", "profanity", "ethnic-slur"}
HEDGES = {"sometimes", "often", "mildly", "possibly", "potentially", "occasionally"}


def plain(word):
    """Lower case, without the hyphens and spaces that join words ("mother-fucker") and with straight apostrophes."""
    return "".join(ch for ch in word.lower() if ch not in "- ").replace("’", "'")


def _read():
    """(the listed words, plain, less the ones in not_obscene.txt; LIST_VERSION), read once."""
    digest = hashlib.sha256()
    words, cleared = set(), set()
    try:
        with open(LIST_FILE, "rb") as f:
            raw = f.read()
        digest.update(raw)
        words = {plain(row["text"]) for row in csv.DictReader(raw.decode("utf-8").splitlines()) if row.get("text")}
    except (OSError, ValueError, KeyError):
        pass
    try:
        with open(NOT_OBSCENE_FILE, "rb") as f:
            raw = f.read()
        digest.update(raw)
        cleared = {plain(line.strip()) for line in raw.decode("utf-8").splitlines()
                   if line.strip() and not line.lstrip().startswith("#")}
    except (OSError, ValueError):
        pass
    words.discard("")
    return frozenset(words - cleared), digest.hexdigest()[:12]


OBSCENE, LIST_VERSION = _read()


def is_obscene(word):
    """True if `word` is on the list (and not in not_obscene.txt)."""
    return bool(word) and plain(word) in OBSCENE
