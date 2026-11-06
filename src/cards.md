# `src/cards.py`

The drawn panels: the word card, the duel's two cards, the anchor strip, the "nothing to do here" card, the queue dialog's shape cards and the file picker's list.

- **Uses:** `buttons`, `constants`, `fonts`, `smears`, `smooth`, `theme`, `ui_motion`
- **Used by:** `app`, `dealing`, `filepicker`
- **Tests:** `_selftest_filepicker`, `_selftest_freeze`, `_selftest_tabswitch`, `_selftest_widgets`, `_selftest_widgets2`

The module docstring has the details; this page is the map.

## Public API

- `DuelCards`: The duel view's controls (UI-8): two big word cards side by side, each with a hover ring and its key hint, and quiet Tie / Skip text buttons under them.
  - methods: buttons, resolve, anim_key, show, set_enabled
- `AnchorLadder`: The S..F strip shown while a word is placed by comparing it to anchors (UI-9).
  - methods: update_range, possible, refresh
- `ShapeCard`: One of the queue dialog's two shape choices (UI-41): a little card with the shape's soft pastel curve (how likely a word is to come up early, from rank #1 to...
  - methods: set, refresh, median_rank
- `short_rank`: 13,863 -> '13.9k', 250,000 -> '250k', 1,200,000 -> '1.2M', 840 -> '840'.
- `FileList`: A white rounded list of files and folders (UI-42): a muted icon, the name, a quiet detail (size, words placed) and a date per row; the selected row in lilac.
  - methods: line, selected, set_rows, select, move_selection, open_selected, scroll, refresh
- `EmptyCard`: A friendly "nothing to do here" card (UI-20): a soft rounded panel with a short title and a line of help, shown instead of greyed-out controls.
  - methods: set, refresh
- `WordCard`: The word being sorted: big text on a soft rounded white card with a faint shadow, and a muted sub-line under it (frequency rank, "skipped", "compound").
  - methods: padx, box, word, sub, censored, kind, set, configure, cget, refresh, transition_from, find_box, begin_typing, end_typing, typed, type_key, note

## Rules and pitfalls (fixed before: keep them fixed)

- A ShapeCard redraws on `set` only when its spread or choice changed.
- RoundButton and WordCard redraw for a `wraplength` only when it changes (F-50: every re-fit sets it).
- `DuelCards.show(fade=True)` fades the cards into the page with `RoundButton.veil`, swaps the words, colours and widths while they are out of sight (`FADE_OUT`), and fades them back; `veil` stops the button's own fade so the two never fight.
- WordCard's kind label (UI-59) lives in the top margin and never changes the card's size; it is placed from the letters' real tops (0.8 em above the baseline) and its font shrinks to fit (asked for: never clipped). Check by pixels at small and large zooms.
- The word card has a fixed size; per-word work never changes geometry (check with `tools/layout_trace.py`).

## Changing it

- Test each new widget in `tests/_selftest_widgets2.py`.
- A censored word shown under a pointer that is not moving gets no pointer event: `WordCard.set` asks where the pointer is (`_pointer_check`) and a hovered `RoundButton` un-smears its new word itself (F-15). The outgoing word is still reset to smeared first, so it never leaves readable.
- The kind above a rude word (UI-59) stays on top of every smear on the card (`WordCard._draw` raises it last): the outgoing word's smear slides up over the kind on a skip (F-15; its cut-off strips, the height of the word's line, are gone since F-33).
- The kind has a row of its own (F-15, asked for): the word under it is drawn at `KIND_SCALE`, every card is `KIND_ROOM` taller (so the card's size never depends on the word), and the kind stays `KIND_GAP` clear of the letters' measured tops (the line's box starts barely above tall letters). Growing the card more costs the 1366 x 768 laptop its last zoom step (`_selftest_zoom`): take the room from the padding instead.
- The card's label (`kind`) is any short text: the App passes `constants.card_label` (parts of speech, then the rude kind, UI-63); the card never decides what it says.
- While typing on the card (UI-51) `set()` only keeps the word for afterwards (`_saved`, with its label); the typing display uses `_put`. A refresh mid-typing used to replace what was typed while keys still went to the typing, and Escape brought the word back without its label (F-16).
- The card's typing caret blinks (UI-70, `WordCard._blink`): shown on every key and redraw, still (shown) after `BLINK_FOR_MS` without a key, so nothing keeps running while idle.
- Never delete and remake a canvas item from its own tag Enter / Leave (or anything that runs then): the new item under the pointer is entered again and Tk loops for good, a freeze (F-21: the card's magnifier). Move and recolour it instead (`itemconfigure`).
