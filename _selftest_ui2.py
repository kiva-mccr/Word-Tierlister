import os, sys, tempfile, time, types
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
T.messagebox.askyesno = lambda title, msg, **k: (asked.append((title, msg)), answer["yes"])[1]
T.messagebox.showinfo = lambda title, msg, **k: shown.append((title, msg))
T.messagebox.showerror = lambda title, msg, **k: errors.append((title, msg))
store = T.Store(path)
app = T.App(root, store, T.Definitions(store), note="Resumed your earlier tier list from X", other_saves=others)


def pump(n=8, d=0.05):
    for _ in range(n):
        root.update(); time.sleep(d)


assert store.path in root.title()
# --- startup: the note shows, and the merge offer is asked once (answered "no" here)
pump(12)
assert asked and "tierlist.db" in asked[0][1] and "306 placed" in asked[0][1], asked
assert app.banner.cget("text").startswith("Not merged") or "Resumed" in app.banner.cget("text")
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
# --- File > Import earlier progress with an exported list
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
bw.close()
app.on_close()
print("UI2 OK")
