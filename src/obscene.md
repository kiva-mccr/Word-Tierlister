# `src/obscene.py`

The kinds of rude meaning (Clinical, Crude, Swear, Insult, Sexual, Slur), which are dealt and which are smeared, and a short hand-picked list that stands in until a save has Wiktionary's meanings scored (OB-6).

- **Uses:** the standard library only
- **Used by:** `dealing`, `measure_rudeness`, `rudeness`, `store`, `wordsource`
- **Tests:** `_selftest_obscene`

The module docstring has the details; this page is the map.

## Public API

- `on_list`: True if `word` is on the hand-picked list (with its usual endings).
- `obscene_in`: The words among `words` on the hand-picked list, as a list.

## Rules and pitfalls (fixed before: keep them fixed)

- The rules in `rudeness.py` decide what is rude; the hand list only stands in. Do not grow it into a word list (the user chose rules).
- `CENSORED` (Crude, Swear, Sexual, Slur) is what gets smeared; Clinical and Insult never are.

## Changing it

- Which kinds start ticked: `TICKED`. Labels shown in stored definitions: `RUDE`.
