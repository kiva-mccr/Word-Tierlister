# `src/errors.py`

Friendly error and message dialogs and the program-wide safety net (ST-2): every run goes through `run_guarded`, and Tk / thread errors are logged and shown once.

- **Uses:** `fonts`, `problems`, `theme`, `ui_style`, `widgets`
- **Used by:** `app`, `browser`, `filepicker`, `sources`, `startup`, `stress_ui`, `tierlist`
- **Tests:** `_selftest_errors`

The module docstring has the details; this page is the map.

## Public API

- `show_error`: Show a modal error dialog and wait for it to close (stderr if no window can be made).
- `show_message`: A plain styled message with an OK button (no error look, no details): a merge result, say.
- `ask_yes_no`: A small styled question dialog.
- `ask_choices`: A styled question with one tick box per choice (ST-4: each package is its own choice).
- `show_exception`: Dialog for an error the program caught itself (a failed export, say): what we were doing, why, what to try.
- `install_handlers`: Route every unexpected error to the log (and, for the window's own errors, a friendly dialog).
- `run_guarded`: Call fn() so that no failure is silent, whether or not there is a console to read.

## Rules and pitfalls (fixed before: keep them fixed)

- No tk messagebox anywhere: use `show_error` / `show_message` / `ask_yes_no`.
- Repeats of one error never pile up dialogs; a deliberate stop (`STOPPED_MESSAGE`) is silent.
