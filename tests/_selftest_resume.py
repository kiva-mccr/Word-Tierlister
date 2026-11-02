import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import os, random, sqlite3, tempfile, time

tmp = tempfile.mkdtemp()
HOME = os.path.join(tmp, "home")
os.makedirs(HOME)
os.environ["HOME"] = HOME            # discovery looks in ~/Documents, ~/Downloads ... : keep it inside the sandbox
os.environ["USERPROFILE"] = HOME
import tierlist as T

random.seed(5)
WORDS = [f"w{i:05d}" for i in range(3000)]


def make_save(path, n_placed, skipped=(), tier_shift=0, comps=0):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    s = T.Store(path)
    s.insert_words(WORDS[:1000] if os.path.basename(os.path.dirname(path)) == "old" else WORDS)   # (not just "old"
    # anywhere in the path: macOS's temporary folders are under /var/folders)
    for i in range(n_placed):
        s.place(WORDS[i], (i + tier_shift) % 6)
    for w in skipped:
        s.skip(w)
    for i in range(comps):
        a, b = WORDS[i], WORDS[i + 1]
        s.db.execute("INSERT INTO comparisons(winner, loser, tie, kind, ts) VALUES(?,?,0,'within',?)", (a, b, time.time()))
    s.db.commit()
    s.close()
    return path


# ------------------------------------------------------------------ 1. recognising save files
script = os.path.join(tmp, "script")
os.makedirs(script)
old = make_save(os.path.join(HOME, "Documents", "tierlist", "old", "tierlist.db"), 400, skipped=["w00400", "w00401"], comps=30)
# (the path contains "old" -> 1,000-word list, like an earlier smaller list)
old = os.path.dirname(os.path.dirname(old)) + "/tierlist.db"
os.rename(os.path.join(HOME, "Documents", "tierlist", "old", "tierlist.db"), old)
os.rmdir(os.path.join(HOME, "Documents", "tierlist", "old"))
dl = make_save(os.path.join(HOME, "Downloads", "tierlist (1).db"), 50, tier_shift=3)
stray = make_save(os.path.join(script, "tierlist.db"), 0)
other_sqlite = os.path.join(HOME, "Downloads", "notes.db")
con = sqlite3.connect(other_sqlite); con.execute("CREATE TABLE t(x)"); con.executemany("INSERT INTO t VALUES(?)", [("x" * 100,)] * 400); con.commit(); con.close()
open(os.path.join(HOME, "Downloads", "readme.txt"), "w").write("hello")
open(os.path.join(HOME, "Downloads", "empty.db"), "w").close()

info = T.save_progress(old)
assert info and info["placed"] == 400 and info["skipped"] == 2 and info["progress"] == 402, info
assert T.save_progress(stray)["progress"] == 0
assert T.save_progress(other_sqlite) is None                                   # some other program's database
assert T.save_progress(os.path.join(HOME, "Downloads", "readme.txt")) is None
assert T.save_progress(os.path.join(HOME, "Downloads", "empty.db")) is None
assert T.save_progress(os.path.join(tmp, "does-not-exist.db")) is None
found = {os.path.realpath(p) for p in T.find_saves(script)}
assert {os.path.realpath(p) for p in (old, dl, stray)} <= found, found

# ------------------------------------------------------------------ 2. choosing between them
path, best, others = T.choose_save(script)
assert os.path.realpath(path) == os.path.realpath(old), path                   # real progress beats the stray empty db
assert best["placed"] == 400 and [os.path.realpath(o["path"]) for o in others] == [os.path.realpath(dl)]
T.remember_save(path)
assert open(T._pointer_file()).read() == os.path.abspath(old)
# the remembered file wins even when another has more... (here: point at the smaller Downloads save)
T.remember_save(dl)
path, best, others = T.choose_save(script)
assert os.path.realpath(path) == os.path.realpath(dl) and best["pointer"]
assert [os.path.realpath(o["path"]) for o in others] == [os.path.realpath(old)]
# the pointer file under the program's old name (1.0.2 and older) is read while there is no new one, and goes once
# the new one is written
os.remove(T._pointer_file())
with open(os.path.join(HOME, ".word_tierlist_path"), "w") as f:
    f.write(dl)
path, best, others = T.choose_save(script)
assert os.path.realpath(path) == os.path.realpath(dl) and best["pointer"]
T.remember_save(dl)
assert os.path.exists(T._pointer_file()) and not os.path.exists(os.path.join(HOME, ".word_tierlist_path"))
# ...but a pointer to a file with no progress does not hide a real save
T.remember_save(stray)
path, best, others = T.choose_save(script)
assert os.path.realpath(path) == os.path.realpath(old), path
# pointer to a deleted file is ignored
T.remember_save(os.path.join(tmp, "gone.db"))
assert os.path.realpath(T.choose_save(script)[0]) == os.path.realpath(old)
# only an empty save around: reuse it
os.remove(T._pointer_file())
for p in (old, dl):
    os.remove(p)
    for ext in ("-wal", "-shm"):
        if os.path.exists(p + ext): os.remove(p + ext)
path, best, others = T.choose_save(script)
assert os.path.realpath(path) == os.path.realpath(stray) and not others
# nothing at all: a new default next to the script
os.remove(stray)
for ext in ("-wal", "-shm"):
    if os.path.exists(stray + ext): os.remove(stray + ext)
path, best, others = T.choose_save(script)
assert path == os.path.join(script, "tierlist.db") and best is None and others == []
print("discovery OK")

# ------------------------------------------------------------------ 3. merging another save
old = make_save(os.path.join(tmp, "m", "old", "x.db"), 400, skipped=["w00400", "w00401"], comps=30)
oldstore = T.Store(old)
oldstore.insert_words(WORDS[:1000] + ["oldonly"])
oldstore.place("oldonly", 4)
oldstore.db.execute("INSERT INTO comparisons(winner, loser, tie, kind, ts) VALUES('oldonly','w00001',0,'within',0)")
oldstore.db.commit()
old_ratings = {w: oldstore.get_word(w)["rating"] for w in WORDS[:400]}
oldstore.db.execute("UPDATE words SET rating=rating+7.5 WHERE word='w00100'")
oldstore.db.commit()
old_ratings["w00100"] += 7.5
oldstore.close()
cur_path = make_save(os.path.join(tmp, "m", "new", "tierlist.db"), 50, tier_shift=3)   # w0..w49 placed differently
cur = T.Store(cur_path)
before = {w: cur.get_word(w)["tier"] for w in WORDS[:50]}
res = cur.merge(old)
print(res)
assert res["added"] == 1 and res["skipped"] == 2
assert res["placed"] == 350 + 1 and res["same"] + res["differs"] == 50 and res["differs"] == 50 and res["same"] == 0
assert res["comparisons"] == 31 and res["backup"] and os.path.exists(res["backup"])
assert {w: cur.get_word(w)["tier"] for w in WORDS[:50]} == before            # nothing already decided is overwritten
assert cur.get_word("w00100")["tier"] == 100 % 6 and abs(cur.get_word("w00100")["rating"] - old_ratings["w00100"]) < 1e-9
assert cur.get_word("oldonly")["tier"] == 4                                   # a word the new list lacks is kept
assert cur.get_word("w00400")["skips"] == 1 and cur.get_word("w00401")["skips"] == 1
assert cur.stats()["placed"] == 50 + 351
# merged words leave the queue; skipped ones go to the back; nothing placed ever comes up
q = [r[0] for r in cur.db.execute("SELECT word FROM words WHERE tier IS NULL ORDER BY skips, qkey LIMIT 3000")]
assert not set(q) & {w for w in WORDS[:400]} and q[-1] in ("w00400", "w00401") and len(q) == 3000 - 400 + 0
bk = sqlite3.connect(res["backup"]); assert bk.execute("SELECT COUNT(*) FROM words WHERE tier IS NOT NULL").fetchone()[0] == 50; bk.close()
assert not res["backup"].endswith(".db")                                        # never mistaken for a save file
assert T.save_progress(res["backup"]) is not None                               # (it is a valid database, just not named like one)
src = T.Store(old); assert src.stats()["placed"] == 401; src.close()           # the source is untouched
res2 = cur.merge(old, backup=False)                                             # merging twice changes nothing
assert (res2["placed"], res2["added"], res2["skipped"], res2["comparisons"]) == (0, 0, 0, 0), res2
try:
    cur.merge(cur_path); raise SystemExit("merging a file into itself must fail")
except ValueError:
    pass
bad = os.path.join(tmp, "bad.db")
con = sqlite3.connect(bad); con.execute("CREATE TABLE t(x)"); con.commit(); con.close()
try:
    cur.merge(bad); raise SystemExit("a non-save database must be rejected")
except ValueError:
    pass
garbage = os.path.join(tmp, "garbage.bin"); open(garbage, "wb").write(os.urandom(5000))
try:
    r = cur.merge(garbage, backup=False)
    assert r["placed"] == 0
except ValueError:
    pass                                                                          # UnicodeDecodeError is a ValueError
assert cur.stats()["placed"] == 50 + 351
print("merge from save OK")

# ------------------------------------------------------------------ 4. export -> import round trips
cur.skip("w02000"); cur.skip("w02001")
for ext in (".txt", ".md", ".csv"):
    out = os.path.join(tmp, "export" + ext)
    T.write_export(out, cur.export_rows(), cur.skipped_words())
    fresh = T.Store(os.path.join(tmp, f"fresh{ext}.db"))
    fresh.insert_words(WORDS)                       # 'oldonly' is not in this list: it must be added, not lost
    r = fresh.merge(out, backup=False)
    want = {x["word"]: x["tier"] for x in cur.export_rows()}
    got = {x["word"]: x["tier"] for x in fresh.export_rows()}
    assert got == want, (ext, len(got), len(want))
    assert set(fresh.skipped_words()) == set(cur.skipped_words()), ext
    assert r["added"] == 1 and r["placed"] == len(want)
    # ordering inside each tier survives the trip
    for t in range(6):
        a = [x["word"] for x in cur.export_rows() if x["tier"] == t]
        b = [x["word"] for x in fresh.export_rows() if x["tier"] == t]
        assert a == b, (ext, t)
    if ext == ".csv":
        assert abs(fresh.get_word("w00100")["rating"] - round(cur.get_word("w00100")["rating"], 1)) < 1e-9
    fresh.close()
    print("export/import", ext, "OK")
print("RESUME OK")
