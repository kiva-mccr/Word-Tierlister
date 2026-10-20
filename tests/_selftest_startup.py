import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import urllib.parse
import gzip, json, os, subprocess, sys, tempfile, threading, time
import tkinter as tk
import startup as S
import tierlist as T

# ---- pure helpers
assert S.parse_progress("  downloaded 1.20 GB (41%)") == 41
assert S.parse_progress("  downloaded 3.00 GB (100%)") == 100
assert S.parse_progress("  downloaded (250%)") == 100          # clamped
assert S.parse_progress("Reading entries (this takes several minutes)...") is None
assert S.parse_progress("  parsed 200,000 entries, kept 150,000 (12s)") is None
assert S.format_elapsed(7) == "0:07" and S.format_elapsed(723) == "12:03" and S.format_elapsed(0) == "0:00"

root = tk.Tk(); root.withdraw()
from fonts import init_fonts
from ui_style import apply_ttk_style
init_fonts(root); apply_ttk_style(root)                         # exactly what main() does first

# record what the window is told (without caring about pixels)
shown, created = [], []
orig_init, orig_show = S.StartupWindow.__init__, S.StartupWindow.show
def spy_init(self, *a, **k): created.append(1); orig_init(self, *a, **k)
steps_shown = []
def spy_show(self, stage, detail, percent, elapsed, eta=None, step=None):
    shown.append((stage, detail, percent)); steps_shown.append(step)
    orig_show(self, stage, detail, percent, elapsed, eta, step)
S.StartupWindow.__init__, S.StartupWindow.show = spy_init, spy_show

# ---- ETA text and tracker
assert S.format_eta(0) == "a few seconds left" and S.format_eta(9) == "a few seconds left"
assert S.format_eta(10) == "about 10 sec left" and S.format_eta(42) == "about 40 sec left"
assert S.format_eta(59) == "about 60 sec left" or S.format_eta(59) == "about 1 min left"
assert S.format_eta(60) == "about 1 min left" and S.format_eta(361) == "about 6 min left"
assert S.format_eta(3600) == "about 1 hr left" and S.format_eta(3900) == "about 1 hr 5 min left"
assert S.format_eta(-5) == "a few seconds left"

tr = S.EtaTracker()
assert tr.remaining(0) is None
tr.add(1, 0.0)                                   # stand-in reading: ignored
assert tr.remaining(0.5) is None
tr.add(10, 1.0); assert tr.remaining(1.0) is None                      # one real reading is not enough
tr.add(12, 3.0)                                                         # 1 % per second
assert abs(tr.remaining(3.0) - 88.0) < 0.01, tr.remaining(3.0)
assert abs(tr.remaining(8.0) - 83.0) < 0.01                            # counts down between readings
tr.add(13, 4.0); tr.add(14, 5.0)
assert abs(tr.remaining(5.0) - 86 / (4 / 4.0)) < 0.01                  # still 1 %/s over 10..14 -> 4 pts in 4 s
tr.add(14, 6.0)                                                         # same percent: ignored
tr.add(13, 6.5)                                                         # going backwards: ignored
assert len(tr.samples) == 4
assert tr.remaining(100.0) is None                                      # stalled for ages: back to estimating
# resumed download: stand-in 1 % then a jump to 60 % must not look like a huge speed
tr = S.EtaTracker(); tr.add(1, 0.0); tr.add(60, 1.0); tr.add(61, 3.0); tr.add(62, 5.0)
assert abs(tr.remaining(5.0) - 38 / 0.5) < 0.01, tr.remaining(5.0)      # 0.5 %/s -> 76 s
# speed changes are followed: only the last 30 s count
tr = S.EtaTracker(); tr.add(1, 0.0)
for i in range(1, 21): tr.add(i * 2, float(i))                           # fast: 2 %/s for 20 s (to 40 %)
fast = tr.remaining(20.0)
for i in range(1, 61): tr.add(40 + i * 0.5 + 0.5, 20.0 + i * 4)          # then slow: +0.5 point per 4 s
tr3 = S.EtaTracker(); tr3.add(1, 0.0)
for i in range(1, 8): tr3.add(40 + i, 20.0 + i * 4)                      # 0.25 %/s only
slow = tr3.remaining(48.0)
assert slow > fast * 3, (fast, slow)
tr.reset(); assert tr.remaining(0) is None and tr.samples == []
tr.add(50, 0.0); tr.add(60, 1.0); tr.add(70, 4.0)                       # first reading after reset ignored again
assert tr.samples == [(1.0, 60), (4.0, 70)]

# ---- fast work: returns its value, and no window ever appears
assert S.run_with_progress(root, lambda log: (log("quick"), 42)[1]) == 42
assert created == []
assert not [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]

# ---- slow work: window appears, shows stages / details / percent, then goes away
def slow(log):
    log("Downloading English Wiktionary (about 3 GB)...")
    time.sleep(0.15)
    log("  downloaded 1.20 GB (41%)")
    time.sleep(0.15)
    log("Reading entries (this takes several minutes)...")
    log("  parsed 200,000 entries, kept 150,000 (12s)")
    time.sleep(0.25)
    return "built"
assert S.run_with_progress(root, slow, delay_ms=0) == "built"
assert created == [1]
assert not [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)], "window must be destroyed"
stages = [s for s, d, p in shown]
assert any(s.startswith("Downloading") for s in stages) and any(s.startswith("Reading") for s in stages)
assert any(p == 41 for s, d, p in shown), shown               # download percent drives the bar
reading = [x for x in shown if x[0].startswith("Reading")]
assert reading and all(p is None for _, _, p in reading)       # a new stage drops the old percent
assert any("parsed 200,000" in d for _, d, _ in reading)       # detail line shown under the stage

# ---- "Step i of n" (the main steps a job announces up front): retries and notes do not move it
from constants import plan_line, parse_plan
assert parse_plan(plan_line(["Downloading", "Reading"])) == ["Downloading", "Reading"] and parse_plan("Reading") is None
plan = ["Downloading English Wiktionary", "Reading entries", "Ranking words"]
assert S.step_of(plan, "Reading entries...", None) == (2, 3)
assert S.step_of(plan, "Download interrupted; retry 1/5...", (1, 3)) == (1, 3)      # not a main step
assert S.step_of(["Only one"], "Only one...", None) is None                          # one step: nothing to count
shown.clear(); steps_shown.clear()
import io, contextlib
printed = io.StringIO()
def planned(log):
    log(plan_line(plan)); time.sleep(0.25)
    log("Downloading English Wiktionary (about 3 GB)..."); time.sleep(0.25)
    log("Download interrupted (timed out); retry 1/5..."); time.sleep(0.25)
    log("Reading entries..."); time.sleep(0.25)
    return 1
with contextlib.redirect_stdout(printed):
    S.run_with_progress(root, planned, delay_ms=0)
assert "plan:" not in printed.getvalue() and "Reading entries" in printed.getvalue()   # the plan is never printed
by_stage = {st: step for (st, _, _), step in zip(shown, steps_shown)}
assert by_stage["Downloading English Wiktionary (about 3 GB)..."] == (1, 3)
assert by_stage["Download interrupted (timed out); retry 1/5..."] == (1, 3) and by_stage["Reading entries..."] == (2, 3)

# ---- a window that cannot be drawn must not hang or stop the work
def broken_init(self, *a, **k): raise RuntimeError("cannot draw")
S.StartupWindow.__init__ = broken_init
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stderr(buf):
    assert S.run_with_progress(root, lambda log: (log("Stage one"), time.sleep(0.3), "survived")[2], delay_ms=0) == "survived"
assert "progress window unavailable" in buf.getvalue()
S.StartupWindow.__init__ = spy_init

# ---- the window is never empty: starts at "Initializing" with the bar at 1%, bar always visible
shown.clear()
def hold(log): time.sleep(0.5); return 1
S.run_with_progress(root, hold, delay_ms=0, initial_stage="Initializing download...")
assert shown[0] == ("Initializing download...", "", 1), shown[0]

seen = {}
orig_show2 = S.StartupWindow.show
def peek(self, stage, detail, percent, elapsed, eta=None, step=None):
    orig_show2(self, stage, detail, percent, elapsed, eta, step)
    seen["step"] = self.step.cget("text")
    self.win.update_idletasks()
    seen.setdefault("first", (self.bar.winfo_ismapped(), str(self.bar.cget("mode")), float(self.bar["value"]),
                              self.detail.cget("text")))
    seen["last"] = (self.bar.winfo_ismapped(), str(self.bar.cget("mode")), float(self.bar["value"]), self.detail.cget("text"))
S.StartupWindow.show = peek
def stages(log):
    time.sleep(0.3)
    log("Downloading English Wiktionary..."); log("  connecting to the server (1%)"); time.sleep(0.3)
    log("  downloaded 0.50 GB (40%)"); time.sleep(0.3)
    log("Ranking words by frequency..."); time.sleep(0.3)      # no detail yet: stand-in text, bar sweeps
    return 1
S.run_with_progress(root, stages, delay_ms=0)
S.StartupWindow.show = orig_show2
vis, mode, val, det = seen["first"]
assert vis and mode == "determinate" and val == S.BAR_FLOOR and det == "Getting started...", seen["first"]
assert seen["step"] == ""                                          # no plan: no step line
vis, mode, val, det = seen["last"]
assert vis and mode == "indeterminate" and det == "Getting started...", seen["last"]   # bar still there, sweeping

# ---- the window shows "estimating" then a real ETA for a bar with a percentage, none for a sweep
etas = []
orig_show3 = S.StartupWindow.show
def peek_eta(self, stage, detail, percent, elapsed, eta=None, step=None):
    orig_show3(self, stage, detail, percent, elapsed, eta, step)
    etas.append((percent, self.elapsed.cget("text")))
S.StartupWindow.show = peek_eta
def downloading(log):
    log("Downloading English Wiktionary (about 3 GB)...")
    log("  connecting to the server (1%)")
    time.sleep(0.25)
    for p in (10, 12, 14, 16):
        log(f"  downloaded {p / 33:.2f} GB ({p}%)"); time.sleep(1.1)
    log("Ranking words by frequency..."); time.sleep(0.4)
    return 1
S.run_with_progress(root, downloading, delay_ms=0)
S.StartupWindow.show = orig_show3
known = [txt for pct, txt in etas if pct is not None]
assert any("estimating time left" in x for x in known), known         # before it can tell
assert any("min left" in x or "sec left" in x or "hr" in x for x in known), known   # then a real estimate
assert all("left" not in txt for pct, txt in etas if pct is None), etas              # sweep: no ETA

# ---- errors in the work come back to the caller unchanged
def bad(log): raise ValueError("boom")
try: S.run_with_progress(root, bad); raise AssertionError("no error")
except ValueError as e: assert str(e) == "boom"
def bye(log): raise SystemExit("Could not build it")
try: S.run_with_progress(root, bye); raise AssertionError("no exit")
except SystemExit as e: assert str(e) == "Could not build it"

# ---- closing the window mid-way stops cleanly (work finishes in the background, caller exits)
gate, finished = threading.Event(), []
def long(log):
    log("Reading entries..."); gate.wait(5); finished.append(1)
def closer():
    w = [x for x in S.StartupWindow.__dict__ and root.winfo_children() if isinstance(x, tk.Toplevel)]
    assert w, "window should be open"
    w[0].tk.call(w[0].wm_protocol("WM_DELETE_WINDOW"))
root.after(300, closer)
try:
    S.run_with_progress(root, long, delay_ms=0); raise AssertionError("should exit")
except SystemExit as e:
    assert "Run the program again" in str(e), e
gate.set(); time.sleep(0.2)
assert finished == [1]                                          # the worker was not killed mid-write
assert not [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]

# ---- the worker may use the Store, and build_wiktionary reports through log
tmp = tempfile.mkdtemp()
def entry(word, glosses=("a thing",)):
    return {"word": word, "lang_code": "en", "pos": "noun", "senses": [{"glosses": list(glosses)}]}
src = os.path.join(tmp, "s.jsonl.gz")
with gzip.open(src, "wt", encoding="utf-8") as f:
    for w in ["the", "run", "serendipity", "gristle", "moist"]:
        f.write(json.dumps(entry(w)) + "\n")
store = T.Store(os.path.join(tmp, "a.db"))
logged = []
def build(log):
    def tee(t): logged.append(t); log(t)
    n = T.build_wiktionary(store, src, log=tee)
    T.prepare_queue(store, log=tee)
    return n
assert S.run_with_progress(root, build, delay_ms=0) == 5
assert store.count_words() == 5 and store.stats()["total"] == 5
assert any("Word list ready" in t for t in logged)
assert store.next_unplaced() is not None                          # queue keys were assigned
S.StartupWindow.__init__, S.StartupWindow.show = orig_init, orig_show
root.destroy()

# ---- Windows console detach (simulated: the real call only exists on Windows)
class FakeK32:
    def __init__(self, console): self.console, self.freed = console, False
    def GetConsoleWindow(self): return 123 if self.console else 0
    def FreeConsole(self): self.freed = True
class FakeTTY(io.StringIO):
    def isatty(self): return True
saved = sys.stdout, sys.stderr
try:
    logf = os.path.join(tmp, "tierlist.log")
    sys.stdout = sys.stderr = FakeTTY()
    k = FakeK32(True)
    assert S.detach_console(logf, kernel32=k) is True and k.freed
    print("hello from detached")
    sys.stdout.flush()
    assert "hello from detached" in open(logf).read()                 # print() now goes to the log
    sys.stdout.close()
    # no console already (pythonw): nothing to free, but None streams get a log so print() cannot crash
    sys.stdout = sys.stderr = None
    k = FakeK32(False)
    assert S.detach_console(logf, kernel32=k) is False and not k.freed and sys.stdout is not None
    print("pythonw safe"); sys.stdout.flush(); assert "pythonw safe" in open(logf).read()
    sys.stdout.close()
    # redirected on purpose (not a tty): left alone
    sys.stdout = sys.stderr = io.StringIO()
    k = FakeK32(True)
    assert S.detach_console(logf, kernel32=k) is False and not k.freed
finally:
    sys.stdout, sys.stderr = saved
assert S.detach_console(os.path.join(tmp, "x.log")) is False             # not Windows: no-op

# ---- wordsource reports stand-ins and a real parse percentage
import wordsource as W
big = os.path.join(tmp, "big.jsonl")
with open(big, "w", encoding="utf-8") as f:
    for i in range(120000):
        f.write(json.dumps(entry(f"word{chr(97 + i % 26)}{'abcdefghij'[i % 10]}{'klmnopqrst'[(i // 10) % 10]}{'uvwxyzabcd'[(i // 100) % 10]}x")) + "\n")
st2 = T.Store(os.path.join(tmp, "p.db"))
st2.db.execute("CREATE TABLE wk(word TEXT PRIMARY KEY, senses INTEGER, lemma INTEGER, live INTEGER, text TEXT,"
               " kinds INTEGER, marks TEXT)")
lines = []
W._parse_wiktionary(st2.db, big, False, lines.append)
assert lines[0].strip().startswith("opening the file") and S.parse_progress(lines[0]) == 1
pcts = [S.parse_progress(l) for l in lines if "parsed" in l]
assert len([p for p in pcts if p is not None]) >= 2, lines
vals = [p for p in pcts if p is not None]
assert vals == sorted(vals) and 0 < vals[0] < vals[-1] <= 99, vals
gz = os.path.join(tmp, "g.jsonl.gz")
with gzip.open(gz, "wt", encoding="utf-8") as f: f.write(json.dumps(entry("hello")) + "\n")
lines = []; W._parse_wiktionary(st2.db, gz, False, lines.append)
assert S.parse_progress(lines[0]) is None and "opening the file" in lines[0]   # .gz: stand-in, no percent
st3 = T.Store(os.path.join(tmp, "q.db")); lines = []
W.build_wiktionary(st3, src, log=lines.append)
text = "\n".join(lines)
for needle in ("Ranking words by frequency", "loading the word-frequency data", "ordering the words",
               "saving 5 words and their definitions"):
    assert needle in text, needle
st3.set_meta("pen_done", "0"); lines = []
W.prepare_queue(st3, log=lines.append)
text = "\n".join(lines)
assert "checking every word for compounds" in text and "giving every unplaced word" in text, text

# ---- the main steps planned up front ("Step i of n") are exactly the stages a build then reports, in order
st4 = T.Store(os.path.join(tmp, "plan.db"))
plan = W.wiktionary_steps(st4, src) + W.queue_steps(st4, adds_words=True, records_kinds=True)
assert plan == ["Reading entries", "Ranking words", "Detecting compound words", "Looking up how common",
                "Shuffling the queue"], plan                    # (src given: nothing to download)
lines = []
W.build_wiktionary(st4, src, log=lines.append); W.prepare_queue(st4, log=lines.append)
stages = [l for l in lines if l and not l.startswith(" ")]
hits = [next(i for i, st in enumerate(stages) if st.startswith(name)) for name in plan]
assert hits == sorted(hits), (plan, stages)
assert W.queue_steps(st4) == []                                 # all done: a later start has no steps
assert W.wiktionary_steps(T.Store(os.path.join(tmp, "plan2.db")))[0] == "Downloading English Wiktionary"
# a save from before ST-6: its kinds come from the stored definitions, its obscene words from Wiktionary's pages
# of the words it files as rude (faked here): most or the first of their meanings rude; their forms by the save's
# definitions ("plural of bitch")
old = T.Store(os.path.join(tmp, "old.db"))
old.insert_words(["run", "bitch", "bitches", "zorp", "come", "shit", "bureaucracy", "class"])
W._fetch_json = lambda url: (_ for _ in ()).throw(OSError("offline for now"))
W.prepare_queue(old, log=lambda *_: None)
assert old.get_meta("obscene_done") == "list" and old.obscene_words() == {"bitch", "bitches", "shit"}  # (the stand-in)
for k in ("kinds_done", "obscene_done", "obscene_tried", "deal_done"):
    old.db.execute("DELETE FROM meta WHERE key=?", (k,))
old.db.execute("UPDATE words SET kinds=NULL, obscene=0"); old.db.commit()
old.set_def("run", "\u2022 (verb) to move fast\n\u2022 (noun) an act of running"); old.set_def("bitch", "1. (noun) a female dog")
old.set_def("bitches", "\u2022 (noun) plural of bitch\n\u2022 (verb) third-person singular simple present indicative of bitch")
plan = W.queue_steps(old)
assert plan == ["Sorting words into kinds", "Finding obscene words"], plan
CATS = {"English vulgarities": [["bitch", "Bitch", "come"], ["shit", "notinlist"]], "English derogatory terms": [["bureaucracy"]]}
PAGES = {"bitch": "==English==\n# {{lb|en|now|rare}} A female dog.\n# {{lb|en|vulgar|derogatory}} A woman.\n"
                  "# {{lb|en|vulgar|slang}} A complaint.\n",                        # most meanings rude
         "shit": "==English==\n===Noun===\n# {{lb|en|vulgar}} Faeces.\n# Nonsense.\n# Stuff.\n",   # the first one rude
         "come": "==English==\n# To move nearer.\n# To arrive.\n# {{lb|en|vulgar|slang}} To orgasm.\n",
         "bureaucracy": "==English==\n# Government by officials.\n# Officials.\n# {{lb|en|pejorative}} Red tape.\n"}
asked = []
def fake(url):
    asked.append(url)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if "list" in q:                                             # a category, in pages of members
        pages = CATS.get(q["cmtitle"][0][9:], [[]])
        k = int(q.get("cmcontinue", ["0"])[0])
        return {"query": {"categorymembers": [{"title": t} for t in pages[k]]},
                **({"continue": {"cmcontinue": str(k + 1)}} if k + 1 < len(pages) else {})}
    titles = q["titles"][0].split("|")                           # page texts: one per answer, then "continue"
    k = int(q.get("rvcontinue", ["0"])[0])
    page = {"title": titles[k], "revisions": [{"slots": {"main": {"content": PAGES.get(titles[k], "")}}}]}
    return {"query": {"pages": [page]}, **({"continue": {"rvcontinue": str(k + 1)}} if k + 1 < len(titles) else {})}
W._fetch_json = fake
lines = []; W.prepare_queue(old, log=lines.append)
stages = [l for l in lines if l and not l.startswith(" ")]
assert [next(i for i, st in enumerate(stages) if st.startswith(n)) for n in plan] == [0, 1], stages
assert old.get_word("run")["kinds"] == 3 and old.get_word("bitch")["kinds"] == 1 and old.get_word("zorp")["kinds"] == 16
assert old.obscene_words() == {"bitch", "bitches", "shit"}, old.obscene_words()       # not "come", not "bureaucracy"
assert old.get_meta("obscene_done") == old.OBSCENE_VERSION and W.queue_steps(old) == []
assert any("(0%)" in l for l in lines)                          # (a real percentage: the progress window's time left)
# offline later: nothing changes; a save that only had the stand-in list asks again after a while
old.set_meta("obscene_done", "list"); old.set_meta("obscene_tried", time.time())
assert W.queue_steps(old) == []
old.set_meta("obscene_tried", time.time() - W.OBSCENE_RETRY_S - 1)
assert W.queue_steps(old) == ["Finding obscene words"]
# a word added by hand (UI-51) has no meanings to read: the hand-picked list decides
old.add_word("dipshits"); old.add_word("glass")
assert "dipshits" in old.obscene_words() and "glass" not in old.obscene_words()

# ---- main() end to end in a subprocess: first run builds, then the main window opens
words = os.path.join(tmp, "words.txt")
open(words, "w").write("\n".join(["alpha", "beta", "gamma", "delta", "epsilon", "zeta"]) + "\n")
env = dict(os.environ, HOME=tmp)                                # keep the pointer file out of the real home
p = subprocess.Popen([sys.executable, os.path.join(_paths.ROOT, "tierlist.py"), "--db", os.path.join(tmp, "m.db"), "--wordlist", words, "--no-install"],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
time.sleep(5)
alive = p.poll() is None
p.terminate()
out, err = p.communicate(timeout=10)
assert alive, (out, err)                                          # the main window stayed open
assert "6 words ready." in out, (out, err)
assert "Traceback" not in err, err
chk = T.Store(os.path.join(tmp, "m.db")); assert chk.count_words() == 6
print("STARTUP OK")
