# `src/review.py`

The review of rude meanings by hand (OB-9, a developer option: `python tierlist.py --review-rude`): a window that goes through a review file word by word, the rules' guess filled in for each meaning, and saves the answers beside it after every word. The answers only test and tune the rules (`tools/measure_rudeness.py answers`); the program never reads them.

- **Uses:** `constants`, `fonts`, `keymap`, `sizing`, `theme`, `ui_style`, `widgets`
- **Used by:** `app`
- **Tests:** `_selftest_review`

The module docstring has the details; this page is the map.

## Public API

- `kind_colour`: A kind's pastel: a tier colour each (read now: they can be changed), Clean the plain neutral.
- `read_review`: The review file's words, in order: [{"w", "why", "whole", "senses": [{"key", "pos", "labels", "gloss", "guess"}]}].
- `read_answers`: {word: {"keys", "kinds", "whole"}} from an answers file, or {} when there is none yet.
- `write_answers`: Write every answer (in the review's order) to `path`, through a temporary file, so a crash mid-write never leaves half a file.
- `RudeReview`: The review window (see the module's note).
  - methods: item, select, set_kind, toggle_whole, next_word, back, apply_keys, on_key, alive, close

## Rules and pitfalls (fixed before: keep them fixed)

- Rules only (the user's choice): the answers are a yardstick for the rules, never a list the program reads.
- The word is never smeared here: judging a rude word needs to see it.
- Every key comes from the keymap's "review" group (App.apply_keys calls `apply_keys` here); Keyboard shortcuts
  shows that group only while the review is open (keymap.DEV_GROUPS).
- The answers file is rewritten whole through a `.part` file after every word, so quitting any time loses nothing.
- A new look (App.reopen) closes the review and App.take_over opens it again on the new window.

## Changing it

- The review file comes from `tools/measure_rudeness.py sample` (which meanings are asked about: `shown_meanings`);
  an answer matches a meaning by its first `rudeness.GLOSS_KEY` characters.
