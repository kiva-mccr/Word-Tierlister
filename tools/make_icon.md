# `tools/make_icon.py`

Draws the program's icon (IC-1) into `src/icons/`: the progress shelf's six spines in the tier colours on the cream tile with rounded corners, the lilac mark over C (the user chose this design). Every size from 16 to 256 px, a 1024 px one for the Linux launcher, and `icon.ico` for the Windows program. Needs Pillow; the program itself only reads the files.

- **Uses:** `theme`
- **Used by:** nothing (run directly)
- **Tests:** `_selftest_icon`

The module docstring has the details; this page is the map.

## Public API

- `rgb`: (no docstring)
- `draw`: The icon, `size` pixels square (RGBA: see-through outside the tile's rounded corners).
- `main`: (no docstring)

## Rules and pitfalls (fixed before: keep them fixed)

- Draw each size from the shapes (four times over, then scaled down), never shrink one big picture: at 16 px the spines' edges fell between pixels and the icon was a blur.
- 32 px and under: edges snapped to whole pixels, no outlines; 16 px has two-pixel spines side by side (no gap) and a three-pixel mark.
- The colours are the light look's defaults, whatever a save picked: the icon is the program's.
- Run it again only to change the icon, and commit the files it writes (`_selftest_icon` checks every size is there).
