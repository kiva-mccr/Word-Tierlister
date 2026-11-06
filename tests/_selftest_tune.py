import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""The rule tuner (OB-10: tools/tune_rudeness.py): fast scoring gives the rules' own results, the search lowers the
error on made-up answers, the parts never test a word on numbers tuned with it, Keep writes the numbers into a copy
of rudeness.py (read back, version bumped), and the window draws every part and asks before a kind doubles."""
import json, os, queue, shutil, sys, tempfile, time
os.environ["HOME"] = tempfile.mkdtemp()
os.environ["USERPROFILE"] = os.environ["HOME"]
sys.path.insert(0, os.path.join(_paths.ROOT, "tools"))
import rudeness
import tune_rudeness as T

folder = tempfile.mkdtemp()


def sense(gloss, tags=(), topics=(), syns=(), pos="noun"):
    return {"g": gloss, **({"t": list(tags)} if tags else {}), **({"p": list(topics)} if topics else {}),
            **({"s": list(syns)} if syns else {}), "pos": pos}


# made-up words: offensive rascals answered Expletive (the rules find them clean: a label alone is a suspect), rude ones
ENTRIES = {
    **{f"mean{i}": [sense(f"A {p} rascal.", tags=["offensive"])]
       for i, p in enumerate(["liver", "kidney", "lung", "skin", "eye", "ear", "bone", "blood", "heart", "gut"] * 3)},
    **{f"rude{i}": [sense("Sexual intercourse.", tags=["vulgar", "slang"]), sense("A tool.")] for i in range(20)},
    **{f"dolt{i}": [sense("A stupid person.", tags=["derogatory"])] for i in range(20)},
    **{f"word{i}": [sense("A thing that is used for work.")] for i in range(30)},
    "bonk": [sense("To hit.", syns=["rude1"]), sense("To have sex with.", tags=["slang"], syns=["rude2", "rude3"])],
}
entries = os.path.join(folder, "entries.jsonl")
with open(entries, "w", encoding="utf-8") as f:
    for w, cs in ENTRIES.items():
        f.write(json.dumps({"w": w, "senses": cs}) + "\n")


def key(c):
    return c["g"][:rudeness.GLOSS_KEY]


answers = {}
for w, cs in ENTRIES.items():
    kinds = {key(cs[0]): ("expletive" if w.startswith("mean") else "sexual" if w.startswith("rude") else "clean")}
    answers[w] = {"kinds": kinds, "whole": w.startswith("rude")}
answers["ghost"] = {"kinds": {"x": "clean"}, "whole": False}          # (a word not in the entries: left out)

data, saved = T.prepare(entries, answers, wn=None, log=lambda *a: None)
assert "ghost" not in data["answers"] and len(data["answers"]) == len(ENTRIES)
assert "rude2" in data["words"]                                       # (bonk's synonyms are scored too)
assert set(saved) >= {"rude1", "dolt1", "mean1"} and "word1" not in saved   # (the program's words: a sign of rudeness)
assert len(T.params()) == len(set(T.params())) > 30
assert "TOPIC_POINTS * clinical" in T.params() and "TAG_POINTS vulgar swear" in T.params()

# fast scoring = the rules' own scoring, whatever the numbers
targets = sorted(data["answers"])
plain = {w: rudeness.score_words({w: data["words"][w] for w in data["words"]}, data["poses"], None,
                                 dict(data["family"]))[w] for w in targets}
start = dict(data["start"])
with T.fast(data["wn_matches"], data["wn_names"], data["words"], data["poses"]):
    assert T.score_targets(data, targets) == plain
    odd = {p: v * 1.7 for p, v in start.items()}
    T.apply(odd, data["base"])
    fast_odd = T.score_targets(data, targets)
with T.fast(data["wn_matches"], data["wn_names"], data["words"], data["poses"], data):     # (and remembering points)
    for vals in (odd, start, {**start, "TAG_POINTS vulgar sexual": 0.0}, odd):
        T.apply(vals, data["base"])
        mem = T.score_targets(data, targets)
        T.apply(vals, data["base"])
    assert mem == fast_odd
T.apply(odd, data["base"])
slow_odd = rudeness.score_words(data["words"], data["poses"], None, dict(data["family"]))
assert all(fast_odd[w] == slow_odd[w] for w in targets)
T.apply(start, data["base"])
assert rudeness.TOPIC_POINTS["medicine"]["clinical"] == 0.5 and rudeness.MEANING_MIN == 3.0     # (put back)
assert rudeness.sense_kind.__module__ == "rudeness" and not isinstance(rudeness.WORDING[0][0], T._Memo)

# the error: 100% minus the average F1; the rules start wrong on the offensive rascals
err, t = T.evaluate(data, start, targets)
assert t["expletive"][2] == 30 and t["expletive"][0] == 0 and 0 < err < 100
assert T.error({"clean": [5, 0, 0], "sexual": [0, 0, 0]}) == 0.0      # (a class never answered is left out)
assert abs(T.error({"clean": [1, 1, 0]}) - 100 / 3) < 1e-9
assert {T.part_of(w) for w in targets} == set(range(T.PARTS))

# the search, in this process: the error falls, every event arrives, Keep's numbers come from all the words
events = queue.Queue()
tu = T.Tuning(data, saved, events, rounds=6, workers=0, misses_path=os.path.join(folder, T.MISSES_FILE))
tu.run()
got = []
while not events.empty():
    got.append(events.get())
names = [e[0] for e in got]
assert "error" not in names, [e for e in got if e[0] == "error"]
sweeps = [e[1] for e in got if e[0] == "sweep"]                       # (a round's results in one event: asked for)
assert set(names) <= {"begin", "part", "step", "sweep", "done"}, set(names)
assert sweeps[0]["round"] == 0 and set(sweeps[1]["errors"]) == set(range(T.PARTS + 1))
assert sweeps[0]["errors"][0][1] is not None and sweeps[0]["tally"][0] == "now" and "misses" in sweeps[0]
assert sweeps[1]["errors"][T.ALL][1] is None                          # (the run on every word has no test)
assert tu.best[0] > 0 and tu.best[1] < sweeps[0]["average"], (tu.best[:2], sweeps[0]["average"])
assert any(sw.get("tally", ("",))[0] == "best" for sw in sweeps)
assert all(sw["wait"][1] == T.patience(sw["noise"]) for sw in sweeps)
assert names[-1] == "done"
moved = dict((p, (a, b)) for p, a, b in T.changed(tu.start_values, tu.best[2]))
assert moved, "nothing moved"
assert rudeness.MEANING_MIN == 3.0 and not isinstance(rudeness.GROUP[0], T._Memo)    # (the rules left as they were)
miss = [sw["misses"] for sw in sweeps if "misses" in sw][-1]
with open(os.path.join(folder, T.MISSES_FILE), encoding="utf-8") as f:
    assert len(f.read().strip().splitlines()) == len(miss) + 1
for p, (lo, hi) in data["bounds"].items():
    assert lo <= tu.best[2][p] <= hi, p

# the helper processes are spawned, never forked (reported: started by the program, a fork hung at round 0 for good:
# the stdin listener held sys.stdin's lock while the fork's start-up closed sys.stdin)
for ex in (T.pool(data, 1), T.pool_for_guard(saved, 1)):
    assert ex._mp_context.get_start_method() == "spawn"
    ex.shutdown(wait=False)

# pause and stop between rounds
events = queue.Queue()
tu2 = T.Tuning(data, saved, events, rounds=50, workers=0)
tu2.pause()
import threading
th = threading.Thread(target=tu2.run, daemon=True)
th.start()
time.sleep(1.5)
assert tu2.round == 0
tu2.stop()
th.join(10)
assert not th.is_alive() and tu2.round == 0

# a few answers leave some parts empty: only the parts with words are tested and averaged (it once added None)
few = {w: answers[w] for w in ("rude1", "mean2", "word3")}
d_few, s_few = T.prepare(entries, few, wn=None, log=lambda *a: None)
assert len(T.tested_parts(d_few)) < T.PARTS
events = queue.Queue()
T.Tuning(d_few, s_few, events, rounds=2, workers=0).run()
got = [events.get() for _ in range(events.qsize())]
assert "error" not in [e[0] for e in got], [e for e in got if e[0] == "error"]
assert all(set(e[1]["errors"]) <= set(T.tested_parts(d_few)) | {T.ALL} for e in got if e[0] == "sweep")
assert all(v is not None for e in got if e[0] == "sweep" for p, (_tr, v) in e[1]["errors"].items() if p != T.ALL)

# the noise: the parts' standard error; the stop waits longer the noisier the average (asked for)
assert T.noise([20.0]) == 0.0 and abs(T.noise([18.0, 22.0]) - 2.0) < 1e-9
assert T.patience(0.0) == T.PATIENCE and T.patience(0.5) == T.PATIENCE + 1 and T.patience(1.2) == T.PATIENCE + 3
assert T.patience(99) == T.PATIENCE_MAX
# Keep's round: the earliest within the noise of the lowest (asked for), not a win by wobble
hist = [(0, {}, 24.0, 1.0, None), (1, {}, 20.5, 1.0, None), (2, {}, 19.5, 1.0, None), (3, {}, 19.2, 1.0, None)]
assert T.best_round(hist) == 2
assert T.best_round(hist[:2]) == 1 and T.best_round([(0, {}, 5.0, 0.0, None), (1, {}, 5.0, 0.0, None)]) == 0

# the guard: what the program's words would show
g_now = T.guard(saved, start, data["base"])
assert g_now["whole"] == 20 and g_now["sexual"] >= 20, g_now
assert T.doubled({"whole": 10, "slur": 0}, {"whole": 25, "slur": 12}) == ["whole", "slur"]
assert T.doubled({"whole": 10, "slur": 0}, {"whole": 19, "slur": 9}) == []

# Keep: the numbers written into a copy of rudeness.py, comments kept, read back exactly; the version bumped
src = os.path.join(folder, "rudeness.py")
shutil.copy(os.path.join(_paths.ROOT, "src", "rudeness.py"), src)
before = open(src, encoding="utf-8").read()
values = dict(start, **{"MEANING_MIN": 2.6, "TAG_POINTS vulgar swear": 4.25, "TOPIC_POINTS * clinical": 1.5,
                        "WORDING * insult": 0.5, "WORDNET_POINTS * slur": 2.0, "GROUP_POINTS slur": 5.5,
                        "OTHERS_WEIGHT": 0.42})
text = T.write_back(src, values, data["base"])
space = {}
exec(compile(text, src, "exec"), space)
assert space["MEANING_MIN"] == 2.6 and space["TAG_POINTS"]["vulgar"]["swear"] == 4.25
assert space["TAG_POINTS"]["vulgar"]["sexual"] == rudeness.TAG_POINTS["vulgar"]["sexual"]
assert space["TOPIC_POINTS"]["medicine"]["clinical"] == 0.75 and space["TOPIC_POINTS"]["medicine"].keys() == \
    rudeness.TOPIC_POINTS["medicine"].keys()
assert space["TOPIC_POINTS"]["sex"]["sexual"] == rudeness.TOPIC_POINTS["sex"]["sexual"]
assert space["WORDNET_POINTS"]["ethnic_slur.n.01"]["slur"] == 10
assert space["GROUP_POINTS"]["slur"] == 5.5 and space["OTHERS_WEIGHT"] == 0.42
assert [p.pattern for p, _t in space["WORDING"]] == [p.pattern for p, _t in rudeness.WORDING]
assert int(space["RUDENESS_VERSION"]) == int(rudeness.RUDENESS_VERSION) + 1
assert "# points for a meaning to count as rude" in text and text.count("\n") == before.count("\n")
try:
    T.check(text, dict(values, MEANING_MIN=9.0), data["base"])
    raise AssertionError("check passed a wrong number")
except ValueError:
    pass
assert T._num(3.0) == "3.0" and T._num(0.35) == "0.35" and T._num(2.499) == "2.5" and T._num(4.0001) == "4.0"
print("tune core passed", flush=True)

# the window: every line drawn and named, the guard marked, Keep asks first and writes
import tkinter as tk
from fonts import init_fonts
import errors
root = tk.Tk()
init_fonts(root)
shutil.copy(os.path.join(_paths.ROOT, "src", "rudeness.py"), src)
win = T.TuneWindow(root, os.path.join(folder, "answers.jsonl"), 6, src)


def pump(n=5):
    for _ in range(n):
        root.update()
        time.sleep(0.02)


pump()
assert "Reading" in win.info.cget("text") and not win.keep_btn.enabled
opened = root.winfo_width(), root.winfo_height()
# every row there from the start, empty (asked for): the kinds, the guard's names, the misses' rows
assert set(win.kind_cells) == {k for k, _n in T.GUARD_NAMES} and len(win.miss_cells) == T.SHOWN_MISSES
assert all(a.cget("text") == T.TuneWindow.BLANK for a, _b in win.kind_cells.values())
assert len(win.change_cells) == T.SHOWN_CHANGES and win.guard_cells["whole"].cget("text") == T.TuneWindow.BLANK
# the bar while the entries are read: moving until a share is known, then the share and (in time) the time left
assert str(win.bar.cget("mode")) == "indeterminate" and win.bar_text.cget("text").startswith(T.READING)
win.events.put(("progress", T.READING, 0.1)); pump(10)
assert str(win.bar.cget("mode")) == "determinate" and float(win.bar.cget("value")) == 10.0
assert "10%" in win.bar_text.cget("text"), win.bar_text.cget("text")
win.eta.samples = [(time.time() - 10, 0.0), (time.time() - 5, 5.0), (time.time(), 10.0)]
win.events.put(("progress", T.READING, 0.12)); pump(10)
assert " left" in win.bar_text.cget("text"), win.bar_text.cget("text")
win.events.put(("progress", T.MATCHING, None)); pump(10)
assert str(win.bar.cget("mode")) == "indeterminate" and win.bar_text.cget("text").startswith(T.MATCHING)
# a round's bar: each part's numbers tried (6 jobs, 3 of them halfway: a quarter), then the time left
win.events.put(("begin", 3, 6))
for part in range(3):
    win.events.put(("step", 3, part, 10, 20))
win.events.put(("step", 2, 4, 20, 20))                            # (a late step of the round before: left out)
pump(10)
assert str(win.bar.cget("mode")) == "determinate" and abs(float(win.bar.cget("value")) - 25) < 1e-6
assert win.bar_text.cget("text").startswith("Round 3 of up to 6: 25%"), win.bar_text.cget("text")
win.round_eta.samples = [(time.time() - 10, 5.0), (time.time() - 5, 15.0), (time.time(), 25.0)]
win.show_bar()
assert "in this round" in win.bar_text.cget("text"), win.bar_text.cget("text")
# started by the program's bubble (--from-program): the close box only hides it while it tunes; "show" brings it back,
# and it comes back by itself when it is done (asked for)
import io
win.from_program = True
win.close_box(); pump()
assert win.hidden and root.state() == "withdrawn" and not win.closed
win.listen(io.StringIO("show\n")); pump(20)                     # (then the stream ends: nothing while it shows)
assert not win.hidden and root.state() == "normal" and not win.closed
win.close_box(); pump()
assert win.hidden
win.events.put(("ready", data, saved, 0, 0))
for _ in range(400):
    pump(1)
    if win.done and "best" in win.guards and win.guards.get("best") is not None:
        break
assert win.done and win.best_round and "Your answers: " in win.info.cget("text")
assert not win.hidden and root.state() == "normal"                # (done while hidden: back, for Keep)
assert (root.winfo_width(), root.winfo_height()) == opened, (opened, root.winfo_width(), root.winfo_height())
assert win.wait and win.noise and "Noise ±" in win.note.cget("text")
assert win.span() == 6                                          # (the rounds axis: never past the rounds it may run)
assert win.kinds_box.winfo_manager() == "pack" and win.guard_box.master is win.kinds_box.master   # (side by side)
texts = [win.chart.itemcget(i, "text") for i in win.chart.find_all() if win.chart.type(i) == "text"]
assert any(t.startswith("error: the average of the 5 parts") for t in texts)
assert any(t.startswith("each part, tested") for t in texts) and "the rules as they are now" in texts
assert "error (lower is better)" in texts                         # (the vertical axis, asked for)


def no_overlap():
    """The axis's name clear of its numbers, the numbers clear of the plot, the round numbers clear of "round"."""
    c = win.chart
    items = {i: c.itemcget(i, "text") for i in c.find_all() if c.type(i) == "text"}
    name = [i for i, t in items.items() if t == "error (lower is better)"][0]
    nums = [i for i, t in items.items() if t.endswith("%") and t[:-1].isdigit()]
    assert all(c.bbox(name)[2] <= c.bbox(i)[0] for i in nums), (c.bbox(name), [c.bbox(i) for i in nums])
    rnd = [i for i, t in items.items() if t == "round"][0]
    ticks = [i for i, t in items.items() if t.isdigit()]
    assert all(c.bbox(i)[3] <= c.bbox(rnd)[1] + 1 for i in ticks)


no_overlap()
import fonts as _fonts
small_font = _fonts.font("small")
small_size = small_font.cget("size")
small_font.configure(size=int(small_size * 1.6) if small_size > 0 else int(small_size * 1.6))   # (a bigger text size)
win.draw(); pump(5)
no_overlap()                                                      # (reported: they overlapped at the user's size)
small_font.configure(size=small_size)
win.draw(); pump(5)
legend = [i for i in win.chart.find_all() if win.chart.type(i) == "text" and
          win.chart.itemcget(i, "text") == "the rules as they are now"][0]
zero = [i for i in win.chart.find_all() if win.chart.type(i) == "text" and win.chart.itemcget(i, "text") == "0%"][0]
assert win.chart.coords(legend)[1] > win.chart.coords(zero)[1] + 30   # (the legend under the plot, not over it)
assert win.bar_text.cget("text") == "Done" and float(win.bar.cget("value")) == 100
# the chart grows with the window
size0, win0 = (win.chart.winfo_width(), win.chart.winfo_height()), (root.winfo_width(), root.winfo_height())
root.geometry(f"{root.winfo_width() + 200}x{root.winfo_height() + 120}"); pump(30)
time.sleep(0.1); pump(10)
after = win.chart.winfo_width(), win.chart.winfo_height()
grew = root.winfo_width() - win0[0], root.winfo_height() - win0[1]   # (a small screen can stop the window growing)
assert grew[0] >= 150 and after[0] - size0[0] >= grew[0] - 2 and after[1] - size0[1] >= grew[1] - 2, \
    (size0, after, grew)
right = max(win.chart.coords(i)[0] for i in win.chart.find_all() if win.chart.type(i) == "text"
            and win.chart.itemcget(i, "text").startswith("average "))
assert right > size0[0], (right, size0)                         # (drawn again at the new size)
assert any(t.startswith("now ") for t in texts) and any(t.startswith("average ") for t in texts)
assert f"best: round {win.best_round}" in texts
lines = [i for i in win.chart.find_all() if win.chart.type(i) == "line" and len(win.chart.coords(i)) > 4]
assert len(lines) >= T.PARTS + 1
assert "Best at round" in win.note.cget("text")
kinds_text = [w.cget("text") for w in win.kinds_box.winfo_children()]
assert "Expletive" in kinds_text and "Smeared whole" in kinds_text and "→" in kinds_text
assert any(w.cget("text").startswith("Numbers changed") for w in win.changes_box.winfo_children())
guard_text = " ".join(w.cget("text") for w in win.guard_box.winfo_children())
assert "with the best numbers" in guard_text and "Smeared whole" in guard_text
asked, told = [], []
errors_ask, errors_show = errors.ask_yes_no, errors.show_message
errors.ask_yes_no = lambda *a, **k: asked.append(a) or False
errors.show_message = lambda *a, **k: told.append(a)
win.guards["best"] = dict(win.guards["now"], slur=win.guards["now"]["slur"] * 3 + 30)
win.draw_guard()
assert "check" in " ".join(w.cget("text") for w in win.guard_box.winfo_children())
win.keep()
assert asked and open(src, encoding="utf-8").read() == before     # (asked, and No: nothing written)
errors.ask_yes_no = lambda *a, **k: True
win.keep()
assert told and told[-1][1] == "Written into src/rudeness.py"
assert open(src, encoding="utf-8").read() != before
errors.ask_yes_no, errors.show_message = errors_ask, errors_show
assert win.closed
# hidden, then the program closes (its end of the pipe): a tuner out of reach stops
root = tk.Tk(); init_fonts(root)
w2 = T.TuneWindow(root, os.path.join(folder, "answers.jsonl"), 6, src)
w2.from_program = True
w2.close_box(); w2.listen(io.StringIO(""))
for _ in range(40):
    try:
        root.update()
    except tk.TclError:
        break
    time.sleep(0.02)
assert w2.closed
print("tune self-test passed")
