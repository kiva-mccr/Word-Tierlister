# `tools/notes.py`

Keeps every code file's notes (the `.md` beside each `.py` in the top folder, `src/` and `tools/`) up to date: it rewrites their generated parts (uses, used by, tests, public API) from the code and keeps the hand-written ones. `check_release` runs it with `--check`.

- **Uses:** the standard library only
- **Used by:** `check_release`
- **Tests:** none of its own

The module docstring has the details; this page is the map.

## Public API

- `code_files`: (no docstring)
- `render`: The note for `path`: its hand-written parts kept from `old`, the rest generated.
- `notes`: Bring every note up to date (or, with `check`, only list the ones missing, out of date or without their purpose written).

## Rules and pitfalls (fixed before: keep them fixed)

- Hand-written: the paragraph under the title, and everything from "## Rules and pitfalls" on. Everything else is regenerated, so edit those parts in the code (docstrings, imports), not in the note.
- A new code file gets a note with a placeholder purpose; `--check` fails until it is written.

## Changing it

- What the generated part shows: `render`. Which folders have notes: `NOTED` (keep `check_release` in step).
