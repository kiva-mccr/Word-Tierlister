"""Stage 1 of installing (ST-4, deps.terminal_setup): in the terminal, before any window, only tkinter is asked
about; every Python package is left for the window. Also the private environment helpers. No tkinter needed."""
import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import os, shutil, sys, tempfile
import deps

home = tempfile.mkdtemp()
real_missing = deps.missing
state = {}
APT = ["sudo", "apt-get", "install", "-y", "python3-tk"]

def setup(answers=(), tk=True, tk_cmd=tuple(APT), run_code=0, tk_after=True):
    """Run terminal_setup with everything external stubbed; returns (result or SystemExit, log)."""
    state.update(tk=tk, answers=list(answers), out=[], asked=[], runs=[], restarts=[])
    def ask(q):
        state["asked"].append(q)
        if not state["answers"]:
            raise EOFError
        return state["answers"].pop(0)
    def run(cmd):
        state["runs"].append(list(cmd))
        if run_code == 0 and tk_after:
            state["tk"] = True
        return run_code
    try:
        result = deps.terminal_setup(["tierlist.py", "--db", "x.db"], ask=ask, out=state["out"].append, run=run,
                                     has_tk=lambda: state["tk"], tk_command=list(tk_cmd) if tk_cmd else [],
                                     restarter=lambda py, argv: state["restarts"].append((py, argv)))
    except SystemExit as exc:
        result = exc
    return result, "\n".join(state["out"])

os.environ.pop(deps.REEXEC_ENV, None)

# tkinter there: silent, no question, even with Python packages missing (those are the window's job)
deps.missing = lambda names: list(names)
r, log = setup()
assert r is True and log == "" and not state["asked"]
deps.missing = real_missing

# tkinter missing, Enter (= yes): the package manager installs it, then the program restarts to open the window
r, log = setup(answers=[""], tk=False)
assert r is True and state["runs"] == [APT] and state["restarts"] == [(sys.executable, ["tierlist.py", "--db", "x.db"])]
assert "needs tkinter" in log and "sudo apt-get install -y python3-tk" in log and log.endswith("Opening the window...")
assert "asked about in the window" in log and "wordfreq" not in log                  # no Python packages here
assert "More about it: " + deps.HOMEPAGE["tkinter"] in log                           # its page (UI-30)
assert state["asked"] == ["Install it now? [Y/n] "]
# a stray answer is asked again
r, log = setup(answers=["maybe", "y"], tk=False)
assert r is True and "Please answer y or n." in log and len(state["asked"]) == 2
# "no", or no terminal input at all (EOF): the window cannot open, so it stops with what to do
for answers in (["n"], []):
    r, log = setup(answers=answers, tk=False)
    assert isinstance(r, SystemExit) and "cannot open without tkinter" in str(r) and not state["runs"]
# no known way to install it here: explains instead of asking
r, log = setup(tk=False, tk_cmd=None)
assert isinstance(r, SystemExit) and "cannot be installed from here" in str(r) and not state["asked"]
# the package manager ran but this Python still has no tkinter (a pyenv Python, say), or it failed
r, log = setup(answers=["y"], tk=False, tk_after=False)
assert isinstance(r, SystemExit) and "could not be installed for this Python" in str(r)
r, log = setup(answers=["y"], tk=False, run_code=100)
assert isinstance(r, SystemExit) and not state["restarts"]

# ---- the private environment (made by the window's install step when pip is refused)
restarts = []
vpy = deps.venv_python(os.path.join(home, ".venv"))
assert deps.use_private_env(["t.py"], home, restarter=lambda p, a: restarts.append(p)) is False   # none yet
os.makedirs(os.path.dirname(vpy)); open(vpy, "w").close()
deps.missing = lambda names: list(names)                                           # wordfreq missing here...
assert deps.use_private_env(["t.py"], home, has_tk=lambda: True, restarter=lambda p, a: restarts.append(p)) is True
assert restarts == [vpy]                                                           # ...so restart in .venv
deps.missing = lambda names: []
assert deps.use_private_env(["t.py"], home, has_tk=lambda: True, restarter=lambda p, a: restarts.append(p)) is False
assert deps.use_private_env(["t.py"], home, has_tk=lambda: False, restarter=lambda p, a: restarts.append(p)) is True
os.environ[deps.REEXEC_ENV] = "1"                                                  # never loops
assert deps.use_private_env(["t.py"], home, has_tk=lambda: False, restarter=lambda p, a: restarts.append(p)) is False
os.environ.pop(deps.REEXEC_ENV)
deps.missing = real_missing
shutil.rmtree(os.path.join(home, ".venv"))

# make_private_env: makes .venv, then pip-installs into ITS python
calls = []
real_make, real_install = deps._make_venv, deps.install
def fake_make(venv, log):
    os.makedirs(os.path.dirname(deps.venv_python(venv)), exist_ok=True); open(deps.venv_python(venv), "w").close()
    return 0
deps._make_venv = fake_make
deps.install = lambda names, log, python=None, plan=True: (calls.append((names, python)), (True, "ok"))[1]
ok, tail, py = deps.make_private_env(home, ["wordfreq"], lambda l: None)
assert ok and py == vpy and calls == [(["wordfreq"], vpy)]
shutil.rmtree(os.path.join(home, ".venv"))
deps._make_venv = lambda venv, log: 1                                              # python3-venv missing
ok, tail, py = deps.make_private_env(home, ["wordfreq"], lambda l: None)
assert not ok and "python3-venv" in tail
deps._make_venv, deps.install = real_make, real_install

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

# ---- install() measures the download (pip prints no progress into a pipe): a fake pip that "downloads" a
#      3 MB file in steps into the TMPDIR it was given, then installs
if os.name == "posix":
    fake = os.path.join(home, "fakepy")
    with open(fake, "w") as f:
        f.write("""#!/bin/sh
echo "Collecting big"
echo "  Downloading big-1.0-py3-none-any.whl.metadata (2 kB)"
echo "Downloading big-1.0-py3-none-any.whl (3.0 MB)"
mkdir -p "$TMPDIR/pip-unpack-x"
for i in 1 2 3 4 5 6; do head -c 500000 /dev/zero >> "$TMPDIR/pip-unpack-x/big-1.0-py3-none-any.whl"; sleep 0.4; done
echo "Installing collected packages: big"
echo "Successfully installed big-1.0"
""")
    os.chmod(fake, 0o755)
    got = []
    deps.DOWNLOAD["big"] = 3
    ok, tail = deps.install(["big"], got.append, python=fake)
    deps.DOWNLOAD.pop("big")
    assert ok and "Successfully installed" in tail
    from constants import parse_plan
    assert parse_plan(got[0]) == deps.INSTALL_STEPS and got[1].startswith("Downloading big (about 3 MB)")
    progress = [l for l in got if l.startswith("  ") and " of 3 MB" in l]
    pcts = [int(l.rsplit("(", 1)[1].rstrip("%)")) for l in progress]
    assert len(progress) >= 3 and pcts == sorted(pcts) and pcts[-1] >= 80, progress    # it climbs to near the end
    assert any("MB/s" in l for l in progress)                                       # and says how fast
    assert "Installing..." in got and got.index("Installing...") > got.index(progress[-1])
    assert not any("Downloading big-1.0" in l or "Collecting" in l for l in got)   # pip's own noise left out
    assert not [d for d in os.listdir(tempfile.gettempdir()) if d.startswith("wordtier-pip-")]  # tidied away

shutil.rmtree(home)
print("INSTALL OK")
