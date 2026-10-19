"""Shared constants: tier names, modes, ranking defaults. Only the standard library, so anything can use it.
"""
import math


# Tier index 0..5 everywhere in the code and the database means S..F in this order.
TIERS = ["S", "A", "B", "C", "D", "F"]
DEFAULT_ANCHORS = ["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist"]
FOCUS_ROUNDS = 8  # duels in one "Refine this word" session
# (key, menu label) for the four sorting modes; the key is also what is saved in meta "mode".
MODES = [
    ("place", "Place new words"),
    ("refine", "Refine within tier"),
    ("boundary", "Boundary check"),
    ("conflict", "Resolve conflicts"),
]

# The progress shelf (UI-14): zones named for how often you would meet such a word in reading, by wordfreq's
# Zipf scale (log10 of uses per billion words): "page" words have Zipf >= 6 (about once a page or more), "chapter"
# 5-6, "book" 4-5, "shelf" 3-4, "library" below 3. Each step is ten times rarer.
SHELF_ZONES = ["page", "chapter", "book", "shelf", "library"]
SHELF_ZIPF = [6, 5, 4, 3]                     # the Zipf value where each zone ends
SHELF_ZONE_RANKS = [100, 1000, 7000, 30000]   # where they end by rank, until the word frequencies are known
SHELF_SPINES = 64                             # spines on the whole shelf
SHELF_SOFT = 30                               # the shelf is a log scale of rank + SHELF_SOFT (see Store.shelf_layout)


def tier_base(t):
    """Starting Elo rating for a word placed in tier t: S (0) = 1875 down to F (5) = 1125, 150 apart."""
    return 1500.0 + (2.5 - t) * 150.0


# Queue order (see Store.reshuffle). "spread" is in frequency ranks: with the exponential shape a
# word `spread` ranks further down the list is e times (about 2.7x) less likely to come up early.
# qshape "rank" is "Most common first" (ST-6): strictly by frequency, no randomness.
QUEUE_DEFAULTS = {"qspread": "20000", "qshape": "exp", "qcompound": "1.0"}
QUEUE_SHAPES = ("exp", "gauss", "rank")
# Push-back for compound words, in multiples of `spread` x the compound-strength setting:
# 0 = normal word, 1 = closed compound ("bookshelf"), 2 = hyphenated / multi-word ("well-known").
PEN_UNITS = {0: 0.0, 1: 1.0, 2: 1.5}


def queue_weight(shape, z):
    """How likely a word z spreads down the frequency list is to come up early, relative to the top word:
    e^-z (exponential) or e^-(z^2)/2 (gaussian). The same recipe Store.reshuffle sorts by."""
    return math.exp(-z * z / 2) if shape == "gauss" else math.exp(-z)


# half of the early words come from above rank median x spread (exponential: ln 2; gaussian: the half-normal's)
QUEUE_MEDIAN = {"exp": math.log(2), "gauss": 0.6745}
QUEUE_AXIS = 100_000             # the queue dialog's diagrams (UI-41) always run from rank #1 to this


# Kinds of words (ST-6): (key, label, bit in words.kinds). A word can be several kinds ("run": noun and verb);
# "other" is every other part of speech. words.kinds is NULL until known (counted as "other").
KINDS = [("noun", "Nouns", 1), ("verb", "Verbs", 2), ("adj", "Adjectives", 4), ("adv", "Adverbs", 8),
         ("other", "Other", 16)]
ALL_KINDS = 31
KIND_OF_POS = {"noun": 1, "verb": 2, "adj": 4, "adjective": 4, "adv": 8, "adverb": 8}
OTHER_KINDS_NOTE = ("Other: pronouns, prepositions, conjunctions, interjections, numbers, abbreviations, "
                    "contractions and the like.")


def kind_bits(pos):
    """The words.kinds bit for a part of speech as Wiktionary, WordNet or dictionaryapi.dev name it."""
    return KIND_OF_POS.get((pos or "").strip().lower(), 16)


def mask_word(word):
    """A censored word as text (ST-6), where a smear cannot be drawn (Browse's list, messages): b•••••d."""
    if len(word) <= 2:
        return "•" * len(word)
    return word[0] + "•" * (len(word) - 2) + word[-1]


# A long job can tell its progress window the main steps it will go through, up front: log(plan_line([...]))
# with the start of each step's stage line ("Downloading English Wiktionary", "Reading entries"). The window
# then shows "Step 2 of 4" in its corner as each of those stages starts (startup.run_with_progress). The plan
# line itself is never shown or printed; stage lines that match no step (a retry note) leave the count alone.
PLAN_MARK = "\x1eplan:"


def plan_line(steps):
    return PLAN_MARK + "\x1f".join(steps)


def parse_plan(line):
    """The steps in a plan line, or None if `line` is not one."""
    return line[len(PLAN_MARK):].split("\x1f") if line.startswith(PLAN_MARK) else None
