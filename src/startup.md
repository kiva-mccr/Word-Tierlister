# `src/startup.py`

Long jobs behind a progress window (ST-1): `run_with_progress` runs `work(log)` on a worker thread and turns its log lines into a stage, a detail line, a bar with an ETA and "Step i of n"; also the install dialog (ST-4) and Windows' console detach.

- **Uses:** `constants`, `deps`, `errors`, `fonts`, `problems`, `sizing`, `theme`
- **Used by:** `sources`, `tierlist`
- **Tests:** `_selftest_sizing`, `_selftest_startup`

The module docstring has the details; this page is the map.

## Public API

- `parse_progress`: Percent (0..100) found in a log line like ' downloaded 1.20 GB (41%)', else None.
- `format_eta`: Friendly time-left text: 'a few seconds left', 'about 40 sec left', 'about 6 min left', 'about 1 hr 5 min left'.
- `EtaTracker`: Estimates the time left for one progress bar from its recent speed.
  - methods: reset, add, remaining
- `step_of`: (i, n) for the plan step `stage` starts (a plan line's names are the starts of stage lines), else `current` unchanged (a stage line that is not a main step, like a...
- `format_elapsed`: '0:07' or '12:03' style elapsed time.
- `StartupWindow`: The progress window itself: a stage line, a detail line, a bar (when a percentage is known).
  - methods: show, close
- `run_with_progress`: Run `work(log)` on a worker thread and return its result (see the module docstring).
- `detach_console`: Windows: drop the console window this process was started from, sending print() output to a log.
- `ensure_packages`: Make sure the packages in `required` (and, if wanted, `optional`) can be imported (ST-4, stage 2).

## Rules and pitfalls (fixed before: keep them fixed)

- Worker threads never touch tkinter; errors in the work are re-raised in the caller, closing the window raises `SystemExit(STOPPED_MESSAGE)`.
- A bar with a real percentage always shows an ETA (`EtaTracker` / `format_eta`).
