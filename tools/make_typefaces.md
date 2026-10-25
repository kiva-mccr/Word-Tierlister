# `tools/make_typefaces.py`

Fetches the program's two typefaces (UI-73) from Google Fonts into `src/typefaces/`, with their SIL Open Font Licences, and tightens their line spacing: Young Serif (the words) and Atkinson Hyperlegible (everything else; the user chose the pair from mock-ups). Needs the internet and fontTools; the program itself only reads the files.

- **Uses:** the standard library only
- **Used by:** nothing (run directly)
- **Tests:** `_selftest_fonts`

The module docstring has the details; this page is the map.

## Public API

- `fetch`: (no docstring)
- `tighten`: Set the font's line metrics (every table a system may read them from) to ascent / descent, with no line gap.
- `tabular_digits`: Point 0-9 at the font's tabular figures (zero.tf ..), when it has them: Tk cannot ask for the tnum feature, and counts that change (the stats line) would otherwise...
- `write_overhangs`: overhang.json: for each face ("family|weight|slant"), the letters whose ink reaches past their own box, as {letter: [left, right]} in 1/1000 em (Young Serif's j...
- `main`: (no docstring)

## Rules and pitfalls (fixed before: keep them fixed)

- `write_overhangs` writes overhang.json, the letters whose ink reaches past their box (F-32); run it again whenever the font files change.
- As shipped, both fonts' lines are tall (Atkinson 1.24 em, Young Serif 1.41 em): much of the layout is measured in lines (the shelf is 30 lines wide, the pane 9 lines tall), so the window grew by a quarter and a 1366 x 768 laptop could not show 100%. `LINE` sets hhea, OS/2 typo and win ascent / descent alike (Windows reads win, Linux and macOS the others).
- Keep Atkinson's ascent above its accented capitals (885) and its descent below `g` (-207); Young Serif's ascent above its ascenders (800). Young Serif's accented capitals reach 1060: drawn, never cut.
- Atkinson's digits point at its tabular figures (`tabular_digits`): Tk cannot ask for the tnum feature, and the stats line's counts shifted the text after them (layout_trace caught it).
- The licence allows changed copies under the same licence (neither font has a Reserved Font Name): keep the OFL files beside them.
- Run it again only to change the fonts, and commit the files it writes (`_selftest_fonts` checks they load and the lines stay short).
