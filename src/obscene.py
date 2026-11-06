"""Obscene words: the kinds of rude meaning (RUDE_KINDS: Expletive, Sexual, Slur, OB-12; TICKED: dealt to start
with; CENSORED: smeared while censoring to start with; RULE_KINDS: what the rules score, folded into them), the labels Wiktionary marks rude meanings with (RUDE: shown in the stored definitions), and a short
list chosen by hand (on_list), which stands in for a save whose Wiktionary meanings have not been read yet and for
a word added by hand (OB-6: src/rudeness.py decides by rules). No tkinter, no internet.

    on_list("motherfucker") -> True          obscene_in(words) -> the ones on the list
"""

import json
import os
import re

# Wiktionary's labels for a rude meaning (shown in the stored definitions, with their hedges: rudeness.HEDGES)
RUDE = {"vulgar", "offensive", "derogatory", "pejorative", "slur", "ethnic slur", "racial slur", "swear word",
        "profane", "profanity", "ethnic-slur"}


# ---- the short list chosen by hand ----------------------------------------------------------------------------
# Obscene wherever they appear, inside longer words too ("motherfucker", "bullshit", "dipshit").
ROOTS = ("fuck", "shit", "cunt", "nigger", "nigga", "wank", "jizz", "bollock", "cocksuck", "faggot")

# Obscene as the whole word, or with a usual ending (-s, -es, -ed, -ing, -er, -ers, -y, -ies, -iest, -ish...).
WORDS = (
    # swearing
    "ass", "arse", "asshole", "arsehole", "asshat", "jackass", "dumbass", "smartass", "fatass",
    "bastard", "bitch", "damn", "goddamn", "crap", "piss", "bugger", "douchebag", "dickhead",
    "knobhead", "bellend", "tosser", "skank", "slut", "whore", "twat",
    # sex and the body, vulgar words
    "dick", "pussy", "tits", "titty", "titties", "boobs", "dildo", "blowjob", "handjob", "rimjob",
    "cumshot", "clit", "butthole", "buttplug", "minge", "jerkoff", "queef",
    # slurs
    "fag", "kike", "spic", "wetback", "gook", "raghead", "towelhead", "beaner", "tranny", "paki", "chinaman",
    "darkie", "sambo", "golliwog", "pikey", "gyppo", "honky", "redskin", "shemale", "dago", "wop",
)

# Innocent words the rules above would catch: a ROOTS word inside them ("snigger", "swanky") ...
NOT_INSIDE = ("snigger", "niggard", "swank", "shittah", "shittim", "ashit", "ishit", "oshit", "ushit", "shitak",
              "shitai", "mishit", "shitzu", "peshitt", "wankel", "nwank", "kwank")
# ... or a WORDS word with an ending ("spicy", "craps", to "dicker")
NOT_OBSCENE = ("spicy", "spicier", "spiciest", "spices", "spiced", "spicer", "spicers", "spicing", "craps",
               "dicker", "dickers", "dickered", "dickering", "dicky", "dickey", "dickie", "dickies", "fagging",
               "fagged", "damning", "beanery", "beaneries", "crappie", "crappies", "asser", "twattle")

_ENDINGS = ("", "s", "es", "ed", "ing", "er", "ers", "y", "ies", "ier", "iest", "ish", "ness")
_WORDS = set(WORDS)


def _plain(word):
    """Lower case, without the hyphens and spaces that join words ("mother-fucker") and a possessive 's (an
    apostrophe inside stays: "who're" is not "whore")."""
    w = "".join(ch for ch in word.lower() if ch not in "- ").replace("\u2019", "'")
    return w[:-2] if w.endswith("'s") else w


_NOT_INSIDE = tuple(_plain(x) for x in NOT_INSIDE)
_NOT_OBSCENE = {_plain(x) for x in NOT_OBSCENE}
_ROOTS = re.compile("|".join(map(re.escape, ROOTS)))
_STARTS = {w[:2] for w in WORDS}                     # (a quick no for almost every word: a million in about 1 s)
_LONGEST = max(map(len, WORDS)) + max(map(len, _ENDINGS))


def on_list(word):
    """True if `word` is on the hand-picked list (with its usual endings)."""
    w = _plain(word)
    if _ROOTS.search(w) and not any(x in w for x in _NOT_INSIDE):
        return True
    if w[:2] not in _STARTS or len(w) > _LONGEST or w in _NOT_OBSCENE:
        return False
    for end in _ENDINGS:
        if end and not w.endswith(end):
            continue
        stem = w[:len(w) - len(end)] if end else w
        if stem in _WORDS:
            return True
        if end and len(stem) > 2 and stem[-1] == stem[-2] and stem[:-1] in _WORDS:     # "sluttish", "pissed"
            return True
        if end in ("ies", "ier", "iest", "ied") and stem + "y" in _WORDS:              # "titties"
            return True
    return False


def obscene_in(words):
    """The words among `words` on the hand-picked list, as a list."""
    return [w for w in words if on_list(w)]


# ---- kinds of rude words (OB-6: src/rudeness.py scores each meaning towards them) ----------------------------------
# OB-12 (asked for: the six kinds were hard to sort into): three broad kinds, every one smeared while censoring.
# Medical words, mild name-calling and toilet words are ordinary words.
RUDE_KINDS = ("expletive", "sexual", "slur")
TICKED = frozenset(("expletive",))    # dealt by default (Sexual and Slur left out)
CENSORED = frozenset(RUDE_KINDS)     # smeared while censoring to start with (each has its smear button, OB-7)
CENSORABLE = frozenset(RUDE_KINDS)
# what the rules' tables give points to (rudeness.py): finer than the kinds shown, folded into them per meaning
# (rudeness.fold: Swear, and Crude or Insult with a vulgar or offensive label, are Expletive; Clinical is none)
RULE_KINDS = ("clinical", "crude", "swear", "insult", "sexual", "slur")


def set_aside_old_answers(path):
    """A review's answers file written with the six kinds from before OB-12 is moved aside (the user: start the answers
    from scratch), to rude_review_answers_six_kinds.jsonl beside it (numbered if that is taken). True if it was."""
    try:
        with open(path, encoding="utf-8") as f:
            old = any(set(json.loads(line).get("kinds", ())) - {"clean", *RUDE_KINDS} for line in f if line.strip())
    except (OSError, ValueError, AttributeError, TypeError):
        return False
    if not old:
        return False
    base, ext = os.path.splitext(path)
    aside, n = f"{base}_six_kinds{ext}", 1
    while os.path.exists(aside):
        n += 1
        aside = f"{base}_six_kinds_{n}{ext}"
    os.replace(path, aside)
    return True
