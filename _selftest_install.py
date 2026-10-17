"""Stage 1 of installing (ST-4, deps.terminal_setup): asked in the terminal before any window, only for what
the program cannot start without; optional packages are left for the window. No tkinter needed."""
import os, shutil, sys, tempfile
import deps

home = tempfile.mkdtemp()
real_missing = deps.missing
state = {}

def setup(answers=(), missing=(), tk=True, tk_cmd=("sudo", "apt-get", "install", "-y", "python3-tk"),
          install_ok=True, tail="Successfully installed", run_code=0, tk_after=True):
    """Run terminal_setup with everything external stubbed; returns (result or SystemExit, log)."""
    state.update(missing=list(missing), tk=tk, answers=list(answers), out=[], asked=[], runs=[],
                 installs=[], restarts=[], venvs=[])
    deps.missing = lambda names: [n for n in names if n in state["missing"]]
    def ask(q):
        state["asked"].append(q)
        if not state["answers"]:
            raise EOFError
        return state["answers"].pop(0)
    def run(cmd):
        state["runs"].append(list(cmd))
        if cmd and cmd[0] != deps.venv_python(os.path.join(home, ".venv")) and run_code == 0 and tk_after:
            state["tk"] = True
        return run_code
    def installer(names, log):
        state["installs"].append(list(names)); log("  Collecting " + names[0])
        if install_ok:
            state["missing"] = []
        return install_ok, tail
    def make_venv(venv, out):
        state["venvs"].append(venv)
        os.makedirs(os.path.dirname(deps.venv_python(venv)), exist_ok=True)
        open(deps.venv_python(venv), "w").close()
        return 0
    try:
        result = deps.terminal_setup(["tierlist.py", "--db", "x.db"], home, ask=ask, out=state["out"].append,
                                     run=run, installer=installer, has_tk=lambda: state["tk"],
                                     tk_command=list(tk_cmd) if tk_cmd else [], make_venv=make_venv,
                                     restarter=lambda py, argv: state["restarts"].append((py, argv)))
    except SystemExit as exc:
        result = exc
    return result, "\n".join(state["out"])

os.environ.pop(deps.REEXEC_ENV, None)

# nothing missing: silent, no question
r, log = setup()
assert r is True and log == "" and not state["asked"]

# wordfreq missing, Enter (= yes): installs only the required package, says the window opens next
r, log = setup(answers=[""], missing=["wordfreq"])
assert r is True and state["installs"] == [["wordfreq"]] and not state["restarts"], state
assert "wordfreq: word frequency data" in log and "pip install wordfreq>=3.0" in log
assert "Optional extras are offered later, in the window." in log and "nltk:" not in log   # nltk is NOT asked here
assert "Collecting wordfreq" in log and log.endswith("Done. Opening the window...")
assert state["asked"] == ["Install them now? [Y/n] "]

# a stray answer is asked again; "no" carries on without (the window explains later)
r, log = setup(answers=["maybe", "n"], missing=["wordfreq"])
assert r is False and state["installs"] == [] and "Please answer y or n." in log and len(state["asked"]) == 2
# no terminal input at all (EOF) counts as no
r, log = setup(answers=[], missing=["wordfreq"])
assert r is False and state["installs"] == []

# a failed install that is not the externally-managed case: SystemExit with the command to run
r, log = setup(answers=["y"], missing=["wordfreq"], install_ok=False, tail="ERROR: no network")
assert isinstance(r, SystemExit) and "no network" in str(r) and "-m pip install wordfreq>=3.0" in str(r)

# tkinter missing: installed through the package manager, then the program restarts so it can import it
r, log = setup(answers=["yes"], tk=False)
assert r is True and state["runs"] == [["sudo", "apt-get", "install", "-y", "python3-tk"]], state
assert state["restarts"] == [(sys.executable, ["tierlist.py", "--db", "x.db"])]
assert "tkinter: the window toolkit" in log and "(installed with: sudo apt-get install -y python3-tk)" in log
# both missing: tkinter first, then pip, then one restart
r, log = setup(answers=["y"], tk=False, missing=["wordfreq"])
assert state["runs"][0][-1] == "python3-tk" and state["installs"] == [["wordfreq"]] and len(state["restarts"]) == 1
# tkinter missing and the user says no: cannot continue
r, log = setup(answers=["n"], tk=False)
assert isinstance(r, SystemExit) and "cannot open without tkinter" in str(r) and not state["runs"]
# tkinter missing and no known way to install it: explains instead of asking
r, log = setup(tk=False, tk_cmd=None)
assert isinstance(r, SystemExit) and "cannot be installed from here" in str(r) and not state["asked"]
# the package manager ran but this Python still has no tkinter (e.g. a pyenv Python)
r, log = setup(answers=["y"], tk=False, tk_after=False)
assert isinstance(r, SystemExit) and "could not be installed for this Python" in str(r)

# externally-managed Python: offers a private .venv, installs there, restarts with it
r, log = setup(answers=["y", "y"], missing=["wordfreq"], install_ok=False,
               tail="error: externally-managed-environment")
vpy = deps.venv_python(os.path.join(home, ".venv"))
assert state["venvs"] == [os.path.join(home, ".venv")] and state["runs"][-1][:4] == [vpy, "-m", "pip", "install"]
assert state["restarts"] == [(vpy, ["tierlist.py", "--db", "x.db"])] and "does not allow installing" in log
# a later start with the system Python finds .venv and restarts into it without asking
r, log = setup(missing=["wordfreq"])
assert state["restarts"] == [(vpy, ["tierlist.py", "--db", "x.db"])] and not state["asked"]
# ...but never loops: once restarted, it asks as usual
os.environ[deps.REEXEC_ENV] = "1"
r, log = setup(answers=["n"], missing=["wordfreq"])
assert not state["restarts"] and state["asked"]
os.environ.pop(deps.REEXEC_ENV)
shutil.rmtree(os.path.join(home, ".venv"))
# declining the private environment: SystemExit with the manual steps
r, log = setup(answers=["y", "n"], missing=["wordfreq"], install_ok=False,
               tail="error: externally-managed-environment")
assert isinstance(r, SystemExit) and "-m venv" in str(r) and not state["venvs"]

deps.missing = real_missing

# ---- the system command for tkinter, per platform
which = lambda tools: (lambda t: "/usr/bin/" + t if t in tools else None)
cmd = deps.tk_install_command("linux", which({"apt-get"}))
assert cmd[-3:] == ["install", "-y", "python3-tk"] and (cmd[0] == "sudo") == (os.geteuid() != 0)
assert deps.tk_install_command("linux", which({"dnf"}))[-1] == "python3-tkinter"
assert deps.tk_install_command("linux", which(set())) is None
assert deps.tk_install_command("darwin", which({"brew"}))[:2] == ["brew", "install"]
assert deps.tk_install_command("win32", which({"apt-get"})) is None
assert "tcl/tk" in deps.tk_advice("win32") and "python3-tk" in deps.tk_advice("linux")
assert deps.tk_available() in (True, False)

# ---- when stage 1 runs at all
assert deps.wants_terminal_setup(no_install=True) is False
assert deps.wants_terminal_setup(no_install=False) in (True, False)    # depends on how the test is run
shutil.rmtree(home)
print("INSTALL OK")
