import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""Nightly (asked for, for testing): File > Source & Updates shows "Update to nightly" only when main on GitHub differs
from the source you run (or the program was built from), told by comparing each file's git id with main's tree.
From source it updates the folder (git pull from main, only on main; otherwise main's source synced in, shown
first). In the program, main's source goes into the source folder beside it, which then starts with --build-nightly
and builds the program in its place, on the same save; the new program says it is the nightly build. (GitHub, git,
downloads and builds are stand-ins: the tests never go online.)"""
import json, os, shutil, subprocess, tempfile, time
os.environ["HOME"] = tempfile.mkdtemp()
os.environ["USERPROFILE"] = os.environ["HOME"]           # (Windows reads home from USERPROFILE)
import tkinter as tk
import tierlist as T
import sources
import standalone as S
from constants import VERSION


def project(**files):
    d = tempfile.mkdtemp(prefix="proj-")
    for f, text in dict({"tierlist.py": "x = 1\n", "src/a.py": "a = 1\n"}, **files).items():
        os.makedirs(os.path.join(d, os.path.dirname(f)), exist_ok=True)
        with open(os.path.join(d, f), "wb") as fh:
            fh.write(text.encode())
    return d


# ---- git's ids: the same as git's own, Windows line ends read as git keeps them -------------------------------------
proj = project(**{"src/b.py": "b = 2\r\nc = 3\r\n", "notes.txt": "mine\n"})
if shutil.which("git"):
    lf = os.path.join(tempfile.mkdtemp(), "b.py"); open(lf, "wb").write(b"b = 2\nc = 3\n")
    want = subprocess.run(["git", "hash-object", lf], capture_output=True, text=True).stdout.strip()
    assert S.blob_sha(os.path.join(proj, "src", "b.py")) == want == S.blob_sha(lf)
assert S.blob_sha(os.path.join(proj, "missing")) is None
here = S.local_files(proj)
assert sorted(here) == ["src/a.py", "src/b.py", "tierlist.py"], here     # (only the source's own files)
assert S.ships(os.path.join("src", "a.py")) and not S.ships("notes.txt") and not S.ships(os.path.join("dist", "x.py"))
assert not S.ships(os.path.join("src", "__pycache__", "a.py"))

# ---- main on GitHub: its newest commit and its files ----------------------------------------------------------------
tree = [{"path": p, "type": "blob", "sha": sha} for p, sha in here.items()] + \
       [{"path": "src", "type": "tree", "sha": "t"}, {"path": "dist/x.py", "type": "blob", "sha": "x"}]
commit = {"sha": "4f2c9ab" + "0" * 33, "commit": {"tree": {"sha": "tree1"}, "message": "Browse: sort\n\nmore",
                                                  "committer": {"date": "2026-11-03T20:00:00Z"}}}
urls = []


def github(answers):
    def fetch(url, timeout=10):
        urls.append(url)
        return json.dumps(answers[url]).encode()
    return fetch


answers = {S.MAIN_COMMIT: commit, S.TREE.format("tree1"): {"tree": tree}}
assert S.latest_main(github(answers)) is None and not urls          # (offline, as every test is)
offline = os.environ.pop("WORD_TIERLISTER_OFFLINE")
try:
    main = S.latest_main(github(answers))
    assert S.latest_main(lambda url, timeout=10: b"{}") is None and S.last_error   # (an odd answer: none, and why)
finally:
    os.environ["WORD_TIERLISTER_OFFLINE"] = offline
assert main["short"] == "4f2c9ab" and main["message"] == "Browse: sort" and main["nightly"]
assert main["when"] == 1793736000 and main["source"].endswith("/zipball/" + commit["sha"]), main
assert sorted(main["files"]) == sorted(here) and S.named(main) == "the nightly build (4f2c9ab)"
assert main["version"] == VERSION + "+4f2c9ab"
assert S.named({"version": "1.2.0"}) == "version 1.2.0"
# the same files: nothing to update to; one changed, one new on main, one gone from it: those three
assert S.nightly_changes(main, proj) == [] and S.nightly_changes(None, proj) == []
open(os.path.join(proj, "src", "a.py"), "wb").write(b"a = 2\n")
os.remove(os.path.join(proj, "tierlist.py"))
main2 = dict(main, files=dict(main["files"], **{"src/new.py": "n"}))
assert S.nightly_changes(main2, proj) == ["src/a.py", "src/new.py", "tierlist.py"]
open(os.path.join(proj, "tierlist.py"), "wb").write(b"x = 1\n")   # (bytes: Windows' text mode writes \r\n)
open(os.path.join(proj, "src", "a.py"), "wb").write(b"a = 1\n")

# a git checkout is compared as committed (edits of yours are not what main has)
if shutil.which("git"):
    g = project()
    q = {"cwd": g, "capture_output": True, "check": True}
    subprocess.run(["git", "init", "-q", "-b", "main"], **q)
    subprocess.run(["git", "add", "-A"], **q)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "one"], **q)
    open(os.path.join(g, "src", "a.py"), "w").write("edited\n")
    committed = S.local_files(g)
    assert committed["src/a.py"] == here["src/a.py"] and S.git_branch(g) == "main"
    assert S.git_branch(tempfile.mkdtemp()) is None
# git pulls main for a nightly
ran = []
S.git_pull("/p", run=lambda args, **kw: (ran.append(args), type("R", (), {"returncode": 0, "stdout": "", "stderr": ""}))[1],
           branch="main")
assert ran == [["git", "pull", "--ff-only", "origin", "main"]]

# ---- the dialog --------------------------------------------------------------------------------------------------------
def pump(root, n=6):
    for _ in range(n):
        root.update(); time.sleep(0.02)


def window():
    s = T.Store(os.path.join(tempfile.mkdtemp(), "s.db")); s.insert_words(["alpha", "beta", "gamma"])
    s.set_meta("dealt_asked", "1")
    s.set_meta("dev_tools", "1")                 # (the nightly shows only with Developer tools on, its bubble lit)
    root = tk.Tk()
    app = T.App(root, s, T.Definitions(s))
    pump(root, 10)
    return root, app


def gone(root):
    try:
        return not root.winfo_exists()
    except tk.TclError:
        return True


def settle(d, root):
    for _ in range(100):
        pump(root, 1)
        if d.checked or not d.alive():
            return


release = {"version": VERSION, "tag": "v" + VERSION, "source": "", "page": "", "assets": {}}
asked, errors_shown, started, links = [], [], [], []
sources.ask_yes_no = lambda *a, **kw: (asked.append((a[1], a[2])), True)[1]
sources.show_error = lambda *a, **kw: errors_shown.append((kw.get("headline"), a[1]))
sources.show_message = lambda *a, **kw: errors_shown.append((a[1], a[2]))
sources.errors.open_link = links.append
S.start = lambda path, args=(): started.append((path, list(args)))
S.start_source = lambda folder, python, args=(): started.append((folder, list(args)))

root, app = window()
Dialog = lambda **kw: sources.SourceDialog(app, source=None, platform="darwin", check=lambda: release, **kw)
# main is the same as this source: nothing to update to, only a line saying so
d = Dialog(frozen=False, root_dir=proj, nightly=lambda: main); settle(d, root)
assert sources.NIGHTLY not in d.buttons and len(d.nightly_box.winfo_children()) == 1
d.close()
# Developer tools off: no nightly at all, even while main differs, and main is never asked for (reported)
asked_main = []
app.dev_tools = False
d = Dialog(frozen=False, root_dir=project(**{"src/a.py": "a = 99\n"}), nightly=lambda: asked_main.append(1) or main)
settle(d, root)
assert sources.NIGHTLY not in d.buttons and not d.nightly_box.winfo_children() and not asked_main
d.close()
app.dev_tools = True
# main differs: says how and offers it; "What's changed" opens main's commits
proj2 = project(**{"src/a.py": "a = 99\n"})
d = Dialog(frozen=False, root_dir=proj2, nightly=lambda: main); settle(d, root)
assert sources.NIGHTLY in d.buttons and "What's changed" in d.buttons and "Update" not in d.buttons
said = " ".join(w.cget("text") for w in d.nightly_box.winfo_children() if isinstance(w, tk.Widget) and "text" in w.keys())
assert "2 changed files " in said and "4f2c9ab" in said and "Browse: sort" in said and "may be broken" in said, said
d.buttons["What's changed"].invoke(); assert links == [S.MAIN_PAGE]
# "Try again" asks GitHub again, the nightly too
d.again(); settle(d, root)
assert sources.NIGHTLY in d.buttons
# from source, not a git checkout: main's source synced in, shown first, then it starts again on the same save
S.git_checkout = lambda root_dir: False


def fetch(r, folder, log):
    shutil.copytree(proj, folder, dirs_exist_ok=True)
    S._write_manifest(folder, folder)
    return folder


save = app.store.path
d.update_nightly(fetch=fetch); pump(root, 3)
assert asked[-1][0] == "Update the source to the nightly build (4f2c9ab)?" and "1 updated" in asked[-1][1], asked
assert open(os.path.join(proj2, "src", "a.py")).read() == "a = 1\n" and started == [(proj2, ["--db", save])]
assert gone(root)
s = T.Store(save); assert s.get_meta(sources.UPDATED_FROM) == "nightly 4f2c9ab"; s.close()
# a git checkout: git pull from main, only while on main
root, app = window()
Dialog = lambda **kw: sources.SourceDialog(app, source=None, platform="darwin", check=lambda: release, **kw)
S.git_checkout = lambda root_dir: True
pulled = []
S.git_pull = lambda root_dir, branch=None: (pulled.append((root_dir, branch)), (True, "Fast-forward"))[1]
S.git_branch = lambda root_dir: "feature"
d = Dialog(frozen=False, root_dir=proj2, nightly=lambda: dict(main, files={})); settle(d, root)
assert "git pull from main" in " ".join(w.cget("text") for w in d.nightly_box.winfo_children() if "text" in w.keys())
d.buttons[sources.NIGHTLY].invoke(); pump(root, 3)
assert not pulled and "on branch feature" in errors_shown[-1][1] and d.alive()
S.git_branch = lambda root_dir: "main"
started.clear()
d.buttons[sources.NIGHTLY].invoke(); pump(root, 3)
assert pulled == [(proj2, "main")] and started == [(proj2, ["--db", app.store.path])] and gone(root)

# ---- in the program: main's source into the source folder beside it, which builds the program in its place ----------
root, app = window()
S.git_checkout = lambda root_dir: False
where = tempfile.mkdtemp()
prog = os.path.join(where, "word-tierlister-linux"); open(prog, "w").write("old")
beside = os.path.join(where, S.SOURCE_FOLDER)
carried = project(**{"src/a.py": "a = 99\n"}); S._write_manifest(carried, carried)
S.running_program = lambda: prog
S.existing_source = lambda: None
S.default_source_folder = lambda: beside
S.python_for_source = lambda: None
sources.offer_system_install = lambda *a, **kw: False
d = sources.SourceDialog(app, source=carried, frozen=True, platform="darwin", check=lambda: release,
                         nightly=lambda: main); settle(d, root)
assert sources.NIGHTLY in d.buttons and "Unpack" in d.buttons          # (compared with the source it carries)
said = " ".join(w.cget("text") for w in d.nightly_box.winfo_children() if "text" in w.keys())
assert "builds a new program" in said and "needs Python" in said, said
d.buttons[sources.NIGHTLY].invoke(); pump(root, 3)
assert errors_shown[-1][0] == "Not updated" and "needs Python 3" in errors_shown[-1][1] and d.alive()  # (no Python)
assert not os.path.exists(beside)
S.python_for_source = lambda: "/usr/bin/python3"
started.clear()
save = app.store.path
d.update_nightly(fetch=fetch); pump(root, 3)
assert asked[-1][0] == "Update to the nightly build (4f2c9ab)?" and where in asked[-1][1] and "PyInstaller" in asked[-1][1]
assert open(os.path.join(beside, "src", "a.py")).read() == "a = 1\n"
assert started == [(beside, ["--db", save, S.BUILD_NIGHTLY, prog])] and gone(root) and open(prog).read() == "old"
s = T.Store(save)
assert s.get_meta(sources.PENDING) == "4f2c9ab" and s.get_meta("offered_program") == "1"
assert not s.get_meta(sources.UPDATED_FROM)                   # (the source building it says nothing about it)
s.close()

# ...that source, started with --build-nightly: builds in the program's place (nothing asked), starts it, same save
store = T.Store(save)
root = tk.Tk(); app = T.App(root, store, T.Definitions(store)); pump(root, 10)
built = []
sources.SourceDialog.packages_ready = lambda self, ensure=None: True
S.make_program = lambda root_dir, log, **kw: (built.append((root_dir, kw)), kw["target"])[1]
sources.ask_buttons = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("asked to clean up behind"))
started.clear()
sources.SourceDialog(app, root_dir=beside, go=True, target=prog, platform="darwin"); pump(root, 3)
assert built == [(beside, {"target": prog})] and started == [(prog, ["--db", save])] and gone(root)
s = T.Store(save); assert s.get_meta(sources.UPDATED_FROM) == "nightly 4f2c9ab"; s.close()
# the program then says so once
root, app = window()
app.store.set_meta(sources.UPDATED_FROM, "nightly 4f2c9ab")
assert app._after_update() == "nightly 4f2c9ab" and "nightly build (4f2c9ab)" in app.toast.cget("text")
assert app._after_update() is None
app.on_close()

# tierlist.py starts that build from its option (only from source)
text = open(os.path.join(os.path.dirname(S.ROOT), os.path.basename(S.ROOT), "tierlist.py"), encoding="utf-8").read()
assert "standalone.BUILD_NIGHTLY" in text and "target=args.build_nightly" in text
assert sources.ago(time.time() - 3 * 3600 - 5) == "3 hours ago" and sources.ago(time.time()) == "just now"
assert sources.ago(100, now=100 + 86400) == "1 day ago"
print("NIGHTLY OK")
