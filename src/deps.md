# `src/deps.py`

The third-party packages and installing them (ST-1..ST-5): the terminal step for tkinter before any window, pip installs measured for the install dialog, the private environment fallback, detaching from the terminal, and the Linux applications-menu launcher.

- **Uses:** `constants`
- **Used by:** `app`, `sources`, `standalone`, `startup`, `tierlist`
- **Tests:** `_selftest_deps`, `_selftest_icon`, `_selftest_install`, `_selftest_sources`, `_selftest_ui2`, `_selftest_updates`

The module docstring has the details; this page is the map.

## Public API

- `use_system_certificates`: A built program (Linux, macOS) carries the OpenSSL of the machine it was built on, which looks for trusted certificates where that machine keeps them (GitHub's...
- `missing`: The import names in `names` that cannot be imported right now.
- `pip_available`: True if `python -m pip` works for this interpreter.
- `install`: pip-install the packages for the import names `names`, streaming pip's output through `log`.
- `tk_available`: True if tkinter (and the _tkinter extension under it) can be imported.
- `system_install_command`: The system command that installs `what` ("tkinter", "pip", "venv" or "python") for this computer, as a list, or None if there is nothing we know to run.
- `tk_install_command`: The system command that installs tkinter for this Python in a terminal (see system_install_command).
- `run_system_install`: Run a system install command (system_install_command), its output through `log`; True if it worked.
- `ensure_pip`: Python's own way to put pip back (ensurepip: no password, nothing from the system); True if pip works then.
- `tk_advice`: What to do yourself when tkinter is missing and cannot be installed from here.
- `venv_python`: The python inside a virtual environment folder (it may not exist yet).
- `restart`: Start the program again with `python` (after tkinter or a private environment was set up).
- `use_private_env`: If something is missing here but the program's private environment (<home>/.venv, made by the window's install step) exists, restart in it straight away: that is...
- `terminal_setup`: Stage 1 of the install (ST-4): in the terminal, before any window, get only what the window itself needs, which is tkinter.
- `make_private_env`: Make <home>/.venv and pip-install `names` into it, streaming output through `log`.
- `wants_terminal_setup`: True when stage 1 should run: an interactive terminal, installs allowed, not a packaged build.
- `windowless_python`: Windows: pythonw.exe, the Python with no console window, beside this python.exe (every python.org install and every venv has it), or None.
- `should_detach`: True when the program, started from a terminal (or a console window a double-click opened), should carry on without it and let it go (so closing it no longer closes...
- `detach_terminal`: Start the program again on its own, not tied to this terminal, and return the exit code for this one: Linux / macOS in a session of its own (setsid), Windows with...
- `kept_icon`: The program's icon copied where it stays (~/.local/share/icons/word-tierlist.png: a built program's own copy is in a folder that is gone once it closes), for a...
- `desktop_entry`: The text of a Linux .desktop launcher that starts the program with no terminal (`script` None: a built program, started by itself); `icon`: a picture's path, or the...
- `launcher_path`: (no docstring)
- `ensure_launcher`: Linux, at every start (reported: no icon in Fedora's taskbar; GNOME shows a window's icon only through a launcher that names its class): write the launcher if there...
- `add_to_menu`: Write (or update) the launcher in ~/.local/share/applications, with the program's icon copied to ~/.local/share/icons (a built program's own copy is gone once it closes).
- `menu_name`: What the desktop's list of programs is called here: "applications menu" (Linux), "Start menu" (Windows), or None where Word Tier List cannot add itself (macOS: an app...
- `in_menu`: True if Word Tier List is in the applications menu / Start menu already (Linux: the launcher that every start keeps for the taskbar counts only once it is shown, not...
- `start_menu_path`: Where the Start menu shortcut goes: the user's own Programs folder (no administrator needed).
- `shortcut_parts`: (target, arguments, working folder, icon) for the shortcut: from source pythonw.exe (no console window, ST-9) running tierlist.py with the program's icon; a built...
- `add_to_start_menu`: Write (or update) the Start menu shortcut.

## Rules and pitfalls (fixed before: keep them fixed)

- A built program on Linux / macOS must trust this computer's certificates (`use_system_certificates`, called first in main; U-3, reported): its OpenSSL looks where the build machine kept them, and without them every https request fails quietly.

- Keep `PACKAGES` in step with `requirements.txt` (a test checks); a new package also needs `SIZE`, `PURPOSE`, `HOMEPAGE`.
- The Windows Start menu shortcut (ST-10) is written by PowerShell's WScript.Shell with every value passed through the environment (`SHORTCUT_PS` reads `$env:WTL_*`): never put a path inside the script's text (quotes and spaces in folder names). From source its target is pythonw.exe, never python.exe (a console window, ST-9).
- Re-measure `SIZE` / `DOWNLOAD` with pip if requirements change.
- Restarts never loop: `REEXEC_ENV` / `DETACHED_ENV` mark the copy that was started.

## Changing it

- Where tkinter install commands come from: `tk_install_command`. The window side of installing: `startup.ensure_packages`.
- The launcher's icon is copied to `~/.local/share/icons/word-tierlist.png` (`add_to_menu`): a built program's own copy is in a folder that is gone once it closes.
- System pieces (ST-8): `SYSTEM_PACKAGES` per package manager; from a window the command goes through `pkexec` (sudo cannot ask for a password without a terminal; no pkexec: no command, the old advice). `ensure_pip` tries Python's own ensurepip first. Tests never run the real ensurepip or an installer (fake them).
- Windows (ST-9): the console stays open while the py launcher that opened it waits, so letting go of it (FreeConsole) is not enough: the program starts again with `pythonw.exe` (`windowless_python`) and this copy ends. Never rename tierlist.py to .pyw (every sync, manifest and launcher expects tierlist.py).
- Linux taskbar icons (IC-3): `StartupWMClass` must equal the window's real class, `constants.WM_CLASS_NAME` (Tk lowers the className and capitalizes it: "WordTierList" became "Wordtierlist"); `ensure_launcher` keeps whether the launcher is in the menu.
