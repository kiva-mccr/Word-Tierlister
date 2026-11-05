# `src/review.py`

The review of rude meanings by hand (OB-9, a developer option: `python tierlist.py --review-rude`): a window that goes through a review file word by word, the rules' guess filled in for each meaning, and saves the answers beside it on every change. The answers only test and tune the rules (`tools/measure_rudeness.py answers`); the program never reads them.

- **Uses:** `constants`, `fonts`, `keymap`, `obscene`, `sizing`, `theme`, `ui_style`, `widgets`
- **Used by:** `app`, `tune_rudeness`
- **Tests:** `_selftest_devtools`, `_selftest_review`

The module docstring has the details; this page is the map.

## Public API

- `kind_colour`: A kind's pastel: a tier colour each (read now: they can be changed), Not rude the plain neutral.
- `read_review`: The review file's words, in order: [{"w", "why", "whole", "senses": [{"key", "pos", "labels", "gloss", "guess"}]}].
- `read_answers`: {word: {"keys", "kinds", "whole"}} from an answers file, or {} when there is none yet (or it was in the old six kinds: set aside, obscene.set_aside_old_answers).
- `write_answers`: Write every answer to `path` (the review's words in its order, then any others: answers from an earlier, smaller review are kept), through a temporary file, so a...
- `score_guesses`: The rules against the answers so far (the "Score the rules" bubble), from the review file alone: each answered meaning's answer against the rules' guess written into...
- `describe_score`: score_guesses' numbers in words, for the message.
- `RudeReview`: The review window (see the module's note).
  - methods: item, select, set_kind, toggle_whole, next_word, back, open_wiktionary, show_online, apply_keys, on_key, alive, close

## Rules and pitfalls (fixed before: keep them fixed)

- It opens with `ui_style.show_drawn`, complete (F-48).

- `score_guesses` (the Score the rules bubble) reads only the review file's own guesses: the program never runs the rules over the 300 MB entries; `measure_rudeness answers` scores the rules as they are now.
- Rules only (the user's choice): the answers are a yardstick for the rules, never a list the program reads.
- The word is never smeared here: judging a rude word needs to see it.
- A kind key leaves its meaning selected: moving on by itself lit the next meaning's kind, which read as the key
  changing the meaning below (reported). Down moves on.
- The lit kind lagged a step behind the arrow keys (the meaning navigated from): `set_enabled` on every redraw
  started a fade that ended at the old colour. Only change enabled when it changes; RoundButton.configure now
  stops a running fade when its colours change.
- Every key comes from the keymap's "review" group (App.apply_keys calls `apply_keys` here); Keyboard shortcuts
  shows that group only while the review is open (keymap.DEV_GROUPS).
- Back and Enter walk the file one word at a time (an answered word shows as answered). A history of words
  answered this time made Enter after Back jump to the first unanswered word, so Back no longer walked straight
  (reported).
- The Wiktionary button follows App.online (App._watch_online calls `show_online`); tests never go online.
- The answers file is rewritten whole through a `.part` file on every answer (a kind key or click, the whole word)
  and on Enter, so Back, quitting or a crash never loses a change (saving only on Enter lost a change before Back:
  reported).
- A new look (App.reopen) closes the review and App.take_over opens it again on the new window.

## Changing it

- The review file comes from `tools/measure_rudeness.py sample` (which meanings are asked about: `shown_meanings`);
  an answer matches a meaning by its first `rudeness.GLOSS_KEY` characters.
