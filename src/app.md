# `src/app.py`

The main window (`App`): the header, the three placing views, the duel tabs, the chart and shelf, the definitions pane, the bottom bar, keys, zoom and window fitting, undo, and the background jobs it polls.

- **Uses:** `browser`, `constants`, `dealing`, `definitions`, `deps`, `errors`, `filepicker`, `fonts`, `keymap`, `rudeness`, `saves`, `shortcuts`, `sizing`, `sources`, `standalone`, `theme`, `tiercolours`, `ui_chart`, `ui_motion`, `ui_style`, `widgets`, `wordsource`
- **Used by:** `speed_check`, `stress_ui`, `tierlist`
- **Tests:** `_selftest_build`, `_selftest_defsize`, `_selftest_filepicker`, `_selftest_looks`, `_selftest_lookup`, `_selftest_release`, `_selftest_sizing`, `_selftest_sources`, `_selftest_tabswitch`, `_selftest_ui`, `_selftest_ui2`, `_selftest_zoom`

The module docstring has the details; this page is the map.

## Public API

- `format_stats`: The status line (UI-15): one quiet line.
- `local_midnight`: The start of today, local time, as a timestamp.
- `apply_look`: The look the save asks for (UI-61, UI-62): dark mode (meta dark_mode) and the tier colours (meta tier_colors, six #RRGGBB as JSON), applied to theme before a window...
- `reopen_while_asked`: After the window's event loop ended: while it ended to reopen (App.reopen: a new look), build the window again in that look on a new root (new_root() -> a hidden Tk...
- `App`: The main window and the state of what is currently on screen.
  - methods: open_window, set_zoom, zoom_step, toggle_defs, toggle_motion, toggle_censor, censor_note, toggle_auto, toast, flash, refresh, after_external_change, modes_with_work, apply_keys, place_word, skip_word, start_compare, cmp_answer, cmp_back, pair_answer, skip_pair, start_focus, clear_focus, start_lookup, lookup_word, on_mode_change, undo, shown, on_key_release, on_key, next_tab, get_def, wiktionary_link, open_wiktionary, open_page, look_up, rude_read_note, anchors, note_anchor_changes, open_browser, edit_anchors, parse_queue_settings, queue_unchanged, add_launcher, source_updates, check_updates, edit_tier_colours, toggle_dark, edit_keys, edit_dealing, show_save_location, describe_merge, merge_file, import_progress, offer_merge, export, take_over, reopen, on_close

## Rules and pitfalls (fixed before: keep them fixed)

- Tk draws every layout the fit measures (`update_idletasks`), so a fit must never try sizes on screen one by one (F-41: switching tabs with the definitions pane open, the pane was tried a line at a time and the page stuttered; the duel cards blinked out). `_fit_window` pins the pane at the height it shows (`DefinitionDrawer.pin`, also a pane sliding open, which carries on to its new height after) and `_fit_lines` works the lines out from one measurement. `_content_size` counts the pane at its lines' height while `_measure_pane` is set (a held pane once counted at its old, taller height, so each duel tab got its own text size). The duel tabs share one `_fit_cache` key.
- From one duel tab to another the cards fade over to the new pair (`_fade_duel` -> `DuelCards.show(fade=True)`, under the duel's `anim_key`: a key press or a tab switch finishes it); the big text is sized for the new words when they show (`then=`).
- Never try a zoom on screen to see if it fits when it can be known before: `_precheck_zoom` tries the steps while the window is hidden (`open_window`) and `_remember_cap` keeps the limits in the save per screen and version (F-30). Estimating from the page's size failed: it grows 0.5-1.7x as fast as its text.
- The page keeps room for a one-line message under its contents (`_toast_room`, F-29/UI-72) inside its breathing room (max, not sum: a sum cost the laptop its 110%); `_recenter` keeps the contents above it.
- A fit that changes an open definitions pane's height eases it (`_fit_window` wraps `_fit_size`; F-29); tests that check the settled layout finish animations first.
- `_fit_defs` grows an open definitions pane as opening does (F-28): hold it, fit the window counting it at its new height (`folded_drawer=True`) with the room it gains going to it (`_room_from` / `_give_room`), then ease it open the rest of the way.
- A timer that reads the save checks it is still open (`App.shut`, `Store.closed`): the form offer's fired after closing and failed reading the closed save (F-25).
- Turning censoring on from View says it may not be fully accurate in a short toast (U-2, asked for: the same words as How words are dealt's line, never a longer note; never a window of its own, UI-71).
- Window size: what shows = min(zoom, biggest that fits) x grow; re-fit from the zoom on every layout change, never ratchet down; measure minimum sizes at grow 1 (`_fit_window`).
- A window grown by its minimum size alone gets that size set too (`_fit_window`): left to the minimum, it shrank back when the minimum fell (the definitions pane closing). The drawer opening only ever needs smaller text: its fit starts from the size shown, not the zoom (each size tried was drawn: the page swelled and stepped back, F-22). The centre contents are placed by their top (`_recenter`, also on their own `<Configure>`): centred by Tk plus an offset, two roundings shook them by a pixel.
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
- Turning censoring on calls `censor_note` (UI-64, U-2): a toast, never a dialog that waits (a modal one hung the tests and would block the How words are dealt page it opens over).
- Updates (U-1): `_check_for_update` runs only on main's starts (`offer_form`), at most once a day, and tells a version once; `_after_update` says an update happened once (meta `updated_from`, set by sources before the restart).
- A new look (UI-66): `reopen` ends the event loop with `after(0, quit)` (a quit asked before the loop runs is forgotten: the loop never ended), `reopen_while_asked` builds the new window while the old one is still up and sets `tk._default_root` to it (anything made without a master must not land on the old one), `take_over` copies place, size, maximized state, the looked-up word and Browse, and `_drop_old` closes the old one after it shows (also from `_shut`, so it never lingers).
- The two zooms (UI-57) must stay compatible (UI-69): the usual window never shows more than the maximized one. `set_zoom` calls `_keep_compatible`; opening lowers a usual zoom above the maximized one; `_grow_for` caps the growth of a big window that is not maximized at `zoom_max`.
