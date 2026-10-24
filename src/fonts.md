# `src/fonts.py`

The fonts: one family and named size roles shared as Tk `Font` objects (UI-2).

- **Uses:** the standard library only
- **Used by:** `app`, `browser`, `dealing`, `errors`, `filepicker`, `shortcuts`, `startup`, `tiercolours`, `tierlist`, `ui_style`, `widgets`
- **Tests:** `_selftest_dealing`, `_selftest_deps`, `_selftest_errors`, `_selftest_filepicker`, `_selftest_fonts`, `_selftest_icon`, `_selftest_looks`, `_selftest_sizing`, `_selftest_startup`, `_selftest_style`, `_selftest_ui`, `_selftest_widgets2`, `_selftest_zoom`

The module docstring has the details; this page is the map.

## Public API

- `pick_font_family`: Return the first preferred family present in `available` (case-insensitive), else fallback.
- `init_fonts`: Pick the family for this machine and build the shared Font objects (once per root).
- `scale_fonts`: Resize every role font to `factor` x its base size (1.0 = normal).
- `family`: Name of the font family chosen by init_fonts().
- `font`: The shared Font object for a role.

## Rules and pitfalls (fixed before: keep them fixed)

- Use `font(role)`; after resizing them (zoom, grow) call `widgets.refresh_widgets(window)`.
- Measure text with the fonts instead of assuming a dpi.

## Changing it

- A new role: `ROLES` with its base size.
