# `src/constants.py`

Shared constants and tiny pure helpers that every layer may use: tiers, modes, kinds of words, queue shapes, the program's `VERSION` and GitHub `REPO`, and the offline switch the tests set.

- **Uses:** the standard library only
- **Used by:** `app`, `browser`, `dealing`, `definitions`, `deps`, `errors`, `saves`, `sources`, `standalone`, `startup`, `store`, `tiercolours`, `tierlist`, `ui_chart`, `widgets`, `wordsource`
- **Tests:** `_selftest_dealing`, `_selftest_deps`, `_selftest_install`, `_selftest_lookup`, `_selftest_selfupdate`, `_selftest_sources`, `_selftest_startup`, `_selftest_updates`, `_selftest_widgets2`, `_selftest_zoom`

The module docstring has the details; this page is the map.

## Public API

- `tier_base`: Starting Elo rating for a word placed in tier t: S (0) = 1875 down to F (5) = 1125, 150 apart.
- `queue_weight`: How likely a word z spreads down the frequency list is to come up early, relative to the top word: e^-z (exponential) or e^-(z^2)/2 (gaussian).
- `card_label`: What the word card writes faintly above a word (asked for): its parts of speech, "compound word" for one made of words (it was on the frequency line), then for a...
- `kind_bits`: The words.kinds bit for a part of speech as Wiktionary, WordNet or dictionaryapi.dev name it.
- `typed_word`: A word typed to look up (UI-51): spaces at the ends gone, runs of spaces made one, and characters that show nothing (zero-width spaces, joiners) dropped: " ice cream"...
- `mask_word`: A censored word as plain text (ST-6), only where nothing can be drawn (messages): b•••••d.
- `plan_line`: A job's main steps as one log line (never shown): the progress window's "Step i of n" (parse_plan).
- `parse_plan`: The steps in a plan line, or None if `line` is not one.

## Rules and pitfalls (fixed before: keep them fixed)

- Standard library only: it sits at the bottom of the layers.
- `VERSION` must match the tag of a release (`v` + VERSION); the build workflow refuses a tag that does not.
- `mask_word` (b•••••d) is only for plain text (messages). Wherever a widget can draw, smear instead (`widgets.smear_items`).

## Changing it

- A new tier/mode/kind: here first, then the UI that lists it; the self-tests read these lists.
