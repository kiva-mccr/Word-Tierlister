"""Missing packages (deps.py, startup.ensure_packages, errors.ask_yes_no / ask_choices): detection, asking,
installing."""
import os, subprocess, sys
import tkinter as tk
from tkinter import ttk
import deps, errors as E, startup as S
from problems import SetupError
from fonts import init_fonts
from ui_style import apply_ttk_style

# ---- detection and the package table
assert deps.missing(["os", "sys"]) == []
assert deps.missing(["os", "surely_not_installed_pkg_xyz"]) == ["surely_not_installed_pkg_xyz"]
req = [l.split("#")[0].strip() for l in open(os.path.join(os.path.dirname(__file__) or ".", "requirements.txt"))]
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
assert ok and "Successfully installed" in tail and lines[0] == "  Collecting wordfreq" and len(lines) == 2   # blank lines dropped
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
assert choices == [("wordfreq", "wordfreq  (needed)", deps.PURPOSE["wordfreq"], True)]              # its own tick box
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
assert choices[1][1] == "nltk  (optional)" and "offline definitions" in choices[1][2] and all(c[3] for c in choices)
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

# ---- the real question dialog: buttons, Return, Escape and closing the window all answer
def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)
def drive(action):
    def go():
        dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
        btns = {w.cget("text"): w for w in walk(dlg) if w.winfo_class() == "TButton"}
        assert set(btns) == {"Install now", "Not now"}, set(btns)
        labels = " ".join(str(w.cget("text")) for w in walk(dlg) if w.winfo_class() == "TLabel")
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
        assert set(boxes) == {"wordfreq  (needed)", "nltk  (optional)"}, set(boxes)
        for label in untick:
            boxes[label].invoke()
        btns = {w.cget("text"): w for w in walk(dlg) if w.winfo_class() == "TButton"}
        btns[press].invoke()
    return go
CH = [("wordfreq", "wordfreq  (needed)", "ranks words", True), ("nltk", "nltk  (optional)", "definitions", True)]
def pick(): return E.ask_choices("T", "Some packages are needed", "Tick", CH, yes="Install selected", no="Not now", parent=root)
root.after(150, drive_choices([], "Install selected")); assert pick() == {"wordfreq", "nltk"}
root.after(150, drive_choices(["nltk  (optional)"], "Install selected")); assert pick() == {"wordfreq"}
root.after(150, drive_choices([], "Not now")); assert pick() is None
# no window possible: the safe answer (False) and no exception
import contextlib, io
real_dialog = E._dialog
E._dialog = lambda *a, **k: (_ for _ in ()).throw(tk.TclError("no display"))
with contextlib.redirect_stderr(io.StringIO()):
    assert E.ask_yes_no("T", "H", "M", parent=root) is False
E._dialog = real_dialog
root.destroy()
print("DEPS OK")
