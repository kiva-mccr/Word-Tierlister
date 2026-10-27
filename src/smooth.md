# `src/smooth.py`

Anti-aliased rounded shapes for our canvases: soft-edged images over an invisible polygon (`SmoothCanvas.round_rect`), curves (`curve_image`) and small icons (`ICONS`).

- **Uses:** `fonts`
- **Used by:** `browser`, `tiercolours`, `ui_chart`, `widgets`
- **Tests:** `_selftest_filepicker`, `_selftest_smooth`, `_selftest_widgets`

The module docstring has the details; this page is the map.

## Public API

- `control_points`: The corner points of a rounded rectangle the way the app has always drawn it (Tk's smoothed polygon): each corner's two tangent points doubled, so the curve passes...
- `smooth_outline`: Tk's smoothing of a closed polygon: around each point, a quadratic Bezier from the middle of the side before it to the middle of the side after it, with the point as...
- `coverage_mask`: For a polygon given relative to a w x h image: per row, runs of [count, fill coverage, outline coverage] (0..255).
- `paint_with_shadow`: Like paint_mask, with a copy of the shape's fill in `shadow` colour, dx, dy pixels down-right, under it, all blended into `backdrop`: every pixel solid or clear.
- `paint_mask`: RGBA rows from a coverage_mask, in these colours (either may be None).
- `SmoothCanvas`: A Canvas whose round_rect() shapes are drawn smooth, and whose text is repainted where its letters reach past their boxes (F-32: fonts.text_overhang).
  - methods: create_text, ink_box, round_rect, round_rect_coords, itemconfigure, itemcget, coords, move, delete, tag_raise, tag_lower, triangle_image, icon_image, smooth_image
- `arrow_image`: A small soft-edged triangle pointing up or down (w x h, see-through around it), filled with `fill` for `reveal` (0..1) of its height and `track` (a paler colour, like...
- `gradient_image`: A pill-shaped bar w x h whose fill runs through `columns` (one (r, g, b) per pixel column, left to right) with a hairline `outline`, blended onto the canvas colour (a...
- `curve_rows`: RGBA rows for the area under a curve and its line: ys[i] is the curve's height (pixels from the top, fractional) at the left edge of column i (w + 1 values).
- `curve_image`: A PhotoImage of the area under the curve `ys` (see curve_rows) and its line, cached.

## Rules and pitfalls (fixed before: keep them fixed)

- Text whose letters reach past the box Tk measures (fonts.text_overhang: Young Serif's j and f) gets an invisible guard rectangle over its whole reach, set again after every move, coords, text, font or state change and deleted with its text (F-32). Tk repaints only a text's box, so the rest stayed on screen; a shape made and dropped at once does not make Tk repaint (only one it has drawn), which is why the guard stays. Never give a guard the text's tags.
- Never `create_polygon(..., smooth=True)` for rounded shapes, and never text symbols for icons.
- Resize with `round_rect_coords`; a shape on the plain canvas colour is pre-blended, over other shapes its edge stays see-through.
