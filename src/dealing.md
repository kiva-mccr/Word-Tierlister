# `src/dealing.py`

Settings > How words are dealt (ST-6): the order new words come in, which kinds of words (and which kinds of rude meaning under "Obscene words"), and censoring; also the three-step page on the first start.

- **Uses:** `background`, `buttons`, `cards`, `constants`, `dialogs`, `fonts`, `obscene`, `popups`, `rudeness`, `theme`
- **Used by:** `app`
- **Tests:** none of its own

The module docstring has the details; this page is the map.

## Public API

- `DealDialog`: The page (or, on the first start, the three steps) of How words are dealt; see the module's note.
  - methods: say, apply, buttons, alive, close

## Rules and pitfalls (fixed before: keep them fixed)

- "Obscene words" shows a minus while only some kinds under it are ticked (ttk's "alternate" state, set after a tick because a variable change clears it).
- Applying re-deals on a worker thread with `App.busy` and a moving bar; nothing else writes meanwhile.
- The kinds of rude meaning open while "Obscene words" or Censor obscene words is ticked (the smear buttons sit beside them). A change to censoring alone applies at once, no re-deal, and calls `App.censor_shown` so the definitions and Browse follow.
