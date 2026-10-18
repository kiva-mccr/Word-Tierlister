"""Shared constants: tier names, modes, ranking defaults. No imports, so anything can use it.
"""

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

# The progress bar's segments (UI-14), by frequency rank: each holds about ten times the words of the one before.
SEGMENT_NAMES = ["everyday", "common", "uncommon", "rare"]
SEGMENT_BOUNDS = [1000, 10000, 100000]      # ranks below 1,000 are everyday ... 100,000 and beyond are rare


def tier_base(t):
    """Starting Elo rating for a word placed in tier t: S (0) = 1875 down to F (5) = 1125, 150 apart."""
    return 1500.0 + (2.5 - t) * 150.0


# Queue order (see Store.reshuffle). "spread" is in frequency ranks: with the exponential shape a
# word `spread` ranks further down the list is e times (about 2.7x) less likely to come up early.
QUEUE_DEFAULTS = {"qspread": "20000", "qshape": "exp", "qcompound": "1.0"}
# Push-back for compound words, in multiples of `spread` x the compound-strength setting:
# 0 = normal word, 1 = closed compound ("bookshelf"), 2 = hyphenated / multi-word ("well-known").
PEN_UNITS = {0: 0.0, 1: 1.0, 2: 1.5}
