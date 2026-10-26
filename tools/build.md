# `tools/build.py`

Building the program from the command line (T-3, T-8): for this computer, or with `--all` for Linux, Windows and macOS on GitHub (the Build programs workflow, through `gh`).

- **Uses:** `standalone`
- **Used by:** nothing (run directly)
- **Tests:** `_selftest_build`, `_selftest_updates`

The module docstring has the details; this page is the map.

## Public API

- `build`: Build the program into `dist` (default dist/ in the project), carrying its source inside (T-7); returns its path, or None if the build failed.
- `check`: Start the built program from a folder of its own, with a short word list and no internet, and see that it opens and stays open, and keeps its save beside itself (T-1).
- `remote_ready`: (branch, commit) to build on GitHub, or (None, why not): gh installed and logged in, the commit pushed.
- `build_all`: Run the "Build programs" workflow on GitHub for the pushed branch, wait for it, and fetch its programs into `dist`: their paths, or (None, why not).
- `main`: (no docstring)

## Rules and pitfalls (fixed before: keep them fixed)

- `--all` needs `gh` logged in and the commit pushed, else it says which and builds for this computer only.
- The real work is `src/standalone.py`; keep this a thin wrapper.
