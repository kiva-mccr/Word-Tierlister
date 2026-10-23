# `src/bundle.py`

What a built program carries besides code (T-2): the English word lists of wordfreq and the few data files its packages read, and the modules never to bundle.

- **Uses:** the standard library only
- **Used by:** `standalone`
- **Tests:** `_selftest_build`, `_selftest_bundle`

The module docstring has the details; this page is the map.

## Public API

- `package_dir`: The folder of an installed package, or None if it is not installed.
- `datas`: [(absolute source path, destination folder inside the program)].
- `size_mb`: (no docstring)

## Rules and pitfalls (fixed before: keep them fixed)

- WordNet is never bundled (an optional download, as from source); the build machine's `~/nltk_data` must stay out (`tools/hooks/hook-nltk.py`).

## Changing it

- A new package with data files: add them to `datas()` and check `tests/_selftest_bundle.py` still runs from the bundled folder.
