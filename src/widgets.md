# `src/widgets.py`

The program's own widgets: buttons, the word card, tier pills, duel cards, the header menus and drop-downs, toasts, dialog frame, the definitions pane, smeared (censored) words and more. New widgets go here.

- **Uses:** `constants`, `definitions`, `fonts`, `rudeness`, `sizing`, `smooth`, `theme`, `ui_motion`
- **Used by:** `app`, `browser`, `dealing`, `errors`, `filepicker`, `shortcuts`, `sources`
- **Tests:** `_selftest_deps`, `_selftest_errors`, `_selftest_filepicker`, `_selftest_motion`, `_selftest_release`, `_selftest_ui`, `_selftest_widgets`, `_selftest_widgets2`

The module docstring has the details; this page is the map.

## Public API

- `smear_items`: Smear the text `item` sideways (ST-6): copies of it side by side over SMEAR_SPREAD letter widths, in one pale tone (so none of them stays crisp on top), cut off...
- `Unsmear`: A censored word (ST-6) on one of our canvases: its text item is hidden behind a sideways smear (smear_items); `clear` (0 = smeared, 1 = the word itself) eases toward...
  - methods: place, paint, hover
- `RoundButton`: A rounded, pastel button with a hover tint, a pressed 'dip', a disabled look and a key hint.
  - methods: configure, cget, set_enabled, enabled, set_selected, refresh, invoke, flash
- `TierRow`: The six tier pills S..F, each with its key hint (1-6), a hover lift and the pressed dip (UI-7).
- `TierChip`: A small tier label drawn like the tier pills (rounded, pastel, a faint edge of the same hue), for places that name a tier without being a button: the Anchor words...
  - methods: refresh
- `DuelCards`: The duel view's controls (UI-8): two big word cards side by side, each with a hover ring and its key hint, and quiet Tie / Skip text buttons under them.
  - methods: buttons, resolve, anim_key, show, set_enabled
- `AnchorLadder`: The S..F strip shown while a word is placed by comparing it to anchors (UI-9).
  - methods: update_range, possible, refresh
- `TabBar`: Folder-style tabs over a page (UI-10): a hairline runs the full width under the tabs, and the chosen tab is drawn in the page colour with its sides and rounded top...
  - methods: tab_x, set, show_only, get, refresh
- `DropMenu`: A styled drop-down menu (UI-10): a borderless window with roomy rows, the pastel highlight, check marks and shortcut hints, used by the header's File / Edit / View /...
  - methods: labels, is_open, open, invoke, close
- `ChoiceButton`: A drop-down choice (UI-43): a soft button showing the current value and a little arrow; a click opens a DropMenu with the choices (a check mark on the current one).
  - methods: set_values, toggle, refresh
- `HeaderMenus`: The row of header menu buttons (File, Edit, View, Settings) with their DropMenus (UI-10).
  - methods: open_name, toggle, open_menu, close
- `Toast`: A small rounded message that fades in near the bottom of the page, stays a moment, and fades out (UI-11).
  - methods: cget, hurry, show, wiggle, fling, hide
- `definition_tags`: The text tags a definition pane uses (fill_definitions): the word in bold, muted numbers, the part of speech and examples in italics, senses indented.
- `fill_definitions`: Fill the definition pane `t` (a tk.Text) with [(word, definition text or None while it is being looked up, the keys of its meanings to smear, True if the word itself...
- `smeared_label`: A small canvas showing `text` smeared (smear_items; wrapped at `width` pixels, 0: one line), for the places that are not our own canvases (the definition panes,...
- `TreeSmears`: Censored words in one column of a ttk.Treeview (Browse's list), smeared as everywhere else (asked for: no more b•••••d).
  - methods: refresh
- `DefinitionDrawer`: The definition pane (UI-12): eases open and closed instead of snapping, and shows each word in bold with its senses numbered, the part of speech in italics and...
  - methods: show_words, is_open, settle, set_open, collapse, lines_needed, natural_height, open, close
- `ShapeCard`: One of the queue dialog's two shape choices (UI-41): a little card with the shape's soft pastel curve (how likely a word is to come up early, from rank #1 to...
  - methods: set, refresh, median_rank
- `short_rank`: 13,863 -> '13.9k', 250,000 -> '250k', 1,200,000 -> '1.2M', 840 -> '840'.
- `FileList`: A white rounded list of files and folders (UI-42): a muted icon, the name, a quiet detail (size, words placed) and a date per row; the selected row in lilac.
  - methods: line, selected, set_rows, select, move_selection, open_selected, scroll, refresh
- `EmptyCard`: A friendly "nothing to do here" card (UI-20): a soft rounded panel with a short title and a line of help, shown instead of greyed-out controls.
  - methods: set, refresh
- `WordCard`: The word being sorted: big text on a soft rounded white card with a faint shadow, and a muted sub-line under it (frequency rank, "skipped", "compound").
  - methods: padx, box, word, sub, censored, set, configure, cget, refresh, transition_from, find_box, begin_typing, end_typing, typed, type_key, note
- `Tooltip`: A small hover note (UI-13 / UI-15 / UI-33): appears after DELAY_MS of hovering, just below what it describes, and stays there (only its text changes over another part...
  - methods: text, show_at, hide
- `close_popups`: Close every drop-down the program has open (UI-43): all DropMenus (header menus, ChoiceButtons).
- `watch_focus`: When the whole program loses focus (another program came to the front), close its drop-downs (close_popups) and call on_lost().
- `dialog_open`: True while one of our dialogs (StyledDialog: a question, a message, a settings page) is on screen.
- `StyledDialog`: The shared dialog frame (UI-24): a bold headline, a muted line of explanation, a body to fill and a row of rounded buttons, the default one (what Enter presses) in...
  - methods: text, button, clear_buttons, show, refit, close, alive
- `refresh_widgets`: Re-measure every canvas widget of ours (RoundButton, WordCard, AnchorLadder, TabBar, the chart...) under `widget` after shared fonts were resized.

## Rules and pitfalls (fixed before: keep them fixed)

- A censored word is smeared (`smear_items` / `Unsmear`; `smeared_label` where it is not our canvas; `TreeSmears` over a Treeview), un-smearing under the pointer; never masked where a widget can draw.
- In a definitions pane the word un-smears while the pointer is anywhere over the pane (`_watch_pane`).
- The word card has a fixed size; per-word work never changes geometry (check with `tools/layout_trace.py`).
- After animating a frame's height, reset it to height 0 and `pack_propagate(True)`, or Tk flips between sizes forever.
- The folded definitions pane is placed, not packed, so its text can measure its lines before opening (F-2).
- No `ttk.Combobox` / `tk.Menu` pop-ups (they grab input on Linux): use `ChoiceButton` / `DropMenu`. Dialogs build on `StyledDialog` (`StyledDialog.text` for wrapped lines).
- Our dialogs mark their window (`styled_dialog`), so `dialog_open(root)` can tell when a question is on screen (nothing else may ask then).

## Changing it

- Test each new widget in `tests/_selftest_widgets2.py`.
