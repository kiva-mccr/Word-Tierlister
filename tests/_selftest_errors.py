"""Friendly errors (ST-2): plain-language messages, the dialog, the safety net and the exit paths."""
import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import contextlib, errno, io, os, sqlite3, sys, tempfile, threading, urllib.error
import tkinter as tk
import errors as E
import problems as P

tmp = tempfile.mkdtemp()
log = os.path.join(tmp, "tierlist.log")

# ---- describe(): the plain-language text
assert "busy" in P.describe(sqlite3.OperationalError("database is locked"))[0]
assert "can't be opened" in P.describe(sqlite3.OperationalError("unable to open database file"))[0]
assert "damaged" in P.describe(sqlite3.DatabaseError("file is not a database"))[0]
assert "disk is full" in P.describe(OSError(errno.ENOSPC, "No space left"))[0]
assert "internet" in P.describe(urllib.error.URLError("dns"))[0]
assert "internet" in P.describe(ConnectionResetError())[0]
assert "allowed" in P.describe(PermissionError(errno.EACCES, "denied", "/x/save.db"))[0]
assert "/x/save.db" in P.describe(PermissionError(errno.EACCES, "denied", "/x/save.db"))[0]
assert "memory" in P.describe(MemoryError())[0]
head, advice = P.describe(P.SetupError("Do this next"))
assert advice == "Do this next"
assert "unexpected" in P.describe(KeyError("x"))[0]

# ---- log helpers never raise; streams are repaired when there is no console
P.append_log(log, "line one"); P.append_log(log, "line two\n")
assert open(log).read() == "line one\nline two\n"
P.append_log(os.path.join(tmp, "no", "such", "dir.log"), "ignored")           # must not raise
saved = sys.stdout, sys.stderr
try:
    sys.stdout = sys.stderr = None
    P.ensure_streams(os.path.join(tmp, "s.log"))
    print("hello")
    assert sys.stdout is not None and "hello" in open(os.path.join(tmp, "s.log")).read()
finally:
    sys.stdout, sys.stderr = saved

# ---- wordsource: a missing package is a SetupError, not a bare sys.exit
import wordsource as W
sys.modules["wordfreq"] = None                       # makes `import wordfreq` fail
try:
    W.build_word_list()
    raise AssertionError("expected SetupError")
except P.SetupError as e:
    assert "pip install wordfreq" in str(e)
finally:
    del sys.modules["wordfreq"]

# ---- run_guarded: quiet stop, dialog for setup problems, messages and crashes
shown = []
real_show = E.show_error
E.show_error = lambda title, message, details=None, parent=None, headline=None: shown.append((headline, message, details))
quiet = contextlib.redirect_stderr(io.StringIO())

def run(fn):
    with quiet:
        try:
            E.run_guarded(fn, log, "/save/tierlist.db")
        except SystemExit as exc:
            return exc.code
    return "returned"

def stop(): raise SystemExit(P.STOPPED_MESSAGE)
assert run(stop) == P.STOPPED_MESSAGE and shown == []                            # deliberate stop: silent
assert run(lambda: None) == "returned" and shown == []
def setup(): raise P.SetupError("Install the thing, then run again.")
assert run(setup) == 1 and "Install the thing" in shown[-1][1] and shown[-1][2] is None
def msg(): raise SystemExit("Some plain message")
assert run(msg) == "Some plain message" and "Some plain message" in shown[-1][1]
def disk(): raise OSError(errno.ENOSPC, "No space left on device")
assert run(disk) == 1 and "disk is full" in shown[-1][0] and "/save/tierlist.db" in shown[-1][1]
def crash(): raise KeyError("oops")
assert run(crash) == 1 and "KeyError" in shown[-1][2] and "progress is saved" in shown[-1][1]
assert "KeyError" in open(log).read()                                           # traceback logged

# ---- install_handlers: Tk callback errors show one dialog, repeats are only logged
root = tk.Tk(); root.withdraw()
from fonts import init_fonts
from ui_style import apply_ttk_style
from widgets import RoundButton
init_fonts(root); apply_ttk_style(root)
shown.clear()
log2 = os.path.join(tmp, "h.log")
old_hooks = sys.excepthook, threading.excepthook
E.install_handlers(root, log2, "/save/tierlist.db")
root.after(0, lambda: 1 / 0)
root.after(10, lambda: 1 / 0)                         # same error again straight away
root.after(20, root.quit)
with quiet:
    root.mainloop()
assert len(shown) == 1 and "ZeroDivisionError" in shown[0][2], shown
assert open(log2).read().count("ZeroDivisionError") >= 2                        # both are in the log
E._state.update(last_key=None)
root.after(0, lambda: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
root.after(20, root.quit)
with quiet:
    root.mainloop()
assert len(shown) == 2 and "busy" in shown[1][0]
# a worker thread's error is logged but never opens a dialog (Tk is not thread-safe)
t = threading.Thread(target=lambda: 1 / 0); 
with quiet:
    t.start(); t.join()
assert len(shown) == 2 and open(log2).read().count("ZeroDivisionError") >= 3
# the program keeps running after an error
ran = []
root.after(0, lambda: ran.append(1)); root.after(20, root.quit); root.mainloop()
assert ran == [1]
sys.excepthook, threading.excepthook = old_hooks
E.show_error = real_show

# ---- the real dialog: text shown, details hidden until asked for, Copy details works, OK closes
def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)

def drive():
    dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    labels = " ".join(str(w.cget("text")) for w in walk(dlg) if w.winfo_class() in ("TLabel", "Label"))
    assert "Headline here" in labels and "Explain it" in labels
    txt = [w for w in walk(dlg) if isinstance(w, tk.Text)][0]
    assert not txt.winfo_ismapped()
    btns = {w.cget("text"): w for w in walk(dlg) if isinstance(w, RoundButton)}
    assert set(btns) == {"OK", "Copy details", "Show details"}, set(btns)
    btns["Show details"].invoke(); dlg.update()
    assert txt.winfo_ismapped() and "tb line" in txt.get("1.0", "end")
    btns["Copy details"].invoke()
    assert "Explain it" in dlg.clipboard_get() and btns["Copy details"].cget("text") == "Copied"
    assert dlg.winfo_x() >= 0 and dlg.winfo_y() >= 0
    btns["OK"].invoke()

root.deiconify(); root.update()
root.after(150, drive)
E.show_error("Test", "Explain it", details="tb line", parent=root, headline="Headline here")
assert not [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]       # closed
# with no details there is no Copy / Show buttons
def drive2():
    dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    btns = [w.cget("text") for w in walk(dlg) if isinstance(w, RoundButton)]
    assert btns == ["OK"], btns
    dlg.destroy()
root.after(150, drive2)
E.show_error("Test", "Plain", parent=root)
# no parent given: it makes its own hidden window, shows the dialog in it, then removes it
seen = []
real_dialog = E._dialog
E._dialog = lambda parent, *a: seen.append((parent.winfo_viewable(), a[1:3]))
E.show_error("Test", "No parent", headline="Own window")
assert seen == [(0, ("Own window", "No parent"))], seen
E._dialog = real_dialog
# no window system at all: falls back to stderr instead of raising
E._dialog = lambda *a: (_ for _ in ()).throw(tk.TclError("no display"))
buf = io.StringIO()
with contextlib.redirect_stderr(buf):
    E.show_error("Test", "Fallback text", headline="H")
assert "Fallback text" in buf.getvalue()
E._dialog = real_dialog
root.destroy()
print("ERRORS OK")
