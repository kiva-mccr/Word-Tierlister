# `src/dealing.py`

Settings > How words are dealt (ST-6): the order new words come in, which kinds of words (and "Obscene words": the list's, OB-14), and censoring; also the three-step page on the first start.

- **Uses:** `background`, `buttons`, `cards`, `constants`, `dialogs`, `fonts`, `popups`, `theme`
- **Used by:** `app`
- **Tests:** none of its own

The module docstring has the details; this page is the map.

## Public API

- `DealDialog`: The page (or, on the first start, the three steps) of How words are dealt; see the module's note.
  - methods: say, apply, buttons, alive, close

## Rules and pitfalls (fixed before: keep them fixed)

- Applying re-deals on a worker thread with `App.busy` and a moving bar; nothing else writes meanwhile.
- "Obscene words" is one plain tick box (OB-14, asked for: no kinds under it, so never the minus). A change to censoring alone applies at once, no re-deal, and calls `App.censor_shown` so the definitions and Browse follow.
