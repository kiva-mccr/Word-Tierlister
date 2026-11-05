# `src/obscene.py`

The kinds of rude meaning (Expletive, Sexual, Slur; OB-12), which are dealt and which are smeared, and a short hand-picked list that stands in until a save has Wiktionary's meanings scored (OB-6).

- **Uses:** the standard library only
- **Used by:** `dealing`, `measure_rudeness`, `review`, `rudeness`, `store`, `tune_rudeness`, `wordsource`
- **Tests:** `_selftest_obscene`

The module docstring has the details; this page is the map.

## Public API

- `on_list`: True if `word` is on the hand-picked list (with its usual endings).
- `obscene_in`: The words among `words` on the hand-picked list, as a list.
- `set_aside_old_answers`: A review's answers file written with the six kinds from before OB-12 is moved aside (the user: start the answers from scratch), to rude_review_answers_six_kinds.jsonl...

## Rules and pitfalls (fixed before: keep them fixed)

- The rules in `rudeness.py` decide what is rude; the hand list only stands in. Do not grow it into a word list (the user chose rules).
- The user chose three broad kinds (OB-12: the six were hard to sort into): every one is smeared to start with
  (`CENSORED`); medical words, mild name-calling and toilet words are ordinary words. `RULE_KINDS` are what the
  rules' tables score; never show them.
- An answers file in the old six kinds is set aside, never read (`set_aside_old_answers`: the user started again).

## Changing it

- Which kinds start ticked: `TICKED`. Labels shown in stored definitions: `RUDE`.
