# `src/problems.py`

What went wrong, in plain words (ST-2), with no tkinter so any layer can raise or describe a problem; plus the small log helpers that keep messages when there is no console.

- **Uses:** the standard library only
- **Used by:** `errors`, `sources`, `startup`, `tierlist`, `wordsource`
- **Tests:** `_selftest_deps`, `_selftest_errors`, `_selftest_sources`

The module docstring has the details; this page is the map.

## Public API

- `SetupError`: A problem the user can fix.
- `describe`: (headline, advice) in plain words for an exception.
- `open_log`: Append-mode text log (restarted when it passes 1 MB); falls back to the null device.
- `append_log`: Add `text` to the log file at `path`; never raises (a broken log must not hide the real error).
- `ensure_streams`: If started without a console (pythonw, a double-clicked launcher) the standard streams are None and print() would crash: send them to the log instead.

## Rules and pitfalls (fixed before: keep them fixed)

- Raise `SetupError` for anything the user can fix; never `sys.exit("...")` with a message.
- Plain-language texts live in `describe`; the dialog that shows them is `errors.py`.

## Changing it

- A new kind of failure: add its headline and advice to `describe`, and a case to `tests/_selftest_errors.py`.
