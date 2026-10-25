# `src/widgets.py`

The program's own widgets: buttons, the word card, tier pills, duel cards, the header menus and drop-downs, toasts, dialog frame, the definitions pane, smeared (censored) words and more. New widgets go here.

- **Uses:** `constants`, `definitions`, `fonts`, `rudeness`, `sizing`, `smooth`, `theme`, `ui_motion`
- **Used by:** `app`, `browser`, `dealing`, `errors`, `filepicker`, `shortcuts`, `sources`, `tiercolours`
- **Tests:** `_selftest_deps`, `_selftest_drawer`, `_selftest_errors`, `_selftest_filepicker`, `_selftest_freeze`, `_selftest_motion`, `_selftest_release`, `_selftest_sizing`, `_selftest_ui`, `_selftest_widgets`, `_selftest_widgets2`, `_selftest_zoom`

The module docstring has the details; this page is the map.

## Public API

- `smear_items`: Smear the text `item` sideways (ST-6): copies of it side by side over SMEAR_SPREAD letter widths, in one pale tone (so none of them stays crisp on top).
- `Unsmear`: A censored word (ST-6) on one of our canvases: its text item is hidden behind a sideways smear (smear_items); `clear` (0 = smeared, 1 = the word itself) eases toward...
  - methods: place, paint, hover
- `RoundButton`: A rounded, pastel button with a hover tint, a pressed 'dip', a disabled look and a key hint.
  - methods: configure, cget, set_enabled, enabled, set_selected, refresh, invoke, flash
- `TierRow`: The six tier pills S..F, each with its key hint (1-6), a hover lift and the pressed dip (UI-7).
- `TierChip`: A small tier label drawn like the tier pills (rounded, pastel, a faint edge of the same hue), for places that name a tier without being a button: the Anchor words...
  - methods: refresh, set_color
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
- `LinkButton`: A small icon (smooth.ICONS) that does something when clicked, muted until hovered, with a hover note: the Wiktionary link at the top right of a definition (asked for).
  - methods: refresh
- `fill_definitions`: Fill the definition pane `t` (a tk.Text) with [(word, definition text or None while it is being looked up, the keys of its meanings to smear, True if the word itself...
- `word_at`: (start index, end index, the word) under the point x, y of the definition pane `t`, inside a meaning, an example or a form's line (LINK_TAGS), or None (a heading, a...
- `smeared_label`: A small canvas showing `text` smeared (smear_items; wrapped at `width` pixels, 0: one line), for the places that are not our own canvases (the definition panes,...
- `TreeSmears`: Censored words in one column of a ttk.Treeview (Browse's list), smeared as everywhere else (asked for: no more b•••••d).
  - methods: refresh
- `DefinitionDrawer`: The definition pane (UI-12): eases open and closed instead of snapping, and shows each word in bold with its senses numbered, the part of speech in italics and...
  - methods: columns, set_lines, lines, show_words, is_open, settle, set_open, collapse, lines_needed, natural_height, unshown_height, give, steady, ease_from, hold, open, close
- `ShapeCard`: One of the queue dialog's two shape choices (UI-41): a little card with the shape's soft pastel curve (how likely a word is to come up early, from rank #1 to...
  - methods: set, refresh, median_rank
- `short_rank`: 13,863 -> '13.9k', 250,000 -> '250k', 1,200,000 -> '1.2M', 840 -> '840'.
- `FileList`: A white rounded list of files and folders (UI-42): a muted icon, the name, a quiet detail (size, words placed) and a date per row; the selected row in lilac.
  - methods: line, selected, set_rows, select, move_selection, open_selected, scroll, refresh
- `EmptyCard`: A friendly "nothing to do here" card (UI-20): a soft rounded panel with a short title and a line of help, shown instead of greyed-out controls.
  - methods: set, refresh
- `WordCard`: The word being sorted: big text on a soft rounded white card with a faint shadow, and a muted sub-line under it (frequency rank, "skipped", "compound").
  - methods: padx, box, word, sub, censored, kind, set, configure, cget, refresh, transition_from, find_box, begin_typing, end_typing, typed, type_key, note
- `Tooltip`: A small hover note (UI-13 / UI-15 / UI-33): appears after DELAY_MS of hovering, just below what it describes, and stays there (only its text changes over another part...
  - methods: text, show_at, hide
- `close_popups`: Close every drop-down the program has open (UI-43): all DropMenus (header menus, ChoiceButtons).
- `watch_focus`: When the whole program loses focus (another program came to the front), close its drop-downs (close_popups) and call on_lost().
- `dialog_open`: True while one of our dialogs (StyledDialog: a question, a message, a settings page) is on screen.
- `StyledDialog`: The shared dialog frame (UI-24): a bold headline, a muted line of explanation, a body to fill and a row of rounded buttons, the default one (what Enter presses) in...
  - methods: text, button, clear_buttons, show, refit, rescale, close, alive
- `refresh_widgets`: Re-measure every canvas widget of ours (RoundButton, WordCard, AnchorLadder, TabBar, the chart...) under `widget` after shared fonts were resized; a definitions...

## Rules and pitfalls (fixed before: keep them fixed)

- The letters next to a line's ends move outward only `near` (em / 20, the space between letters), never over the end letter: "fart"'s a buried the f (F-39). Copies moved right are the line less its last letter, or less its last two past `near`; left likewise. The short runs (F-38) start at the third letter from either end and stop at the end letters.
- On one line the short letters' runs (SHORT_LETTERS) smear SHORT_SPREAD times as far, each capped at its room to the word's ends (F-38, the user's idea; a thin end letter such as the i of "imam" would let them out); not on wrapped text, where the many runs made the pane's frames twice as slow.
- The smear's band behind the letters runs only from the end of the first letter to the start of the last, hidden in the word (F-37, asked for): at the box's edges, then at the end letters' bodies (F-35), its flat ends still showed as a bar under the smear. Without it, white gaps show between round letters ("uc", "ss").
- A smear frame must stay cheap (F-36, reported as lag): its layout is worked out once per text and box (`_smear_layout`), its copies are plain items (tk.Canvas.create_text, no overhang tracking each) under one invisible guard over its whole reach, copies on big text sit `em / 40` pixels apart, and a card sliding in moves its smear instead of drawing it again. A copy moved right is the line less its last letter, one moved left less its first: one item a copy.
- A smear never reaches past its word (F-33, the user's rules): each line's first and last letter smear only inward over the same spread, the letters between both ways (`smear_items`, `_smear_lines`). The straight cut-off strips it had cut through letters that reach past their boxes (Young Serif's j and f), and a smeared label's canvas, only as wide as its text, cropped the outer copies (the definitions pane).
- A button's and a pill's edge is its fill `EDGE` (0.07) of the way to the ink (UI-78: the user chose it softer from mock-ups); keep RoundButton and TierChip on the same constant.
- The definitions pane's two columns (UI-60) together ask no more width than its one column (each less its padding and the hairline): two plain halves made a zoomed duel tab too wide, so it was shown smaller. Set its height with `set_lines`, never on one text.
- Definition links (W-1): `word_at` only answers inside `LINK_TAGS` and over a real letter (past a line's end the nearest index is not under the pointer); `_watch_links` binds once per pane, so `on_word` is read from the pane at click time. Text tag bindings (the "Back to" line) follow the last motion: tests send a `<Motion>` first.
- WordCard's kind label (UI-59) lives in the top margin and never changes the card's size; it is placed from the letters' real tops (0.8 em above the baseline) and its font shrinks to fit (asked for: never clipped). Check by pixels at small and large zooms.
- `smear_items`: one text copy per whole pixel, side copies faded into the paper by half a pixel apart, the middle copy drawn last. Copies stacked on one pixel looked bold on small text and then snapped (the definitions pane); check the last frames' ink against the plain word.
- A censored word is smeared (`smear_items` / `Unsmear`; `smeared_label` where it is not our canvas; `TreeSmears` over a Treeview), un-smearing under the pointer; never masked where a widget can draw.
- In a definitions pane the word un-smears while the pointer is anywhere over the pane (`_watch_pane`).
- The word card has a fixed size; per-word work never changes geometry (check with `tools/layout_trace.py`).
- After animating a frame's height, reset it to height 0 and `pack_propagate(True)`, or Tk flips between sizes forever.
- The folded definitions pane is placed, not packed, so its text can measure its lines before opening (F-2).
- No `ttk.Combobox` / `tk.Menu` pop-ups (they grab input on Linux): use `ChoiceButton` / `DropMenu`. Dialogs build on `StyledDialog` (`StyledDialog.text` for wrapped lines).
- Our dialogs mark their window (`styled_dialog`), so `dialog_open(root)` can tell when a question is on screen (nothing else may ask then).
- `StyledDialog.refit` keeps the dialog on its monitor (`sizing.keep_on_screen`).

## Changing it

- Test each new widget in `tests/_selftest_widgets2.py`.
- A censored word shown under a pointer that is not moving gets no pointer event: `WordCard.set` asks where the pointer is (`_pointer_check`) and a hovered `RoundButton` un-smears its new word itself (F-15). The outgoing word is still reset to smeared first, so it never leaves readable.
- The kind above a rude word (UI-59) stays on top of every smear on the card (`WordCard._draw` raises it last): the outgoing word's smear slides up over the kind on a skip (F-15; its cut-off strips, the height of the word's line, are gone since F-33).
- The kind has a row of its own (F-15, asked for): the word under it is drawn at `KIND_SCALE`, every card is `KIND_ROOM` taller (so the card's size never depends on the word), and the kind stays `KIND_GAP` clear of the letters' measured tops (the line's box starts barely above tall letters). Growing the card more costs the 1366 x 768 laptop its last zoom step (`_selftest_zoom`): take the room from the padding instead.
- The card's label (`kind`) is any short text: the App passes `constants.card_label` (parts of speech, then the rude kind, UI-63); the card never decides what it says.
- While typing on the card (UI-51) `set()` only keeps the word for afterwards (`_saved`, with its label); the typing display uses `_put`. A refresh mid-typing used to replace what was typed while keys still went to the typing, and Escape brought the word back without its label (F-16).
- An open dialog follows a change of the shared fonts (a zoom; maximizing brings back the maximized window's own, UI-57): `refresh_widgets` calls `StyledDialog.rescale`, which re-wraps every wrapped label in proportion, then sizes and centres the dialog again. Without it the text grew inside a window that kept its size and was cut off (F-18).
- The Wiktionary link (UI-67, `_place_link`, `LinkButton`) is placed over the pane's top right; a canvas's `lift()` raises items, so it is raised with `tk.Misc.lift`. The word's line gets a right margin so a long word never runs under it.
- The drawer's contents are placed for good and its height is always set (F-27): by the slide, else from the contents (`_follow`, on their `<Configure>`). Never switch them between place and pack: the switch at each slide's end unmapped and remapped them, and on a compositing desktop (GNOME on Wayland, Windows) a frame now and then showed the pane without them, the whole pane seeming to dip (F-20, F-22, F-27; `_selftest_drawer` counts the unmaps).
- Opening, the drawer never lets the page move against its slide (F-22, `_selftest_drawer` under openbox): the room a window grows by for it is handed over in the same layout as the window's new size (`give`, from App's `<Configure>`, on top of the height it has then: a window manager may grow the window only after the slide has begun, F-23, and taken as its whole height the pane's text dropped a little; held before the resize, the page jumped up, after it, down). Closing, it is left at a pixel and unpacked (it drew one frame at full height when its natural size came back first). Its gap below (`gap`) is inside it, so it slides shut too.
- A definitions pane's italics (part of speech, examples) are a copy of the body font's size: `definition_tags` keeps the body on the Text and `refresh_widgets` sets them again after a zoom (F-26: they kept their old size until the pane was refilled).
- `ease_from(height)` (F-29): after a fit changed its height, it shows it back at `height` and eases to the new one; `easing` is true meanwhile (App settles it before the next fit measures).
- Growing for a longer definition (F-28): `hold()` keeps its height while the window is fitted (`give` hands it what the window gains), then `open()` eases it from there to its new height. Never let `_follow` set a taller height in one go while it is open.
- Smeared meanings in a pane (W-2, asked for): when the entry's word is smeared too, they are the pane's (`hover=False`, in `_words`) and un-smear with the pointer anywhere over it; otherwise each under the pointer. Once shown, their words are clickable like the pane's (`smeared_label(on_word=)`, `_canvas_word`: a canvas text only says which letter is under a point, so a word's ends are measured by laying out the text up to each).
- The card's typing caret blinks (UI-70, `WordCard._blink`): shown on every key and redraw, still (shown) after `BLINK_FOR_MS` without a key, so nothing keeps running while idle.
- Never delete and remake a canvas item from its own tag Enter / Leave (or anything that runs then): the new item under the pointer is entered again and Tk loops for good, a freeze (F-21: the card's magnifier). Move and recolour it instead (`itemconfigure`).
