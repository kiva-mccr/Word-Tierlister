# `src/smears.py`

Censored (obscene) words drawn smeared, and un-smearing under the pointer: on our canvases (`smear_items`, `Unsmear`), on a small canvas of its own for the definition panes (`smeared_label`) and over Browse's list (`TreeSmears`).

- **Uses:** `fonts`, `theme`, `ui_motion`
- **Used by:** `browser`, `buttons`, `cards`, `drawer`
- **Tests:** `_selftest_dealing`, `_selftest_widgets2`

The module docstring has the details; this page is the map.

## Public API

- `smear_items`: Smear the text `item` sideways (ST-6): copies of it side by side over SMEAR_SPREAD letter widths, in one pale tone (so none of them stays crisp on top).
- `Unsmear`: A censored word (ST-6) on one of our canvases: its text item is hidden behind a sideways smear (smear_items); `clear` (0 = smeared, 1 = the word itself) eases toward...
  - methods: place, paint, hover
- `smeared_label`: A small canvas showing `text` smeared (smear_items; wrapped at `width` pixels, 0: one line), for the places that are not our own canvases (the definition panes,...
- `TreeSmears`: Censored words in one column of a ttk.Treeview (Browse's list), smeared as everywhere else (asked for: no more b•••••d).
  - methods: refresh

## Rules and pitfalls (fixed before: keep them fixed)

- Aqua (macOS) leaves trailing spaces out of a text item's bbox: never take the end of the text before a word as where the word starts. `_canvas_word` measures up to the last letter before it and adds the spaces' width (a smeared pane's clickable word was underlined from the space before it, seen on GitHub's Macs, T-18).
- The letters' holes are filled with their own shapes (fonts.letter_holes, from overhang.json), never rectangles: those left white crescents at a hole's curves (F-40). The fill and the band go in the first FILL_FADE of un-smearing; both only on one line.
- The letters next to a line's ends move outward only `near` (em / 20, the space between letters), never over the end letter: "fart"'s a buried the f (F-39). Copies moved right are the line less its last letter, or less its last two past `near`; left likewise. The short runs (F-38) start at the third letter from either end and stop at the end letters.
- A line's first and last letters smear inward END_SPREAD times as far, behind the rest (F-43, asked for: their counters showed at the word's ends); never further than the word's other end, so a two-letter word stays inside itself.
- On one line the short letters' runs (SHORT_LETTERS) smear SHORT_SPREAD times as far, each capped at its room to the word's ends (F-38, the user's idea; a thin end letter such as the i of "imam" would let them out); not on wrapped text, where the many runs made the pane's frames twice as slow.
- The smear's band behind the letters runs only from the end of the first letter to the start of the last, hidden in the word (F-37, asked for): at the box's edges, then at the end letters' bodies (F-35), its flat ends still showed as a bar under the smear. Without it, white gaps show between round letters ("uc", "ss").
- A smear frame must stay cheap (F-36, reported as lag): its layout is worked out once per text and box (`_smear_layout`), its copies are plain items (tk.Canvas.create_text, no overhang tracking each) under one invisible guard over its whole reach, copies on big text sit `em / 40` pixels apart, and a card sliding in moves its smear instead of drawing it again. A copy moved right is the line less its last letter, one moved left less its first: one item a copy.
- A smear never reaches past its word (F-33, the user's rules): each line's first and last letter smear only inward over the same spread, the letters between both ways (`smear_items`, `_smear_lines`). The straight cut-off strips it had cut through letters that reach past their boxes (Young Serif's j and f), and a smeared label's canvas, only as wide as its text, cropped the outer copies (the definitions pane).
- `smear_items`: one text copy per whole pixel, side copies faded into the paper by half a pixel apart, the middle copy drawn last. Copies stacked on one pixel looked bold on small text and then snapped (the definitions pane); check the last frames' ink against the plain word.
- A censored word is smeared (`smear_items` / `Unsmear`; `smeared_label` where it is not our canvas; `TreeSmears` over a Treeview), un-smearing under the pointer; never masked where a widget can draw.
- `smear_items` reads a text item's top left: draw the text with `anchor="nw"` (centred text smeared below and beside itself, `SmearToggle`). `round_rect`'s corners are soft splines: a pill needs `r` about the full height, not half.

## Changing it

- Test each new widget in `tests/_selftest_widgets2.py`.
- Never delete and remake a canvas item from its own tag Enter / Leave (or anything that runs then): the new item under the pointer is entered again and Tk loops for good, a freeze (F-21: the card's magnifier). Move and recolour it instead (`itemconfigure`).
