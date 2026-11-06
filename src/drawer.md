# `src/drawer.py`

The definitions pane: `DefinitionDrawer` (eases open and closed), `fill_definitions` (words and their senses in a tk.Text, rude meanings smeared, a Wiktionary link) and `word_at` (a word in a meaning to look up).

- **Uses:** `buttons`, `definitions`, `rudeness`, `smears`, `theme`
- **Used by:** `app`, `browser`, `review`, `widgets`
- **Tests:** `_selftest_drawer`, `_selftest_widgets2`

The module docstring has the details; this page is the map.

## Public API

- `definition_tags`: The text tags a definition pane uses (fill_definitions): the word in bold, muted numbers, the part of speech and examples in italics, senses indented.
- `fill_definitions`: Fill the definition pane `t` (a tk.Text) with [(word, definition text or None while it is being looked up, the keys of its meanings to smear, True if the word itself...
- `word_at`: (start index, end index, the word) under the point x, y of the definition pane `t`, inside a meaning, an example or a form's line (LINK_TAGS), or None (a heading, a...
- `DefinitionDrawer`: The definition pane (UI-12): eases open and closed instead of snapping, and shows each word in bold with its senses numbered, the part of speech in italics and...
  - methods: columns, set_lines, lines, line_height, show_words, is_open, settle, set_open, collapse, natural_height, height_for, steady, ease_from, pin, unpin, opening, open, close

## Rules and pitfalls (fixed before: keep them fixed)

- `DefinitionDrawer.pin()` / `unpin()` (F-41): while App changes its lines (`_fill_pane`) or fits the window, the pane and its box keep the height they show and the scroll bars stay as they are (`_pin_box`); a pane stopped sliding open eases on from there at `unpin()`. `ease_from` starts from the pinned height, so unpin with `follow=False` before it.
- The definitions pane's two columns (UI-60) together ask no more width than its one column (each less its padding and the hairline): two plain halves made a zoomed duel tab too wide, so it was shown smaller. Set its height with `set_lines`, never on one text.
- Definition links (W-1): `word_at` only answers inside `LINK_TAGS` and over a real letter (past a line's end the nearest index is not under the pointer); `_watch_links` binds once per pane, so `on_word` is read from the pane at click time. Text tag bindings (the "Back to" line) follow the last motion: tests send a `<Motion>` first.
- In a definitions pane the word un-smears while the pointer is anywhere over the pane (`_watch_pane`).
- After animating a frame's height, reset it to height 0 and `pack_propagate(True)`, or Tk flips between sizes forever.
- The folded definitions pane is placed, not packed, so its text can measure its lines before opening (F-2).

## Changing it

- Test each new widget in `tests/_selftest_widgets2.py`.
- The Wiktionary link (UI-67, `_place_link`, `LinkButton`) is placed over the pane's top right; a canvas's `lift()` raises items, so it is raised with `tk.Misc.lift`. The word's line gets a right margin so a long word never runs under it.
- The drawer's contents are placed for good and its height is always set (F-27): by the slide, else from the contents (`_follow`, on their `<Configure>`). Never switch them between place and pack: the switch at each slide's end unmapped and remapped them, and on a compositing desktop (GNOME on Wayland, Windows) a frame now and then showed the pane without them, the whole pane seeming to dip (F-20, F-22, F-27; `_selftest_drawer` counts the unmaps).
- Opening, the drawer never lets the page move against its slide (F-22, `_selftest_drawer` under openbox): it slides into room the window already keeps for it (Z-1: the window never grows for it, so `give`, F-23, is gone). Closing, it is left at a pixel and unpacked (it drew one frame at full height when its natural size came back first). Its gap below (`gap`) is inside it, so it slides shut too.
- A definitions pane's italics (part of speech, examples) are a copy of the body font's size: `definition_tags` keeps the body on the Text and `refresh_widgets` sets them again after a zoom (F-26: they kept their old size until the pane was refilled).
- `ease_from(height)` (F-29): after its lines changed (a tab, a comparison: App._fill_pane), it shows it back at `height` and eases to the new one; `easing` is true meanwhile (App settles it before the next fit measures).
- `height_for(lines)` works its height out from one measurement (App counts the pane at its shortest in the worst case, Z-1); the pane never grows for a longer definition, it scrolls (F-28's `hold` / `give` are gone).
- Smeared meanings in a pane (W-2, asked for): when the entry's word is smeared too, they are the pane's (`hover=False`, in `_words`) and un-smear with the pointer anywhere over it; otherwise each under the pointer. Once shown, their words are clickable like the pane's (`smeared_label(on_word=)`, `_canvas_word`: a canvas text only says which letter is under a point, so a word's ends are measured by laying out the text up to each).
