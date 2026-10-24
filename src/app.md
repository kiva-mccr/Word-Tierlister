# `src/app.py`

The main window (`App`): the header, the three placing views, the duel tabs, the chart and shelf, the definitions pane, the bottom bar, keys, zoom and window fitting, undo, and the background jobs it polls.

- **Uses:** `browser`, `constants`, `dealing`, `deps`, `errors`, `filepicker`, `fonts`, `keymap`, `rudeness`, `saves`, `shortcuts`, `sizing`, `sources`, `standalone`, `theme`, `tiercolours`, `ui_chart`, `ui_motion`, `ui_style`, `widgets`, `wordsource`
- **Used by:** `speed_check`, `stress_ui`, `tierlist`
- **Tests:** `_selftest_build`, `_selftest_defsize`, `_selftest_filepicker`, `_selftest_looks`, `_selftest_lookup`, `_selftest_release`, `_selftest_sizing`, `_selftest_sources`, `_selftest_ui`, `_selftest_ui2`, `_selftest_zoom`

The module docstring has the details; this page is the map.

## Public API

- `format_stats`: The status line (UI-15): one quiet line.
- `local_midnight`: The start of today, local time, as a timestamp.
- `apply_look`: The look the save asks for (UI-61, UI-62): dark mode (meta dark_mode) and the tier colours (meta tier_colors, six #RRGGBB as JSON), applied to theme before a window...
- `reopen_while_asked`: After the window closed: while it closed to reopen (App.reopen: a new look), build it again in that look on a new root (new_root() -> a hidden Tk with fonts and...
- `App`: The main window and the state of what is currently on screen.
  - methods: open_window, set_zoom, zoom_step, toggle_defs, toggle_motion, toggle_censor, censor_note, toggle_auto, toast, flash, refresh, after_external_change, modes_with_work, apply_keys, place_word, skip_word, start_compare, cmp_answer, cmp_back, pair_answer, skip_pair, start_focus, clear_focus, start_lookup, lookup_word, on_mode_change, undo, shown, on_key_release, on_key, next_tab, get_def, look_up, rude_read_note, anchors, note_anchor_changes, open_browser, edit_anchors, parse_queue_settings, queue_unchanged, add_launcher, source_updates, edit_tier_colours, toggle_dark, edit_keys, edit_dealing, show_save_location, describe_merge, merge_file, import_progress, offer_merge, export, reopen, on_close

## Rules and pitfalls (fixed before: keep them fixed)

- Window size: what shows = min(zoom, biggest that fits) x grow; re-fit from the zoom on every layout change, never ratchet down; measure minimum sizes at grow 1 (`_fit_window`).
- In a grown window the folded definitions pane counts at its full height and is shortened to fit (it once slid open over the word card).
- A definition that arrives while the pane slides open settles the slide before the fit (`_fit_defs`); fitted against the half-open pane it ended over the word card (F-8).
- Every key goes through `on_key` and the keymap; a held key repeats after 500 ms, then every 250 ms (`_repeat_allowed`).
- Messages: `flash(text, kind)`; each is its own toast, newest on top. Text-only places name a censored word with `shown()` (masked); everything drawn smears it.
- The window opens complete (`open_window`, F-1).
- The first start offers the other form once (`_offer_other_form`, T-9), never while a dialog is open (`widgets.dialog_open`), a job runs or a download is going; `App(offer_form=...)` is off unless `main()` turns it on, so tests never see it.
- Every word in a message goes through `shown()` (duel results too: they once printed censored words whole).
- `on_close` waits while `busy` (a worker writing the save) and cancels pending timers before destroying the window.
- The fit may shrink a big zoom to half the normal size on a small screen (`FIT_LOWEST` applies to the normal size, not the zoom).
- Two saved zooms (UI-57): `zoom_max` while maximized, `zoom` otherwise (`_zoom_key`); `_follow_maximize` applies the right one when the state changes. A fit never moves or resizes a maximized window (it would un-maximize). A zoom step is "in" only when it is bigger than zoom x grow (in a grown window 120% can be a step down: it was refused as "as big as fits").
- on_close cancels pending `after` jobs with Tcl's `after cancel`, never `after_cancel` (that deletes a command another widget still owns; root.destroy then raises "can't delete Tcl command").

## Changing it

- Building the window: `_build_ui` / `_build_header`. Placing / skipping: `place_word` / `skip_word`. Zoom: `set_zoom` / `zoom_step`.
- A word looked up on the card (UI-51) is tidied by `constants.typed_word`, needs a letter or a number, and is added in lower case. Undoing its placement or skip brings it back onto the card (`_was_looked_up`); Undo ends typing first (F-16).
- Turning censoring on calls `censor_note` (UI-64): a dialog once a save (meta `censor_noted`), a toast after. It must never wait (a modal one hung the tests and would block the How words are dealt page it opens over).
