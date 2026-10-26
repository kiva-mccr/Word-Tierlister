import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import os, sys, tempfile, time
tmp = tempfile.mkdtemp()
HOME = os.path.join(tmp, "home"); os.makedirs(HOME)
os.environ["HOME"] = HOME
import tkinter as tk
import tierlist as T

WORDS = [f"w{i:05d}" for i in range(2000)]
ANCH = ["w01990", "w01991", "w01992", "w01993", "w01994", "w01995"]


def make_save(path, n, tier_shift=0):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    s = T.Store(path)
    s.insert_words(WORDS)
    s.set_anchors(ANCH)
    s.reshuffle(seed=3)
    for i in range(n):
        s.place(WORDS[i], (i + tier_shift) % 6)
    s.skip("w01500")
    s.close()
    return path


script = os.path.join(tmp, "script"); os.makedirs(script)
old = make_save(os.path.join(HOME, "Documents", "tierlist", "tierlist.db"), 300)
cur_path = make_save(os.path.join(script, "tierlist.db"), 20, tier_shift=2)
T.remember_save(cur_path)
path, best, others = T.choose_save(script)
assert os.path.realpath(path) == os.path.realpath(cur_path) and len(others) == 1   # pointer wins; the old save is offered

root = tk.Tk()
asked, shown, errors = [], [], []
answer = {"yes": False}
import app as A
A.ask_yes_no = lambda title, headline, msg, **k: (asked.append((title, msg)), answer["yes"])[1]
A.show_message = lambda title, headline, msg, **k: shown.append((title, msg))
A.show_error = lambda title, msg, **k: errors.append((title, msg))
store = T.Store(path)
app = T.App(root, store, T.Definitions(store), note="Resumed your earlier tier list from X", other_saves=others)


def pump(n=8, d=0.05):
    for _ in range(n):
        root.update(); time.sleep(d)


assert store.path in root.title()
# --- startup: the note shows, and the merge offer is asked once (answered "no" here)
pump(12)
assert asked and "tierlist.db" in asked[0][1] and "306 placed" in asked[0][1], asked
assert app.toast.cget("text").startswith("Not merged") or "Resumed" in app.toast.cget("text")
assert store.stats()["placed"] == 26
n_asked = len(asked)
app.offer_merge(others)                                   # already answered: it must not ask again
assert len(asked) == n_asked
# --- answer "yes" (reset the memory of the question)
store.set_meta("merge_prompted", "[]")
answer["yes"] = True
app.offer_merge(others)
pump(3)
assert store.stats()["placed"] == 26 + 280 and "Brought over 280 words placed" in shown[-1][1], shown[-1]
assert "were in a different tier here" in shown[-1][1] and "backup" in shown[-1][1].lower()
assert app.cur_word and store.get_word(app.cur_word)["tier"] is None   # the screen moved on to an unplaced word
# --- File > Import earlier progress with an exported list (the system dialog's path: Windows and macOS; the
#     app's own picker, used on Linux, has its own test in _selftest_filepicker.py)
import app as A
A.use_themed = lambda root: False
exp = os.path.join(tmp, "mine.txt")
other_store = T.Store(os.path.join(tmp, "elsewhere.db"))
other_store.insert_words(WORDS); other_store.place("w01000", 1); other_store.place("w01001", 0)
T.write_export(exp, other_store.export_rows(), [])
T.filedialog.askopenfilename = lambda **k: exp
app.import_progress()
pump(3)
assert store.get_word("w01000")["tier"] == 1 and store.get_word("w01001")["tier"] == 0
assert "Brought over 2 words placed" in shown[-1][1]
# --- importing garbage or the current file reports an error instead of crashing
T.filedialog.askopenfilename = lambda **k: cur_path
app.import_progress()
assert errors and "already using" in errors[-1][1], errors
bad = os.path.join(tmp, "bad.db")
import sqlite3
c = sqlite3.connect(bad); c.execute("CREATE TABLE t(x)"); c.commit(); c.close()
T.filedialog.askopenfilename = lambda **k: bad
app.import_progress()
assert "could not import" in errors[-1][1]
T.filedialog.askopenfilename = lambda **k: ""
app.import_progress()                                      # cancelled dialog: nothing happens
# --- save location info + export via the menu code path
app.show_save_location()
assert store.path in shown[-1][1]
T.filedialog.asksaveasfilename = lambda **k: os.path.join(tmp, "out.csv")
app.export()
assert os.path.getsize(os.path.join(tmp, "out.csv")) > 100
# --- the browse window still works on the merged list
app.open_browser(); pump(6)
bw = app.browsers[0]
assert bw.total == store.stats()["placed"]
# UI-39: Delete unplaces the selected word (like the Unplace button); Ctrl+Z in Browse puts it back
victim = next(i for i in bw.tree.get_children() if i not in store.get_anchors())
tier_before = store.get_word(victim)["tier"]
bw.tree.selection_set(victim); bw.tree.focus_set(); pump(2)
bw.tree.event_generate("<Delete>"); pump(2)
assert store.get_word(victim)["tier"] is None and victim not in bw.tree.get_children()
bw.win.event_generate("<Control-z>"); pump(2)
assert store.get_word(victim)["tier"] == tier_before and victim in bw.tree.get_children()
bw.entry.focus_set(); bw.entry.insert(0, "x"); pump(1)                   # typing in the search box: Delete edits it
n_placed = store.stats()["placed"]
bw.entry.icursor(0); bw.entry.event_generate("<Delete>"); pump(2)
assert store.stats()["placed"] == n_placed
# UI-38: closing remembers what you were looking at; the next open starts there
bw.search_var.set(victim[:3]); bw.filter_var.set("All placed"); pump(8)
bw.reload(); pump(2); bw.tree.selection_set(victim); pump(2)
bw.close(); pump(2)
app.open_browser(); pump(8)
bw = app.browsers[0]
assert bw.search_var.get() == victim[:3] and bw.tree.selection() == (victim,) and bw.current == victim
# a click on a pill or the card does not close it; a click on the bare background does
app.tier_btns[0].event_generate("<ButtonPress-1>", x=1, y=1); app.tier_btns[0].event_generate("<ButtonRelease-1>",
                                                                                              x=-50, y=-50)
app.tier_row.event_generate("<ButtonPress-1>", x=1, y=1); pump(2)
assert bw.alive() and app.browsers == [bw]
app.center.event_generate("<ButtonPress-1>", x=2, y=2); pump(2)
assert not bw.alive() and not app.browsers
app.browse_state = None
import browser as _B
# it opens complete (its rows in) and in its place, like every other window: no growing, nothing moves, no fade of
# its own (reported: a bounce on Linux and Windows; then, faded, it opened unlike the other windows)
mapped = []
real_init = _B.Browser._open
def spy(self):
    self.win.bind("<Map>", lambda e, w=self.win: e.widget is w and mapped.append(
        (w.winfo_width(), w.winfo_height(), len(self.tree.get_children()), self.fsize)), add="+")
    real_init(self)
_B.Browser._open = spy
app.open_browser(); bw = app.browsers[0]
geos = set()
for _ in range(12):
    pump(1); geos.add(bw.win.geometry())
assert mapped and mapped[0][2] > 0, mapped                        # rows already in when it first shows
assert len(geos) == 1, geos                                       # never resized or moved while opening
assert mapped[0][3] == bw.fsize                                   # its text size already final when it first shows
assert float(bw.win.attributes("-alpha")) == 1.0 and bw.search_var.get() == ""   # never see-through
w_full = bw.win.winfo_width()
bw.close()
_B.Browser._open = real_init
app.anim.reduce_motion = True                                    # Reduce motion: the same
app.open_browser(); bw = app.browsers[0]
assert bw.tree.get_children()
pump(4); assert abs(bw.win.winfo_width() - w_full) <= 2
bw.close()
app.anim.reduce_motion = False
# M-7: a click on a column heading sorts by it (the Sort drop-down follows); again, the other way round
app.browse_state = None
app.open_browser(); pump(4); bw = app.browsers[0]
ws = [r["word"] for r in app.store.list_words("", "All placed", limit=6)[0]]
for i in range(2, len(ws)):                                                          # (some words with more duels)
    for _ in range(i):
        app.store.record_comparison(ws[i], ws[1], "a", "within")
bw.reload(); pump(2)
rows = lambda key: [bw.tree.set(i, key) for i in bw.tree.get_children()]
arrow = lambda: bw.arrow[:2]
assert arrow() == ("tier", "down") and bw.tree.heading("tier", "image")              # Tier: S..F, arrow down (asked for)
bw.tree.tk.call(bw.tree.heading("games", "command"))                                # (what a click runs)
root.update(); assert bw.arrow[2] < 1.0 and bw.tree.heading("games", "image")         # rows in; the arrow fills from here
pump(8)                                                                             # ...and is full once loaded
duels = [int(v) for v in rows("games")]
assert bw.sort_var.get() == "Duels" and not bw.reverse and duels == sorted(duels, reverse=True) and duels[0] > 0
assert bw.arrow == ("games", "up", 1.0) and not bw.tree.heading("tier", "image") and bw.tree.heading("tier", "text") == "Tier"
bw.tree.tk.call(bw.tree.heading("games", "command")); pump(8)                       # same heading: turned round
duels = [int(v) for v in rows("games")]
assert bw.reverse and duels == sorted(duels) and arrow() == ("games", "down")
bw.tree.tk.call(bw.tree.heading("word", "command")); pump(8)
assert bw.sort_var.get() == "A-Z" and not bw.reverse and rows("word") == sorted(rows("word"))
assert bw.tree.heading("word", "text").strip() == "Word  (A\u2013Z)" and arrow() == ("word", "down")   # in words too
bw.tree.tk.call(bw.tree.heading("word", "command")); pump(8)
assert rows("word") == sorted(rows("word"), reverse=True) and "(Z\u2013A)" in bw.tree.heading("word", "text")
assert arrow() == ("word", "up")
bw.close(); app.open_browser(); pump(4); bw = app.browsers[0]                       # remembered, either way round
assert bw.sort_var.get() == "A-Z" and bw.reverse and rows("word") == sorted(rows("word"), reverse=True)
assert bw.arrow == ("word", "up", 1.0)                                             # (no fill on opening)
bw.sort_var.set("Rating"); bw.sort_by("Rating"); pump(8)                            # the drop-down: its usual order
assert not bw.reverse and arrow() == ("rating", "up")
bw.close(); app.browse_state = None
app.on_close()

# --- ST-5: File > Add to applications menu (Linux): a launcher that starts the program with no terminal
if sys.platform.startswith("linux"):
    ls = T.Store(os.path.join(tempfile.mkdtemp(), "launch.db")); ls.insert_words(WORDS[:50])
    root = tk.Tk(); app = T.App(root, ls, T.Definitions(ls)); pump(4)
    assert "Add to applications menu" in [it[1] for it in app.header.menus["File"] if len(it) > 1]
    os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp()
    path = app.add_launcher(); pump(2)
    text = open(path).read()
    assert "Terminal=false" in text and "tierlist.py" in text and app.toast.cget("text").startswith("Word Tier List added")
    app.add_launcher(); pump(2); assert app.toast.cget("text") == "Word Tier List updated in your applications menu"
    del os.environ["XDG_DATA_HOME"]
    assert "Add to Start menu" not in [it[1] for it in app.header.menus["File"] if len(it) > 1]   # (Windows only)
    # Windows (asked for): the same item, as File > Add to Start menu (the shortcut itself: _selftest_deps)
    made = []
    import deps as D
    keep = D.add_to_start_menu
    D.add_to_start_menu = lambda python, script: (made.append(script), ("C:\\x\\Word Tier List.lnk", "added"))[1]
    assert app.add_launcher(platform="win32") == "C:\\x\\Word Tier List.lnk" and made[0].endswith("tierlist.py")
    pump(2)
    assert app.toast.cget("text") == "Word Tier List added to your Start menu (it starts without a console window)"
    D.add_to_start_menu = lambda python, script: (_ for _ in ()).throw(OSError("Access is denied."))
    import app as A_mod
    shown = []
    keep_show = A_mod.show_exception
    A_mod.show_exception = lambda title, exc, *a, **k: shown.append((title, str(exc)))
    assert app.add_launcher(platform="win32") is None and shown == [("Start menu", "Access is denied.")]
    A_mod.show_exception, D.add_to_start_menu = keep_show, keep
    app.on_close()

# --- every word placed (UI-20): a friendly card in Place, and no tier buttons
done = T.Store(os.path.join(tempfile.mkdtemp(), "done.db"))
six = ["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist"]
done.insert_words(six); done.set_anchors(six)                     # anchors are placed: nothing left to place
root = tk.Tk(); app = T.App(root, done, T.Definitions(done)); pump(4)
assert app.cur_word is None and app.place_empty.winfo_ismapped() and not app.word_card.winfo_ismapped()
assert app.place_empty.title == "Every word is placed" and not app.tier_row.winfo_ismapped()
app.on_close()
# a saved mode whose tab is hidden falls back to Place new words (UI-46)
fresh = T.Store(os.path.join(tempfile.mkdtemp(), "fresh.db"))
fresh.insert_words(WORDS[:50]); fresh.set_meta("mode", "conflict")
root = tk.Tk(); app = T.App(root, fresh, T.Definitions(fresh)); pump(12)
assert app.mode == "place" and app.mode_switch.visible == {"place"}
app.on_close()
print("UI2 OK")
