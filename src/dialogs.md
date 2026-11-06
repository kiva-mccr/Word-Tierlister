# `src/dialogs.py`

The shared dialog frame, `StyledDialog`, that every dialog is built on, and `dialog_open`.

- **Uses:** `buttons`, `fonts`, `sizing`, `theme`, `ui_style`
- **Used by:** `app`, `dealing`, `errors`, `filepicker`, `shortcuts`, `sources`, `syncdialog`, `tiercolours`, `widgets`
- **Tests:** `_selftest_fullscreen`, `_selftest_sizing`, `_selftest_veil`, `_selftest_widgets2`, `_selftest_zoom`

The module docstring has the details; this page is the map.

## Public API

- `dialog_open`: True while one of our dialogs (StyledDialog: a question, a message, a settings page) is on screen.
- `StyledDialog`: The shared dialog frame (UI-24): a bold headline, a muted line of explanation, a body to fill and a row of rounded buttons, the default one (what Enter presses) in...
  - methods: dev_bubbles, text, button, make_default, clear_buttons, show, refit, rescale, close, alive, when_closed

## Rules and pitfalls (fixed before: keep them fixed)

- `StyledDialog.decorate` (FS-2) is called once with each dialog just before it shows: full screen's Back bar. Only App sets it.
- `StyledDialog.rescale` re-centres the dialog, then follows its parent's moves for a second (`FOLLOW_MS`): a maximize re-fits inside its first `<Configure>` (F-50), and macOS moves the window after that, so the dialog stayed centred on where the window had been (GitHub's Macs).
- `StyledDialog.show` veils the dialog while it draws (`ui_style.veil` / `unveil`, F-48): shown plainly it appeared as a heading alone, then labels, then the rest, over ~0.2 s.
- Developer bubbles (`StyledDialog.dev_bubbles`) are packed in the headline's own row, never placed over the dialog: a placed frame takes no room, so a narrow dialog ran its headline under them.
- No `ttk.Combobox` / `tk.Menu` pop-ups (they grab input on Linux): use `ChoiceButton` / `DropMenu`. Dialogs build on `StyledDialog` (`StyledDialog.text` for wrapped lines).
- Our dialogs mark their window (`styled_dialog`), so `dialog_open(root)` can tell when a question is on screen (nothing else may ask then).
- `StyledDialog.refit` keeps the dialog on its monitor (`sizing.keep_on_screen`).

## Changing it

- Test each new widget in `tests/_selftest_widgets2.py`.
- An open dialog follows a change of the shared fonts (a zoom): `refresh_widgets` calls `StyledDialog.rescale`, which re-wraps every wrapped label in proportion, then sizes and centres the dialog again. Without it the text grew inside a window that kept its size and was cut off (F-18).
