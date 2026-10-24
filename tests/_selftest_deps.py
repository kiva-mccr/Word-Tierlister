"""Missing packages (deps.py, startup.ensure_packages, errors.ask_yes_no / ask_choices): detection, asking,
installing."""
import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import os, subprocess, sys, tempfile
import tkinter as tk
from widgets import RoundButton
import deps, errors as E, startup as S
from theme import PALETTE
from problems import SetupError
from fonts import init_fonts
from ui_style import apply_ttk_style

# ---- detection and the package table (every package has a purpose and a size for the install dialog)
assert set(deps.SIZE) == set(deps.PIP_NAMES) == set(deps.DOWNLOAD) == set(deps.PURPOSE) - {"tkinter"} \
    == set(deps.HOMEPAGE) - {"tkinter"}
assert not set(deps.BUILD_PACKAGES) & set(deps.PACKAGES)               # (the builder is not in requirements.txt)
assert deps.missing(["os", "sys"]) == []
assert deps.missing(["os", "surely_not_installed_pkg_xyz"]) == ["surely_not_installed_pkg_xyz"]
req = [l.split("#")[0].strip() for l in open(os.path.join(_paths.ROOT, "requirements.txt"))]
req = [l for l in req if l]
for spec in deps.PACKAGES.values():                                   # requirements.txt lists every package
    assert spec in req or spec.split(">=")[0] in [r.split(">=")[0] for r in req], spec

# ---- install(): streams pip's lines through log, reports success and the tail on failure
real_popen = subprocess.Popen
def fake_popen(script, code):
    def popen(cmd, **kw):
        assert cmd[:4] == [sys.executable, "-m", "pip", "install"] and "wordfreq>=3.0" in cmd, cmd
        return real_popen([sys.executable, "-c", f"{script}\nraise SystemExit({code})"], **{k: v for k, v in kw.items() if k != "creationflags"})
    return popen
lines = []
deps.subprocess.Popen = fake_popen("print('Collecting wordfreq'); print(); print('Successfully installed wordfreq-3.1')", 0)
ok, tail = deps.install(["wordfreq"], lines.append)
from constants import parse_plan
assert ok and "Successfully installed" in tail and parse_plan(lines[0]) == deps.INSTALL_STEPS
assert lines[1] == "Downloading wordfreq (about 59 MB)..."                   # the first main step, with its size
assert lines[2:] == ["  Successfully installed wordfreq-3.1"]                # blank lines and "Collecting" dropped
deps.subprocess.Popen = fake_popen("print('error: externally-managed-environment')", 1)
ok, tail = deps.install(["wordfreq"], lambda l: None)
assert not ok and "externally-managed-environment" in tail
deps.subprocess.Popen = real_popen
assert deps.pip_available() in (True, False)

# ---- ensure_packages flow (asking and installing are stubbed)
root = tk.Tk(); root.withdraw(); init_fonts(root); apply_ttk_style(root)
state = {"missing": ["wordfreq"]}
S.deps.missing = lambda names: [n for n in names if n in state["missing"]]
S.deps.pip_available = lambda: state.get("pip", True)
asked, installs = [], []
def ask(title, headline, message, choices, yes="OK", no="Cancel", parent=None):
    asked.append((headline, message, choices, yes, no))
    a = state["answer"]
    return set(a) if a is not None else None            # the ticked names, or None for "Not now"
S.ask_choices = ask
def installer(ok, tail="", clears=True):
    def run(names, log):
        installs.append(list(names)); log("  Collecting " + names[0])
        if ok and clears: state["missing"] = [n for n in state["missing"] if n not in names]
        return ok, tail
    return run
ALL = ["wordfreq", "nltk"]

state["missing"] = []; assert S.ensure_packages(root, ["wordfreq"]) is True and not asked      # nothing missing: silent
state.update(missing=["wordfreq"], answer=None)
assert S.ensure_packages(root, ["wordfreq"], installer=installer(True)) is False and installs == []       # "Not now"
headline, message, choices, yes, no = asked[-1]
assert headline == "A package is needed" and (yes, no) == ("Install selected", "Not now")
assert [c[0] for c in choices] == ["wordfreq"] and choices[0][3:5] == (True, True)                 # its own tick box
assert choices[0][1] == " (required, about 70 MB)"                                                 # with its size
assert choices[0][5] == ("wordfreq", deps.HOMEPAGE["wordfreq"])                                    # its name links (UI-30)
assert choices[0][2] == deps.PURPOSE["wordfreq"]                                                    # just the reason
state.update(answer=["wordfreq"])
assert S.ensure_packages(root, ["wordfreq"], installer=installer(True)) is True and installs == [["wordfreq"]]
state.update(missing=["wordfreq"], answer=[])                                                      # unticked it
assert S.ensure_packages(root, ["wordfreq"], installer=installer(True)) is False and installs == [["wordfreq"]]
state.update(missing=["wordfreq"], answer=["wordfreq"])
try: S.ensure_packages(root, ["wordfreq"], installer=installer(False, "error: externally-managed-environment")); raise AssertionError
except SetupError as e: assert "virtual environment" in str(e) and "-m venv" in str(e)              # no restart given: manual steps
state.update(missing=["wordfreq"])
try: S.ensure_packages(root, ["wordfreq"], installer=installer(False, "ERROR: No matching distribution\nno internet")); raise AssertionError
except SetupError as e: assert "Could not install wordfreq" in str(e) and "no internet" in str(e) and "pip install wordfreq>=3.0" in str(e)
state.update(missing=["wordfreq"])
try: S.ensure_packages(root, ["wordfreq"], installer=installer(True, clears=False)); raise AssertionError          # pip "succeeded" but still missing
except SetupError as e: assert "Could not install" in str(e)
state.update(missing=["wordfreq"], pip=False)
S.deps.ensure_pip = lambda: False                                    # (never the real ensurepip in a test)
system_install_command = deps.system_install_command
S.deps.system_install_command = lambda what, window=False: None      # (nothing known to install pip with: told)
try: S.ensure_packages(root, ["wordfreq"], installer=installer(True)); raise AssertionError
except SetupError as e: assert "pip is not available" in str(e) and "pip install wordfreq" in str(e)
state.update(pip=True, missing=["wordfreq"]); n = len(asked)
sys.frozen = True                                                                                  # packaged build: never installs
assert S.ensure_packages(root, ["wordfreq"], installer=installer(True)) is False and len(asked) == n
del sys.frozen

# ---- required and optional together: one dialog, each its own choice
state.update(missing=list(ALL), answer=ALL); installs.clear()
assert S.ensure_packages(root, ["wordfreq"], optional=["nltk"], installer=installer(True)) is True
assert installs == [ALL]                                                            # one pip run for what was ticked
headline, message, choices = asked[-1][:3]
assert headline == "Some packages are needed" and [c[0] for c in choices] == ALL
assert choices[1][1] == " (optional, about 35 MB)" and choices[1][5][1] == deps.HOMEPAGE["nltk"] and "offline definitions" in choices[1][2] and all(c[3] for c in choices)
assert [c[4] for c in choices] == [True, False]                                     # only the required one gets the *
# required ticked, optional unticked: installs only the required one, remembers the optional "no"
state.update(missing=list(ALL), answer=["wordfreq"]); installs.clear(); remembered = []
assert S.ensure_packages(root, ["wordfreq"], optional=["nltk"], installer=installer(True), on_decline=remembered.append) is True
assert installs == [["wordfreq"]] and remembered == [["nltk"]]
# optional ticked, required unticked: installs nltk, still reports the required one missing
state.update(missing=list(ALL), answer=["nltk"]); installs.clear(); remembered = []
assert S.ensure_packages(root, ["wordfreq"], optional=["nltk"], installer=installer(True), on_decline=remembered.append) is False
assert installs == [["nltk"]] and remembered == []
# only the optional one missing
state.update(missing=["nltk"], answer=None); asked.clear(); installs.clear(); remembered = []
assert S.ensure_packages(root, ["wordfreq"], optional=["nltk"], on_decline=remembered.append) is True
assert asked[-1][0] == "An optional package is available" and remembered == [["nltk"]] and installs == []
n = len(asked)
assert S.ensure_packages(root, ["wordfreq"], optional=["nltk"], declined={"nltk"}) is True and len(asked) == n   # not asked again
state.update(missing=list(ALL), answer=["wordfreq"]); installs.clear()
assert S.ensure_packages(root, ["wordfreq"], optional=["nltk"], declined={"nltk"}, installer=installer(True)) is True
assert installs == [["wordfreq"]] and [c[0] for c in asked[-1][2]] == ["wordfreq"]   # declined one not even listed
state.update(missing=["nltk"], answer=["nltk"])
def nltk_fails(names, log):
    return False, "ERROR: nltk failed"
import contextlib, io
with contextlib.redirect_stderr(io.StringIO()) as err:
    assert S.ensure_packages(root, ["wordfreq"], optional=["nltk"], installer=nltk_fails) is True   # optional failure: no error
assert "optional" in err.getvalue()
state.update(missing=["nltk"], pip=False)
assert S.ensure_packages(root, ["wordfreq"], optional=["nltk"]) is True            # no pip + only optional missing: silent
state.update(pip=True)

# ---- pip refused (externally-managed): offers a private environment and restarts in it
state.update(missing=["wordfreq"], answer=["wordfreq"])
yes_no = []
S.ask_yes_no = lambda *a, **k: (yes_no.append(a[1]), state["venv_ok"])[1]
made, restarted = [], []
S.deps.make_private_env = lambda home, names, log: (made.append((home, names)), (True, "ok", "/venv/bin/python"))[1]
state["venv_ok"] = True
S.ensure_packages(root, ["wordfreq"], installer=installer(False, "error: externally-managed-environment"),
                  restart=restarted.append, home="/prog")
assert yes_no == ["Make a private environment for the program?"] and made == [("/prog", ["wordfreq"])]
assert restarted == ["/venv/bin/python"]
state.update(missing=["wordfreq"], venv_ok=False)                                 # said no: manual steps
try: S.ensure_packages(root, ["wordfreq"], installer=installer(False, "error: externally-managed-environment"),
                       restart=restarted.append, home="/prog"); raise AssertionError
except SetupError as e: assert "-m venv" in str(e) and len(restarted) == 1

# ---- asked for: what comes from the system (pip, venv, Python) is offered too, not only told (the system's
# package manager; from the window the desktop's own password prompt, pkexec)
def which_of(tools):
    return lambda name: f"/usr/bin/{name}" if name in tools else None
real_euid = deps.os.geteuid
deps.os.geteuid = lambda: 1000
assert system_install_command("pip", "linux", which_of({"dnf", "pkexec"}), window=True) == \
    ["pkexec", "dnf", "install", "-y", "python3-pip"]
assert system_install_command("venv", "linux", which_of({"apt-get"})) == ["sudo", "apt-get", "install", "-y", "python3-venv"]
assert system_install_command("venv", "linux", which_of({"dnf"})) is None          # (Fedora's Python has it)
assert system_install_command("python", "linux", which_of({"pacman", "pkexec"}), window=True)[-2:] == ["python", "tk"]
assert system_install_command("pip", "linux", which_of({"apt-get"}), window=True) is None   # (no password prompt)
assert system_install_command("python", "win32", which_of({"winget"}))[:2] == ["winget", "install"]
assert system_install_command("python", "darwin", which_of({"brew"})) == ["brew", "install", "python-tk"]
assert system_install_command("tkinter", "linux", which_of({"zypper"})) == ["sudo", "zypper", "--non-interactive",
                                                                                 "install", "python3-tk"]
deps.os.geteuid = lambda: 0
assert system_install_command("pip", "linux", which_of({"apt-get"}), window=True)[0] == "apt-get"     # (as root)
deps.os.geteuid = real_euid
assert deps.run_system_install([sys.executable, "-c", "print('done')"], log=installs.append) is True and "  done" in installs
assert deps.run_system_install(["/nonexistent/tool"], log=installs.append) is False
# no pip: ensurepip first, then the system's package (asked); a required package then installs as usual
state.update(missing=["wordfreq"], answer=["wordfreq"], pip=False)
S.deps.ensure_pip = lambda: False
S.deps.system_install_command = lambda what, window=False: ["pkexec", "dnf", "install", "-y", f"python3-{what}"]
yes_no.clear(); ran = []
S.ask_yes_no = lambda *a, **k: (yes_no.append(a[1]), True)[1]
def system(cmd, log):
    ran.append(cmd); state["pip"] = True
    return True
installs.clear()
assert S.ensure_packages(root, ["wordfreq"], installer=installer(True), system_installer=system) is True
assert yes_no == ["Install pip, Python's package installer?"] and ran == [["pkexec", "dnf", "install", "-y", "python3-pip"]]
assert installs == [["wordfreq"]]
state.update(missing=["wordfreq"], pip=False); yes_no.clear()               # said no: the old message, nothing run
S.ask_yes_no = lambda *a, **k: (yes_no.append(a[1]), False)[1]
try: S.ensure_packages(root, ["wordfreq"], installer=installer(True), system_installer=system); raise AssertionError
except SetupError as e: assert "pip is not available" in str(e) and len(ran) == 1
# the private environment needs venv (Debian keeps it apart): offered, then made again
state.update(missing=["wordfreq"], pip=True)
tries = []
def venv_missing_once(home, names, log):
    tries.append(1)
    return (len(tries) > 1, "Could not make the private environment.", "/nonexistent/venv/bin/python")
S.deps.make_private_env = venv_missing_once
S.ask_yes_no = lambda *a, **k: (yes_no.append(a[1]), True)[1]
yes_no.clear(); restarted.clear()
S.ensure_packages(root, ["wordfreq"], installer=installer(False, "error: externally-managed-environment"),
                  restart=restarted.append, home="/prog", system_installer=system)
assert yes_no == ["Make a private environment for the program?", "Install Python's venv module?"] and len(tries) == 2
assert ran[-1][-1] == "python3-venv" and restarted == ["/nonexistent/venv/bin/python"]

# ---- the real question dialog: buttons, Return, Escape and closing the window all answer
def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)
def drive(action):
    def go():
        dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
        btns = {w.cget("text"): w for w in walk(dlg) if isinstance(w, RoundButton)}
        assert set(btns) == {"Install now", "Not now"}, set(btns)
        labels = " ".join(str(w.cget("text")) for w in walk(dlg) if w.winfo_class() in ("TLabel", "Label"))
        assert "needed" in labels
        action(dlg, btns)
    return go
def question(): return E.ask_yes_no("T", "A package is needed", "Explain", yes="Install now", no="Not now", parent=root)
root.deiconify(); root.update()
root.after(150, drive(lambda d, b: b["Install now"].invoke())); assert question() is True
root.after(150, drive(lambda d, b: b["Not now"].invoke())); assert question() is False
root.after(150, drive(lambda d, b: d.event_generate("<Return>"))); assert question() is True
root.after(150, drive(lambda d, b: d.event_generate("<Escape>"))); assert question() is False
root.after(150, drive(lambda d, b: d.protocol("WM_DELETE_WINDOW") and d.tk.call(d.protocol("WM_DELETE_WINDOW")))); assert question() is False
# the tick-box dialog: what is ticked when "Install selected" is pressed comes back; "Not now" gives None
def drive_choices(untick, press):
    def go():
        dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
        boxes = {w.cget("text"): w for w in walk(dlg) if w.winfo_class() == "TCheckbutton"}
        assert set(boxes) == {"wordfreq  (required)", "nltk  (optional)"}, set(boxes)
        stars = [w for w in walk(dlg) if w.winfo_class() == "TLabel" and w.cget("text") == "*"]
        assert len(stars) == 1 and str(stars[0].cget("foreground")) == PALETTE["required"]   # red, on wordfreq only
        for label in untick:
            boxes[label].invoke()
        btns = {w.cget("text"): w for w in walk(dlg) if isinstance(w, RoundButton)}
        btns[press].invoke()
    return go
CH = [("wordfreq", "wordfreq  (required)", "ranks words", True, True), ("nltk", "nltk  (optional)", "definitions", True, False)]
def pick(): return E.ask_choices("T", "Some packages are needed", "Tick", CH, yes="Install selected", no="Not now", parent=root)
root.after(150, drive_choices([], "Install selected")); assert pick() == {"wordfreq", "nltk"}
root.after(150, drive_choices(["nltk  (optional)"], "Install selected")); assert pick() == {"wordfreq"}
root.after(150, drive_choices([], "Not now")); assert pick() is None
def enter_after_untick():
    dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    [w for w in walk(dlg) if w.winfo_class() == "TCheckbutton"][1].invoke()      # untick nltk
    btn = [w for w in walk(dlg) if isinstance(w, RoundButton) and w.cget("text") == "Install selected"][0]
    assert btn.cget("bg") == PALETTE["select_bg"]                                # drawn as the default button
    dlg.event_generate("<Return>")
root.after(150, enter_after_untick); assert pick() == {"wordfreq"}              # Enter = Install selected
# a choice with a link (UI-30): the name is a quiet link that opens its page; the rest of the label still ticks
opened = []
real_open, E.open_link = E.open_link, opened.append
def drive_link():
    dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    link = [w for w in walk(dlg) if getattr(w, "url", None)][0]
    assert link.cget("text") == "wordfreq" and str(link.cget("fg")) == PALETTE["muted"] and link.cget("cursor") == "hand2"
    assert tk.font.Font(font=link.cget("font")).actual("underline")
    link.event_generate("<Button-1>"); dlg.update()
    rest = [w for w in walk(dlg) if w.winfo_class() == "TLabel" and str(w.cget("text")).startswith(" (required")][0]
    rest.event_generate("<Button-1>"); dlg.update()                             # unticks wordfreq
    [w for w in walk(dlg) if isinstance(w, RoundButton) and w.cget("text") == "Install selected"][0].invoke()
root.after(150, drive_link)
LINKED = [("wordfreq", " (required, about 70 MB)", "ranks words", True, True, ("wordfreq", deps.HOMEPAGE["wordfreq"])),
          ("nltk", " (optional)", "definitions", True, False, ("nltk", deps.HOMEPAGE["nltk"]))]
assert E.ask_choices("T", "H", "M", LINKED, yes="Install selected", parent=root) == {"nltk"}
assert opened == [deps.HOMEPAGE["wordfreq"]]
E.open_link = real_open
# no window possible: the safe answer (False) and no exception
import contextlib, io
real_dialog = E._dialog
E._dialog = lambda *a, **k: (_ for _ in ()).throw(tk.TclError("no display"))
with contextlib.redirect_stderr(io.StringIO()):
    assert E.ask_yes_no("T", "H", "M", parent=root) is False
E._dialog = real_dialog
root.destroy()

# ---- ST-5: started from a terminal on Linux / macOS, the program carries on in its own session
class Tty:
    def __init__(self, tty=True): self.tty = tty
    def isatty(self): return self.tty
term, desk = (Tty(), Tty()), {"DISPLAY": ":0"}
assert deps.should_detach(env=desk, streams=term, posix=True)
assert not deps.should_detach(console=True, env=desk, streams=term, posix=True)              # --console keeps it
assert not deps.should_detach(env=desk, streams=(Tty(), Tty(False)), posix=True)            # output redirected
assert not deps.should_detach(env=dict(desk, **{deps.DETACHED_ENV: "1"}), streams=term, posix=True)   # never twice
assert not deps.should_detach(env=desk, streams=term, posix=False)                          # Windows: its own way
if sys.platform != "darwin":
    assert not deps.should_detach(env={}, streams=term, posix=True)                         # no desktop: stay put
    assert deps.should_detach(env={"WAYLAND_DISPLAY": "wayland-0"}, streams=term, posix=True)
said, started = [], []


class Child:
    def __init__(self, code, after, text=b""):
        self.code, self.after, self.text, self.polls = code, after, text, 0
    def poll(self):
        self.polls += 1
        return self.code if self.polls > self.after else None


def popen_of(child):
    def popen(cmd, stdin=None, stdout=None, stderr=None, start_new_session=False, env=None):
        started.append((cmd, start_new_session, env.get(deps.DETACHED_ENV)))
        stdout.write(child.text); stdout.flush()
        return child
    return popen
clock = [0.0]
tick = lambda: clock[0]
step = lambda dt: clock.__setitem__(0, clock[0] + 0.05)
# it gets going: the terminal is told it can close, and gets its prompt back (exit 0)
assert deps.detach_terminal(["tierlist.py", "--db", "x.db"], out=said.append, popen=popen_of(Child(None, 0)),
                         clock=tick, sleep=step) == 0
assert started[-1] == ([sys.executable, "tierlist.py", "--db", "x.db"], True, "1") and "close this terminal" in said[-1]
# it fails straight away (no window could open): what it said is shown here, with its exit code
clock[0] = 0.0
assert deps.detach_terminal(["tierlist.py"], out=said.append, popen=popen_of(Child(1, 2, b"TclError: no display")),
                         clock=tick, sleep=step) == 1
assert said[-1] == "TclError: no display"
# File > Add to applications menu: a launcher with no terminal; adding it again updates it
entry = deps.desktop_entry("/usr/bin/python3", '/home/me/My "Tier" List/tierlist.py')
assert 'Exec="/usr/bin/python3" "/home/me/My \\"Tier\\" List/tierlist.py"' in entry and "Terminal=false" in entry
assert "Path=/home/me/My \"Tier\" List" in entry and entry.startswith("[Desktop Entry]")
assert 'Exec="/opt/word-tierlist"' in deps.desktop_entry("/opt/word-tierlist", None)        # a built program
home = tempfile.mkdtemp()
os.environ.pop("XDG_DATA_HOME", None)
path, how = deps.add_to_menu("/usr/bin/python3", "/x/tierlist.py", home=home)
assert how == "added" and path == os.path.join(home, ".local", "share", "applications", "word-tierlist.desktop")
icon = os.path.join(home, ".local", "share", "icons", "word-tierlist.png")        # (IC-1: the icon copied beside)
assert open(path).read() == deps.desktop_entry("/usr/bin/python3", "/x/tierlist.py", icon=icon)
assert f"Icon={icon}" in open(path).read() and open(icon, "rb").read() == open(deps.ICON, "rb").read()
assert deps.add_to_menu("/usr/bin/python3", "/y/tierlist.py", home=home)[1] == "updated" and "/y/tierlist.py" in open(path).read()
print("DEPS OK")
