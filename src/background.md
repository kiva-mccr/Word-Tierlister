# `src/background.py`

Work on a worker thread handed back to the Tk thread (`Task`), and timers that repeat on it (`Repeat`); both stop when their widget is destroyed. Every place that waits on a worker uses it: the update check (app), the reshuffle (dealing), Source & Updates' check and the sync rounds.

- **Uses:** the standard library only
- **Used by:** `app`, `dealing`, `sources`, `syncdialog`
- **Tests:** `_selftest_background`

The module docstring has the details; this page is the map.

## Public API

- `Repeat`: fn() on the Tk thread every `ms` (the first after `first` ms, by default `ms`) until it returns False, stop() is called or `widget` is destroyed.
  - methods: stop
- `Task`: work() on a worker thread, its answer handed to the Tk thread (see the module's note).
  - methods: running, cancel

## Rules and pitfalls (fixed before: keep them fixed)

- A worker never touches Tk: `work()` only returns its answer; `done` / `failed` run on the Tk thread.
- A worker's exception is never lost: `failed(exc)`, or Tk's error handler (the friendly dialog). Before this, an exception in a worker left its poll running for good (Source & Updates said "Checking..." for ever if the check raised).
- A timer is cancelled when its widget is destroyed (`<Destroy>`): one left on a closed window fired a deleted command ("invalid command name ...") once Tk ran again.
- A long job that writes the save holds answers that would write it too: pass `wait=lambda: app.busy`.
- `thread=False` runs the work inline (tests that pass a stand-in runner expect the answer at once).
