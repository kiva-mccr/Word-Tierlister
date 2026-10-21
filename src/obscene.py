"""Which words are obscene (ST-6: the "Obscene words" tick box and "Censor obscene words").

The rule (the user's): a word is flagged if MOST of its meanings are rude, or its FIRST meaning is. A meaning is
rude when Wiktionary labels it vulgar, offensive, derogatory / pejorative or a slur ("sometimes offensive" is not);
a meaning that is only a form of another word ("plural of bitch", "present participle of fuck") is rude when that
word is flagged. So "fuck" and "cunt" are, "bureaucracy" (one pejorative meaning of three), "box" and "screw" are
not. (A looser rule, any meaning rude, was tried and caught far too much.) The user's own answers in the review
(python tierlist.py --review-obscene) win over it.

    decide({"bitch": ["p", "r", "r"], "bitches": ["f:bitch"], "box": ["p", "p", "r", "p"]})  ->  {"bitch", "bitches"}

Each word's meanings come in as marks, in Wiktionary's order: "r" rude, "p" plain, "f:<word>" a form of <word>.
They are read from the Wiktionary download (tag_marks, for each sense's tags) or from a page's wikitext
(page_senses, for a save whose download is gone). Until a save has them (offline), the short list chosen by hand
below stands in (on_list). No tkinter, no internet.
"""

import re

RUDE = {"vulgar", "offensive", "derogatory", "pejorative", "slur", "ethnic slur", "racial slur", "swear word",
        "profane", "profanity", "ethnic-slur"}
HEDGES = {"sometimes", "possibly", "potentially", "occasionally", "may", "can", "rarely", "mildly", "slightly"}


def _verdict(marks, obscene):
    kinds = [m == "r" or (m.startswith("f:") and m[2:] in obscene) for m in marks]
    return bool(kinds) and (kinds[0] or 2 * sum(kinds) > len(kinds))


def decide(marks):
    """The obscene words among {word: [marks]} (see the module's note). Forms of forms are followed a few steps."""
    obscene = set()
    for _ in range(4):
        new = {w for w, m in marks.items() if _verdict(m, obscene)}
        if new == obscene:
            break
        obscene = new
    return obscene


def rude_labels(labels):
    """True if a list of labels says rude ("vulgar", "derogatory"), not hedged ("sometimes", "offensive")."""
    hedge = False
    for lab in (x.strip().lower().replace("_", " ") for x in labels):
        if not lab or lab in ("and", "or", "&", ",", "with"):
            continue
        words = lab.split()
        if lab in RUDE or (words and words[-1] in RUDE):
            if not hedge and not (len(words) > 1 and words[0] in HEDGES):
                return True
        hedge = bool(words) and words[-1] in HEDGES
    return False


def tag_marks(sense):
    """The mark for one sense of the Wiktionary download (kaikki.org's JSON: its "tags", "form_of" / "alt_of")."""
    target = (sense.get("form_of") or sense.get("alt_of") or [{}])[0].get("word")
    tags = [str(t).replace("-", " ") for t in sense.get("tags", [])] + [str(t) for t in sense.get("raw_tags", [])]
    if any(t.lower() in RUDE for t in tags) and not any(t.lower() in HEDGES for t in tags):
        return "r"
    return f"f:{target}" if target else "p"


_SECTION = re.compile(r"^==\s*English\s*==\s*$(.*?)(?=^==[^=].*==\s*$|\Z)", re.M | re.S)
_SENSE = re.compile(r"^#+(?![:*#])\s*(.*)$", re.M)
_TEMPLATE = re.compile(r"\{\{([^{}]*)\}\}")
_FORM_NAMES = ("alt form", "altform", "alt sp", "alt-sp", "alternative spelling", "alternative form", "obsolete spelling",
               "standard spelling", "nonstandard spelling", "misspelling", "abbreviation", "clipping", "short for")


_TEXT_TEMPLATES = {"l", "m", "ll", "w", "link", "mention", "taxlink", "vern", "gloss", "gl", "n-g", "ng",
                   "non-gloss", "non-gloss definition", "q", "qualifier", "i", "sense", "s"}
_LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
_MARKUP = re.compile(r"<ref[^>]*>.*?</ref>|<[^>]+>|'{2,}", re.S)


def page_senses(wikitext):
    """Each sense line ("# ...") of a Wiktionary page's English section, in order: (mark, its rude labels, its gloss
    as plain text). The mark is "r" by its {{lb|en|...}} labels, "f:<word>" for a form of another word
    ({{plural of|en|bitch}}, {{en-past of|fuck}}), else "p"."""
    m = _SECTION.search(wikitext or "")
    if not m:
        return []
    out = []
    for line in _SENSE.findall(m.group(1)):
        mark, rude = "p", []

        def text_of(t):
            nonlocal mark, rude
            parts = [x.strip() for x in t.group(1).split("|")]
            name = parts[0].lower()
            args = [x for x in parts[1:] if "=" not in x]
            if name in ("lb", "lbl", "label") and args[:1] == ["en"]:
                if rude_labels(args[1:]):
                    mark = "r"
                    rude = [a.replace("_", " ") for a in args[1:] if a.lower().replace("_", " ").split()[-1:] and
                            a.lower().replace("_", " ").split()[-1] in RUDE]
                return ""
            if name.endswith(" of") or name in _FORM_NAMES:
                target = args[0] if name.startswith("en-") else (args[1] if args[:1] == ["en"] and len(args) > 1 else None)
                if target and mark == "p":
                    mark = "f:" + target
                return f"{name} {target}" if target else ""
            if name in _TEXT_TEMPLATES and args:
                return args[-1]
            return ""
        gloss = _TEMPLATE.sub(text_of, line)
        gloss = _MARKUP.sub("", _LINK.sub(lambda g: g.group(1), gloss))
        out.append((mark, rude, " ".join(gloss.split())))
    return out


# a gloss that only says which word this is a form of ("plural of bitch", "present participle of fuck")
FORM_GLOSS = re.compile(r"\b(?:plural|participle|tense|form|spelling|singular|comparative|superlative|gerund|"
                        r"inflection|misspelling)\b.*\bof ([^\s,;:()]+)\s*$", re.I)
_TOKEN = re.compile(r"[a-z0-9]+")


def label_lines(text, senses, cutoff=0.5):
    """A stored definition (the Wiktionary build's "\u2022 (noun) gloss" lines) with Wiktionary's rude labels put
    in front of the senses they belong to: each line goes with the page sense whose gloss shares most of its
    words (at least `cutoff` of them, so a loose match labels nothing). Lines already labelled rude stay as
    they are. Returns the new text, or None if nothing changed."""
    page = [(set(_TOKEN.findall(g.lower())), rude) for mark, rude, g in senses if mark == "r" and rude]
    if not page:
        return None
    out, changed = [], False
    for line in (text or "").splitlines():
        m = re.match(r"^(\s*\u2022\s*(?:\([^)]*\)\s*)?)(?:\(([^()]*)\)\s*)?(.*)$", line)
        if not m or not m.group(3):
            out.append(line)
            continue
        head, labels, gloss = m.group(1), m.group(2), m.group(3)
        have = [x.strip() for x in labels.split(",")] if labels else []
        words = set(_TOKEN.findall(gloss.lower()))
        best = max(page, key=lambda p: len(words & p[0]) / max(1, len(words | p[0])))
        score = len(words & best[0]) / max(1, len(words | best[0]))
        if words and score >= cutoff and not rude_labels(have):
            have = list(best[1]) + have
            line = f"{head}({', '.join(have)}) {gloss}"
            changed = True
        out.append(line)
    return "\n".join(out) if changed else None


# ---- the short list chosen by hand: used until a save has Wiktionary's labels (offline) ------------------------
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
