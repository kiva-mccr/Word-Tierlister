# `src/obscene.py`

Which words are obscene (OB-14): the words on Surge AI's published profanity list (`src/wordlists/profanity_en.csv`, MIT), less the ordinary words in `src/wordlists/not_obscene.txt`; and Wiktionary's labels for a rude meaning (`RUDE`, `HEDGES`), which the stored definitions show.

- **Uses:** the standard library only
- **Used by:** `store`, `wordsource`
- **Tests:** `_selftest_obscene`, `_selftest_wikt`

The module docstring has the details; this page is the map.

## Public API

- `plain`: Lower case, without the hyphens and spaces that join words ("mother-fucker") and with straight apostrophes.
- `is_obscene`: True if `word` is on the list (and not in not_obscene.txt).
- `obscene_in`: The words among `words` on the list, as a list.

## Rules and pitfalls (fixed before: keep them fixed)

- The user chose a published list over rules (OB-14: the rules, OB-6..OB-13, never reached a point they were happy with;
  archived on branch `archive/censoring`). Keep `profanity_en.csv` exactly as published: fix a word it gets wrong in
  `not_obscene.txt`. One list, no kinds: a listed word is obscene whole, in every meaning.
- `LIST_VERSION` is a hash of both files: any change makes every save mark its words again (prepare_queue).
- Words are matched by `plain` (lower case, no joining hyphens or spaces), so "mother-fucker" counts as "motherfucker".

## Changing it

- Clear a word the list gets wrong: a line in `not_obscene.txt`. Labels shown in stored definitions: `RUDE`, `HEDGES`.
