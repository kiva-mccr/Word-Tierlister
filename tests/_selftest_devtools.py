import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""Developer tools from the window (asked for: not only by command): Settings > Developer tools (off to start with,
saved) shows small bubbles at the top right of How words are dealt ("Make review words", "Review rude meanings", "Score
the rules", "Tune the rules": the first and last run tools/ from the source) and
Source & Updates ("Nightly", "Log", "Crash test"); none while it is off. The review asks for a file when there is
none next to the save and remembers it; the score compares the answers with the review file's guesses."""
import json, os, tempfile, time
os.environ["HOME"] = tempfile.mkdtemp()
os.environ["USERPROFILE"] = os.environ["HOME"]           # (Windows reads home from USERPROFILE)
import tkinter as tk
import tierlist as T
import app as A
import review as R
import sources
import standalone as S
from constants import VERSION, review_answers_path
from widgets import DevBubble

WORDS = [f"w{i:04d}" for i in range(40)]
folder = tempfile.mkdtemp()
s = T.Store(os.path.join(folder, "dev.db")); s.insert_words(WORDS); s.set_anchors(WORDS[:6])
root = tk.Tk(); app = T.App(root, s, T.Definitions(s))
app.anim.reduce_motion = True
shown = []
A.show_message = lambda *a, **kw: shown.append(a)


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

# ---- the bubble itself ------------------------------------------------------------------------------------------
clicks, var = [], tk.BooleanVar(value=False)
b = DevBubble(root, "Nightly", lambda: clicks.append(var.get()), variable=var); b.pack(); pump(2)
assert not b.lit()
b.invoke(); assert var.get() and b.lit() and clicks == [True]
b.event_generate("<Enter>"); b.refresh(); assert int(b.cget("width")) > 20
b.destroy()

# ---- How words are dealt: the review and its score ------------------------------------------------------------
d = app.edit_dealing(); pump(3)
assert list(d.bubbles) == ["Make review words", "Review rude meanings", "Score the rules", "Tune the rules"]
x_head = d.dlg.head_row.winfo_children()[0].winfo_rootx()
x_bub = d.bubbles["Review rude meanings"].winfo_rootx()
assert x_bub > x_head + d.dlg.head_row.winfo_children()[0].winfo_width(), "the bubbles sit right of the headline"
# no review file next to the save: it asks; no answer, nothing opens and the dialog stays
asked = []
assert app.review_rude(d.dlg, ask=lambda start: asked.append(start)) is None
assert asked == [folder] and d.dlg.alive() and app.review is None
path = os.path.join(tempfile.mkdtemp(), "mine.jsonl")
items = [{"w": "tail", "why": "", "whole": False, "senses": [
             {"key": "k1", "pos": "noun", "labels": [], "gloss": "The back end.", "guess": "clean"},
             {"key": "k2", "pos": "noun", "labels": ["slang"], "gloss": "Sex.", "guess": "sexual"}]},
         {"w": "idiot", "why": "", "whole": True, "senses": [
             {"key": "k3", "pos": "noun", "labels": [], "gloss": "A fool.", "guess": "insult"}]}]
with open(path, "w", encoding="utf-8") as f:
    f.write("".join(json.dumps(it) + "\n" for it in items))
rv = app.review_rude(d.dlg, ask=lambda start: path); pump(3)
assert rv is app.review and rv.alive() and not d.dlg.alive()       # (the dialog closed: it held the input)
assert s.get_meta("review_file") == path and app.review_file() == path       # remembered: not asked again
rv.win.destroy(); app.review = None
# the score: nothing answered yet, then two words
d = app.edit_dealing(); pump(3)
text = app.score_rules(d.dlg)
assert "Nothing answered yet" in text and shown[-1][0] == "Score the rules"
with open(review_answers_path(path), "w", encoding="utf-8") as f:
    f.write(json.dumps({"w": "tail", "keys": ["k1", "k2"], "kinds": ["clean", "crude"], "whole": False}) + "\n")
    f.write(json.dumps({"w": "idiot", "keys": ["k3"], "kinds": ["insult"], "whole": False}) + "\n")
sc = R.score_guesses(R.read_review(path), R.read_answers(review_answers_path(path)))
assert (sc["words"], sc["meanings"], sc["agree"], sc["whole"], sc["whole_agree"]) == (2, 3, 2, 2, 1), sc
assert sc["kinds"]["insult"] == (1, 1, 1) and sc["kinds"]["sexual"] == (0, 1, 0) and sc["kinds"]["crude"] == (0, 0, 1)
text = app.score_rules(d.dlg)
assert "2 words answered, 3 meanings" in text and "67%" in text and "Insult: 100% right, found 1 of 1" in text, text
assert "Crude: - right, found 0 of 1" in text and "Clinical" not in text
d.dlg.close()

# ---- Make review words and Tune the rules: the tools in the source folder (OB-10, OB-11) ----------------------------
src_root = tempfile.mkdtemp()
app.TOOLS_ROOT = src_root
d = app.edit_dealing(); pump(3)
assert app.make_review_words(d.dlg) is None and shown[-1][1] == "Only from the source"    # (no tools/ there)
assert app.tune_rules(d.dlg) is None and shown[-1][1] == "Only from the source"
os.makedirs(os.path.join(src_root, "tools"))
for name in ("measure_rudeness.py", "tune_rudeness.py"):
    open(os.path.join(src_root, "tools", name), "w").write("")
mr = os.path.join(src_root, "tools", "measure_rudeness.py")
asked, ran = [], []
assert app.make_review_words(d.dlg, ask=lambda: asked.append(1) or False) is None and asked    # (no entries: asked)
fresh = os.path.join(folder, "rude_review.jsonl")                    # (no review file yet: sample makes one here)
s.set_meta("review_file", "")
cmds = app.make_review_words(d.dlg, ask=lambda: True, run=lambda c, cwd: ran.append((c, cwd)) or (0, "Wrote 1,500"))
assert [c[1:] for c in cmds] == [[mr, "fetch"], [mr, "sample", "--out", fresh]] and ran[0][1] == src_root
pump(3)
assert app._tool_job is None and s.get_meta("review_file") == fresh
open(os.path.join(src_root, "rudeness_entries.jsonl"), "w").write("")
open(fresh, "w").write("")
cmds = app.make_review_words(d.dlg, run=lambda c, cwd: (1, "MemoryError"))
assert [c[1:] for c in cmds] == [[mr, "next", "--review", fresh]]   # (entries there, a review file: 300 more)
pump(3)
assert app._tool_job is None
before = app.open_review(fresh)                                     # (an open review: opened again on the new words)
app.make_review_words(None, run=lambda c, cwd: (0, "300 new words to review"))
pump(3)
assert app.review is not None and app.review is not before and app.review.alive() and not before.alive()
app.review.close()
d = app.edit_dealing(); pump(3)
started = []
assert app.tune_rules(d.dlg, start=started.append) is None and shown[-1][1] == "Nothing answered yet"
open(review_answers_path(fresh), "w").write("")
cmd = app.tune_rules(d.dlg, start=started.append)
assert started == [cmd] and cmd[1:] == [os.path.join(src_root, "tools", "tune_rudeness.py"), "--review", fresh,
                                        "--entries", os.path.join(src_root, "rudeness_entries.jsonl")]
assert not d.dlg.alive()                                             # (the tuner is a window of its own)

# ---- the rings: a running tool's progress, read by its bubble (asked for, picked from a mock-up) -------------------
import threading
assert app.dev_progress("review words") is None and app.dev_progress("tune") is None


class FakeTuner:                   # (prints its rounds on a pipe the test writes into)
    def __init__(self):
        self.lines, self.more, self.code = [], threading.Event(), None
        self.stdout = self

    def __iter__(self):
        while True:
            self.more.wait(5)
            self.more.clear()
            while self.lines:
                line = self.lines.pop(0)
                if line is None:
                    return
                yield line

    def say(self, line):
        self.lines.append(line); self.more.set(); time.sleep(0.05)

    def poll(self):
        return self.code


tuner = FakeTuner()
d = app.edit_dealing(); pump(3)
ring = d.bubbles["Tune the rules"]
assert not ring.running() and ring.progress is not None and d.bubbles["Score the rules"].progress is None
assert app.tune_rules(d.dlg, start=lambda c: tuner) and app.dev_progress("tune") == (0.0, "The tuner is reading "
                                                                                       "Wiktionary's entries")
d = app.edit_dealing(); pump(3)                                     # (opened while it runs: it shows at once)
ring = d.bubbles["Tune the rules"]
tuner.say("Round 3 of up to 12\n")
assert app.dev_progress("tune") == (0.25, "Round 3 of up to 12")
for _ in range(30):
    pump(1)
assert ring.running() and ring.lit() and ring.state == (0.25, "Round 3 of up to 12")
assert abs(ring._shown - 0.25) < 0.01, ring._shown                  # (eased there)
calls = []
ring.command = lambda: calls.append(1)
ring.invoke(); assert not calls                                     # (a click on a running tool does nothing)
assert app.tune_rules(d.dlg, start=lambda c: calls.append(c)) is None and not calls    # (one tuner at a time)
tuner.say("Done\n")
assert app.dev_progress("tune") is None
pump(4)
assert not ring.running() and ring._blink                           # (the whole ring blinks once)
for _ in range(40):
    pump(1)
assert not ring._blink and not ring.lit()
ring.invoke(); assert calls == [1]                                  # (plain again: a click runs it)
tuner.lines.append(None); tuner.more.set()
# Make review words: no fraction (an arc goes round), its last line in the hover note
app._tool_job = None
job = {"done": None, "path": fresh, "note": "Step 1 of 2: 400,000 entries read"}
app._tool_job = job
assert app.dev_progress("review words") == (None, "Step 1 of 2: 400,000 entries read")
mk = d.bubbles["Make review words"]
pump(6)
assert mk.running() and mk.state[0] is None
spin = mk._spin; pump(4); assert mk._spin == spin                   # (reduce motion: it stays still)
app.anim.reduce_motion = False
pump(4); spin = mk._spin; pump(4); assert mk._spin != spin          # (the arc turns)
app.anim.reduce_motion = True
job["done"] = (0, "300 new words to review"); app._watch_tool(job)
assert app.dev_progress("review words") is None
d.dlg.close()

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
app.crash_test(d.dlg, delay=10)
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
# Keyboard shortcuts lists the review's keys only while the review is open, not for Developer tools alone (F-48:
# the long card made the three stack on a narrower screen)
import keymap
assert "review" in keymap.DEV_GROUPS
app.dev_var.set(True); app.toggle_dev()
assert app.dev_tools and getattr(app, "review", None) is None
k = app.edit_keys(); root.update()
assert "review_clean" not in k.rows and "left" in k.rows
k.dlg.close(); root.update()
root.destroy()
print("devtools self-test passed")
