# `src/fonts.py`

The fonts: one family and named size roles shared as Tk `Font` objects (UI-2).

- **Uses:** the standard library only
- **Used by:** `app`, `browser`, `dealing`, `errors`, `filepicker`, `shortcuts`, `smooth`, `startup`, `tiercolours`, `tierlist`, `ui_style`, `widgets`
- **Tests:** `_selftest_dealing`, `_selftest_deps`, `_selftest_drawer`, `_selftest_errors`, `_selftest_filepicker`, `_selftest_fonts`, `_selftest_icon`, `_selftest_looks`, `_selftest_sizing`, `_selftest_smooth`, `_selftest_startup`, `_selftest_style`, `_selftest_ui`, `_selftest_widgets2`, `_selftest_zoom`

The module docstring has the details; this page is the map.

## Public API

- `typeface_files`: The bundled font files (.ttf), sorted.
- `load_typefaces`: Make the bundled typefaces usable by Tk in this program only (once per process).
- `text_overhang`: (left, right): how many pixels `text` in `font` reaches past the box Tk measures for it.
- `letter_holes`: The holes of `text`'s letters (an e's, an o's) as polygons [x0, y0, x1, y1, ..], pixels from the text's left end and its baseline (y up): the smear fills them so no...
- `pick_font_family`: Return the first preferred family present in `available` (case-insensitive), else fallback.
- `init_fonts`: Load the bundled typefaces, pick the families and build the shared Font objects (once per root).
- `spec`: (size, weight, face) a role is built with: a display role's stand-in (Young Serif missing) is bold, as the words were before.
- `scale_fonts`: Resize every role font to `factor` x its base size (1.0 = normal).
- `family`: Name of the text font family chosen by init_fonts().
- `display_family`: Name of the display font family (the words) chosen by init_fonts().
- `font`: The shared Font object for a role.

## Rules and pitfalls (fixed before: keep them fixed)

- `letter_holes` reads overhang.json's "holes|..." tables (upright faces only); a font not bundled, or text under 14 px, has none (F-40). Keep them out of the overhang letters (`_overhangs`).
- `text_overhang` reads src/typefaces/overhang.json (written by tools/make_typefaces.py): only a word's first and last letters count (inside a word the overhang lies over its neighbour); no Tk call unless such a letter is there (F-32).
- Use `font(role)`; after resizing them (zoom, grow) call `widgets.refresh_widgets(window)`.
- Measure text with the fonts instead of assuming a dpi.
- The typefaces load for this program only (`load_typefaces`: fontconfig, a private GDI font, CoreText), once, before the families are picked; a failure is never an error: the installed stand-ins (`PREFERRED`) are used, and a display role is then bold, as the words were.
- Young Serif has one weight: never ask a display role for bold while it is loaded.
- Digits are all one width (the files' tabular figures, tools/make_typefaces.py); Atkinson Hyperlegible's zero is slashed (its design, for telling 0 from O).
- The text keeps to three sizes (20 / 12 / 10, `_selftest_fonts` checks); only the card's word and a duel's two words are bigger. 13 pt text made the window a tenth wider (the layout is measured in lines).
- A build packs `src/typefaces` as `typefaces` (standalone.pyinstaller_args), where `TYPEFACES` looks.

## Changing it

- A new role: `ROLES` with its base size, weight and face ("display" or "text").
- New font files: `tools/make_typefaces.py` (keep their line spacing tight).
