# `src/devtools.py`

The developer tools' bubbles (Settings > Developer tools, DT-1, DT-2): `DevTools` (one per main window, `App.devtools`) has Log and Crash test for Source & Updates. The review of rude meanings and the tuner (DT-3..DT-7) went with the rudeness rules (OB-14; branch `archive/censoring`).

- **Uses:** `constants`, `standalone`
- **Used by:** `app`
- **Tests:** none of its own

The module docstring has the details; this page is the map.

## Public API

- `DevTools`: The developer tools of one main window (App.devtools).
  - methods: open_log, crash_test

## Rules and pitfalls (fixed before: keep them fixed)

- A developer bubble that opens a window of its own (the crash test) closes its dialog first: a StyledDialog holds the input (grab).
- They run from the source only, never from a built program.
