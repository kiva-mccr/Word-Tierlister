import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""Developer tools from the window (asked for: not only by command): Settings > Developer tools (off to start with,
saved) shows small bubbles at the top right of Source & Updates ("Nightly", "Log", "Crash test"); none while it is
off, and How words are dealt has none (OB-14: the review of rude meanings and the tuner went with the rules)."""
import os, tempfile, time
os.environ["HOME"] = tempfile.mkdtemp()
os.environ["USERPROFILE"] = os.environ["HOME"]           # (Windows reads home from USERPROFILE)
import tkinter as tk
import tierlist as T
import sources
import standalone as S
from constants import VERSION
from buttons import DevBubble

WORDS = [f"w{i:04d}" for i in range(40)]
folder = tempfile.mkdtemp()
s = T.Store(os.path.join(folder, "dev.db")); s.insert_words(WORDS); s.set_anchors(WORDS[:6])
root = tk.Tk(); app = T.App(root, s, T.Definitions(s))
app.anim.reduce_motion = True


def pump(n=6):
    for _ in range(n):
        root.update(); time.sleep(0.02)


pump()
# ---- the switch: in the Settings menu, off to start with, saved -------------------------------------------------
settings = dict(app._menu_items())["Settings"]
assert ("check", "Developer tools", app.dev_var, app.toggle_dev) in settings
assert app.dev_tools is False and not app.dev_var.get()
d = app.edit_dealing(); pump(3)
assert not hasattr(d, "bubbles") and not d.dlg.head_row.winfo_children()[1:]     # (only the headline)
d.dlg.close()
app.dev_var.set(True); app.toggle_dev()
assert app.dev_tools and s.get_meta("dev_tools") == "1"
d = app.edit_dealing(); pump(3)
assert not hasattr(d, "bubbles") and not d.dlg.head_row.winfo_children()[1:]     # (none here any more: OB-14)
d.dlg.close()

# ---- the bubble itself ------------------------------------------------------------------------------------------
clicks, var = [], tk.BooleanVar(value=False)
b = DevBubble(root, "Nightly", lambda: clicks.append(var.get()), variable=var); b.pack(); pump(2)
assert not b.lit()
b.invoke(); assert var.get() and b.lit() and clicks == [True]
b.event_generate("<Enter>"); b.refresh(); assert int(b.cget("width")) > 20
b.destroy()
pump(5)

# ---- Source & Updates: Nightly (a switch), Log, Crash test ----------------------------------------------------------
proj = tempfile.mkdtemp()
for name, text in (("tierlist.py", "x = 1\n"), ("src/a.py", "a = 1\n")):
    os.makedirs(os.path.join(proj, os.path.dirname(name)), exist_ok=True)
    open(os.path.join(proj, name), "wb").write(text.encode())
main = {"short": "4f2c9ab", "when": time.time() - 7200, "message": "x", "page": "", "nightly": True,
        "version": VERSION + "+4f2c9ab", "files": S.local_files(proj)}
release = {"version": VERSION, "tag": "v" + VERSION, "source": "", "page": "", "assets": {}}


def dialog():
    dlg = sources.SourceDialog(app, frozen=False, root_dir=proj, source=None, platform="darwin",
                               check=lambda: release, nightly=lambda: main)
    for _ in range(40):
        pump(1)
        if dlg.checked:
            break
    return dlg


def said(dlg):
    return " ".join(w.cget("text") for w in dlg.nightly_box.winfo_children() if "text" in w.keys())


d = dialog()
assert list(d.bubbles) == ["Nightly", "Log", "Crash test"] and d.bubbles["Nightly"].lit()
assert "you have main as it is now (commit 4f2c9ab, 2 hours ago)" in said(d), said(d)   # (shown though the same)
d.bubbles["Nightly"].invoke(); pump(2)
assert not d.bubbles["Nightly"].lit() and said(d) == "" and s.get_meta("nightly_always") == "0"
d.bubbles["Nightly"].invoke(); pump(2)
assert "you have main" in said(d) and s.get_meta("nightly_always") == "1"
# the log: opened with the system's own program; none yet: a note
opened = []
S.open_folder = opened.append
log = os.path.join(folder, "tierlist.log")
d.bubbles["Log"].invoke(); pump(2)
assert not opened
open(log, "w").write("--- a session\n")
d.bubbles["Log"].invoke()
assert opened == [log]
# the crash test: the dialog closes, then a real error goes through the safety net
errors_seen = []
root.report_callback_exception = lambda *exc: errors_seen.append(exc[1])
app.devtools.crash_test(d.dlg, delay=10)
assert not d.dlg.alive()
for _ in range(20):
    pump(1)
    if errors_seen:
        break
assert errors_seen and isinstance(errors_seen[0], ZeroDivisionError)
# switched off: no bubbles and no nightly section at all (it showed to everyone while main was ahead: reported)
app.dev_var.set(False); app.toggle_dev()
d = dialog()
assert d.nightly_always is None and not hasattr(d, "bubbles") and said(d) == ""
d.close()
# Keyboard shortcuts has no review keys any more (OB-14)
import keymap
assert "review" not in dict(keymap.GROUPS) and not any(a.startswith("review") for a, *_ in keymap.ACTIONS)
app.dev_var.set(True); app.toggle_dev()
k = app.edit_keys(); root.update()
assert "left" in k.rows
k.dlg.close(); root.update()
root.destroy()
print("devtools self-test passed")
