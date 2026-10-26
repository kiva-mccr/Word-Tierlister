# `tierlist.py`

The program's entry point and its roadmap. `main()` parses the options, finds or makes the save, gets packages and the word list ready behind the progress window, then opens the main window. The big comment block at the top is the roadmap: every step, its status and the decisions behind it. It also re-exports the main classes so tests can `import tierlist as T`.

- **Uses:** `app`, `browser`, `constants`, `definitions`, `deps`, `errors`, `fonts`, `problems`, `saves`, `sizing`, `standalone`, `startup`, `store`, `theme`, `ui_style`, `wordsource`
- **Used by:** `layout_trace`, `stress_ui`
- **Tests:** `_selftest`, `_selftest_appdir`, `_selftest_build`, `_selftest_dealing`, `_selftest_defsize`, `_selftest_deps`, `_selftest_drawer`, `_selftest_filepicker`, `_selftest_fonts`, `_selftest_freeze`, `_selftest_install`, `_selftest_looks`, `_selftest_lookup`, `_selftest_motion`, `_selftest_queue`, `_selftest_release`, `_selftest_resume`, `_selftest_selfupdate`, `_selftest_shortcuts`, `_selftest_sizing`, `_selftest_smoke`, `_selftest_sources`, `_selftest_startup`, `_selftest_tidy`, `_selftest_ui`, `_selftest_ui2`, `_selftest_updates`, `_selftest_wikt`, `_selftest_zoom`

The module docstring has the details; this page is the map.

## Public API

- `main`: Start the program: parse options, pick and open the save, build the word list on first run, open the window.

## Rules and pitfalls (fixed before: keep them fixed)

- Never move it into a sub-folder: your save, `tierlist.log` and exports sit next to it (R-1).
- It adds `src/` to the import path itself; nothing else should edit `sys.path` at run time.
- The window is built hidden and shown complete (`App.open_window`, F-1); never `deiconify()` before `App(...)`.
- Roadmap IDs are stable: tick `[x]` and add notes under a step, never renumber.
- The re-exports at the top are why pyflakes reports "imported but unused" here; that is known noise.

## Changing it

- New command-line option: `main()`'s argparse block, plus the README's Options table.
- First-run steps: the `set_up` function inside `main()` (keep `wordsource.wiktionary_steps` / `queue_steps` in step).
