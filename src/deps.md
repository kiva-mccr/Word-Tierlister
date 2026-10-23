# `src/deps.py`

The third-party packages and installing them (ST-1..ST-5): the terminal step for tkinter before any window, pip installs measured for the install dialog, the private environment fallback, detaching from the terminal, and the Linux applications-menu launcher.

- **Uses:** `constants`
- **Used by:** `app`, `startup`, `tierlist`
- **Tests:** `_selftest_deps`, `_selftest_install`

The module docstring has the details; this page is the map.

## Public API

- `missing`: The import names in `names` that cannot be imported right now.
- `pip_available`: True if `python -m pip` works for this interpreter.
- `install`: pip-install the packages for the import names `names`, streaming pip's output through `log`.
- `tk_available`: True if tkinter (and the _tkinter extension under it) can be imported.
- `tk_install_command`: The system command that installs tkinter for this Python, as a list, or None if we do not know one.
- `tk_advice`: What to do yourself when tkinter is missing and cannot be installed from here.
- `venv_python`: The python inside a virtual environment folder (it may not exist yet).
- `restart`: Start the program again with `python` (after tkinter or a private environment was set up).
- `use_private_env`: If something is missing here but the program's private environment (<home>/.venv, made by the window's install step) exists, restart in it straight away: that is...
- `terminal_setup`: Stage 1 of the install (ST-4): in the terminal, before any window, get only what the window itself needs, which is tkinter.
- `make_private_env`: Make <home>/.venv and pip-install `names` into it, streaming output through `log`.
- `wants_terminal_setup`: True when stage 1 should run: an interactive terminal, installs allowed, not a packaged build.
- `should_detach`: True when the program, started from a terminal on Linux or macOS, should carry on in its own session and give the terminal its prompt back (so closing the terminal no...
- `detach_terminal`: Start the program again in a session of its own (setsid), not tied to this terminal, and return the exit code for this one.
- `desktop_entry`: The text of a Linux .desktop launcher that starts the program with no terminal (`script` None: a built program, started by itself).
- `add_to_menu`: Write (or update) the launcher in ~/.local/share/applications.

## Rules and pitfalls (fixed before: keep them fixed)

- Keep `PACKAGES` in step with `requirements.txt` (a test checks); a new package also needs `SIZE`, `PURPOSE`, `HOMEPAGE`.
- Re-measure `SIZE` / `DOWNLOAD` with pip if requirements change.
- Restarts never loop: `REEXEC_ENV` / `DETACHED_ENV` mark the copy that was started.

## Changing it

- Where tkinter install commands come from: `tk_install_command`. The window side of installing: `startup.ensure_packages`.
