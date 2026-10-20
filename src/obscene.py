"""Which words are obscene (ST-6: the "Obscene words" tick box and "Censor obscene words").

A short list chosen by hand: swear words, vulgar words for sex and the body, and slurs. Wiktionary's own labels
were tried first and caught far too much (a word with one vulgar or pejorative sense among many, such as
"bureaucracy", "box" or "screw", came out obscene). No tkinter, no internet.

    is_obscene("motherfuckers")    -> True   (a ROOTS word inside it)
    is_obscene("bitchy")           -> True   (a WORDS word with a usual ending)
    is_obscene("class")            -> False  (WORDS only match the whole word, so "ass" is not in "class")

Words whose usual meaning is innocent are left out on purpose (a cock is a rooster, a tit a bird, a dyke a wall,
to prick a finger): censoring them would hide everyday words. Edit the two lists to change what counts.
"""

import re

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


def is_obscene(word):
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
    """The obscene words among `words` (an iterable of words), as a list."""
    return [w for w in words if is_obscene(w)]
