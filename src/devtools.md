# `src/devtools.py`

The developer tools' bubbles (Settings > Developer tools, DT-1..DT-7): `DevTools` (one per main window, `App.devtools`) starts the review of rude meanings, makes review words and runs the tuner from tools/ in the source folder, shows how a running tool is doing on its bubble's ring and stops it. Log and Crash test for Source & Updates are here too.

- **Uses:** `background`, `constants`, `errors`, `filepicker`, `review`, `saves`, `standalone`
- **Used by:** `app`
- **Tests:** `_selftest_devtools`

The module docstring has the details; this page is the map.

## Public API

- `stop_tree`: Stop a tool a developer bubble started, and the processes it started (the tuner's workers); never waits (whoever watches it sees it end).
- `Job`: A tool running in the background, shared by the window and the worker thread that reads it.
  - methods: running
- `run_tools`: Run each command in turn (a worker thread: no Tk here): (the exit code, the last line it printed), stopping at the first that fails.
- `follow_tuner`: Read the tuner's printed rounds into `job` (a worker thread: no Tk here): over once it says it is done (its window may stay open for Keep; what it prints later is...
- `DevTools`: The developer tools of one main window (App.devtools).
  - methods: review_file, pick_review_file, review_rude, progress, stop_note, stop, show_tuner, review_words, next_auto_tune, review_answered, tune_reroll, make_review_words, tune_rules, open_log, crash_test

## Rules and pitfalls (fixed before: keep them fixed)

- A worker thread never touches Tk: it writes into a `Job` (each field written by one side only, see its docstring) and the window polls it (`_watch_tool`, `_watch_tuner`).
- DT-7: a stopped tool must never leave a half-written file that looks finished (rudeness_entries.jsonl, a first review file): `_watch_tool` removes the stopped step's `partial`. Tools start in their own process group (`OWN_GROUP`) so `stop_tree` reaches the tuner's workers; it never waits on the Tk thread.
- DT-5: Tune & reroll rerolls only once the tuner printed "Done" (`Job.tuned`) and its process has ended (Keep or Discard closed it): a tuner closed while tuning (Discard) or failing makes no new words. `_watch_tuner` (Tk side) clears `tuner`; `progress` only reads it and treats an ended process as not running.
- `follow_tuner` keeps reading the tuner's stdout after it says Done (its window stays open for Keep): a pipe nobody reads fills and freezes the tuner. The tuner's prints go through `say`, which never raises once the program has closed.
- A developer bubble that opens a window of its own (the review, the crash test) closes its dialog first: a StyledDialog holds the input (grab), so the review opened under it could not be clicked.
- The tools run only from the source (`_tool`): a built program carries no tools/ and says so.
