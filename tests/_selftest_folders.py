import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""F-47 (a review of the folder logic, asked for: "does what a user expects"): removing the source keeps what you
added or changed (a git checkout's uncommitted work, an unpacked folder's edits, your own files at the top, an
export); only TOP_FILES ship from the top; a new build is swapped in, never leaving none or half of one; moving the
save keeps the log and a kept download; a Mac app is started anew (open -n) after an update."""
import json, os, shutil, subprocess, sys, tempfile
import standalone as S

ROOT = _paths.ROOT
tmp = tempfile.mkdtemp(prefix="wtl-folders-")


def source(name, files=None):
    """A small source folder: tierlist.py, a module, a README (and `files`)."""
    d = os.path.join(tmp, name)
    for f, text in {"tierlist.py": "v1\n", os.path.join("src", "a.py"): "a1\n", "README.md": "r\n",
                    **(files or {})}.items():
        os.makedirs(os.path.dirname(os.path.join(d, f)), exist_ok=True)
        with open(os.path.join(d, f), "w") as fh:
            fh.write(text)
    return d


def names(folder):
    return sorted(os.path.relpath(os.path.join(b, f), folder).replace(os.sep, "/")
                  for b, _, fs in os.walk(folder) for f in fs)


# ---- what ships from the top: only TOP_FILES (an export, your notes or a script of yours never)
plain = source("plain", {"my notes.md": "mine\n", "my_script.py": "print(1)\n", "tierlist-export.md": "## S tier\n",
                         "tierlist.db": "save", os.path.join("tools", "t.py"): "t\n"})
assert sorted(S.source_files(plain)) == sorted(["README.md", os.path.join("src", "a.py"), "tierlist.py",
                                                os.path.join("tools", "t.py")]), S.source_files(plain)
if os.path.isdir(os.path.join(ROOT, ".git")) and shutil.which("git"):            # (in step with git's own list)
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
    top = {f for f in tracked if f and "/" not in f}
    assert top <= set(S.TOP_FILES), f"a new file at the top: add it to standalone.TOP_FILES: {top - set(S.TOP_FILES)}"

# ---- a plain folder (no git, no unpack record): the source's files go, yours stay
S.mark_for_removal(plain, git=lambda root: None)
assert not S.knows_changes(plain, git=lambda root: None)
left = S.remove_source(plain, tries=1)
assert names(plain) == ["my notes.md", "my_script.py", "tierlist-export.md", "tierlist.db"], names(plain)
# ... and a file changed after it was written down (between the window closing and the program starting) stays
plain2 = source("plain2")
S.mark_for_removal(plain2, git=lambda root: None)
with open(os.path.join(plain2, "src", "a.py"), "w") as fh:
    fh.write("changed since\n")
S.remove_source(plain2, tries=1)
assert names(plain2) == ["src/a.py"], names(plain2)
# ... an older window's record (a list of paths, no contents) still removes those files
plain3 = source("plain3")
with open(os.path.join(plain3, S.REMOVE_RECORD), "w") as fh:
    json.dump({"files": ["tierlist.py", "src/a.py"]}, fh)
S.remove_source(plain3, tries=1)
assert names(plain3) == ["README.md"], names(plain3)

# ---- a folder unpacked from the program: a file you edited since stays (it was kept as .bak on updates too)
packed = source("packed")
S._write_manifest(packed, packed)
unpacked = os.path.join(tmp, "Word Tierlister source")
S.unpack(packed, unpacked)
with open(os.path.join(unpacked, "src", "a.py"), "w") as fh:
    fh.write("my edit\n")
assert S.knows_changes(unpacked, git=lambda root: None)
assert sorted(S.removable(unpacked, git=lambda root: None)) == ["README.md", "tierlist.py"]
S.mark_for_removal(unpacked, git=lambda root: None)
S.remove_source(unpacked, tries=1)
assert names(unpacked) == ["src/a.py"], names(unpacked)
# ... and without the window's record (the unpack record alone), the same: only the unchanged ones go
unpacked2 = os.path.join(tmp, "unpacked2")
S.unpack(packed, unpacked2)
with open(os.path.join(unpacked2, "tierlist.py"), "w") as fh:
    fh.write("mine\n")
S.remove_source(unpacked2, tries=1)
assert names(unpacked2) == ["tierlist.py"], names(unpacked2)

# ---- a git checkout: only files as committed go; an uncommitted edit, a staged one, an untracked file and .git stay
if shutil.which("git"):
    repo = source("repo")
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t")
    git = lambda *a: subprocess.run(["git", *a], cwd=repo, env=env, capture_output=True, check=True)
    git("init", "-q")
    git("add", ".")
    git("commit", "-q", "-m", "one")
    with open(os.path.join(repo, "src", "a.py"), "w") as fh:
        fh.write("not committed\n")
    with open(os.path.join(repo, "README.md"), "w") as fh:
        fh.write("staged\n")
    git("add", "README.md")
    with open(os.path.join(repo, os.path.join("src", "b.py")), "w") as fh:
        fh.write("untracked\n")
    assert S.knows_changes(repo)
    assert sorted(S.removable(repo)) == ["tierlist.py"], S.removable(repo)
    S.mark_for_removal(repo)
    S.remove_source(repo, tries=1)
    kept = [n for n in names(repo) if not n.startswith(".git/")]
    assert kept == ["README.md", "src/a.py", "src/b.py"] and os.path.isdir(os.path.join(repo, ".git")), kept

# ---- a new build is swapped in: the old one replaced, nothing left beside it; a failed copy leaves the old one
dist, place = os.path.join(tmp, "dist"), os.path.join(tmp, "place")
os.makedirs(dist)
os.makedirs(place)
target = os.path.join(place, "word-tierlister")
with open(target, "w") as fh:
    fh.write("old")
built = os.path.join(dist, "word-tierlister")
with open(built, "w") as fh:
    fh.write("new")
assert S.install_program(built, target) == target and open(target).read() == "new"
assert sorted(os.listdir(place)) == ["word-tierlister"], os.listdir(place)
try:
    S.install_program(os.path.join(dist, "gone"), target)        # (the copy fails: nothing to copy)
    raise AssertionError("a failed copy must raise")
except OSError:
    pass
assert open(target).read() == "new" and sorted(os.listdir(place)) == ["word-tierlister"]
fresh = os.path.join(place, "Word Tierlister.app")                # (a .app is a folder; none there before)
os.makedirs(os.path.join(dist, "Word Tierlister.app", "Contents"))
S.install_program(os.path.join(dist, "Word Tierlister.app"), fresh)
assert os.path.isdir(os.path.join(fresh, "Contents")) and not os.path.exists(fresh + S.NEW_SUFFIX)

# ---- moving the save: a log already there gets this one added, a kept Wiktionary download moves along
here, there = os.path.join(tmp, "here"), os.path.join(tmp, "there")
os.makedirs(here)
os.makedirs(there)
for name, text in (("tierlist.db", "save"), ("tierlist.log", "old lines\n"), (S.WIKT_FILENAME, "download")):
    with open(os.path.join(here, name), "w") as fh:
        fh.write(text)
with open(os.path.join(there, "tierlist.log"), "w") as fh:
    fh.write("there\n")
assert S.move_save(os.path.join(here, "tierlist.db"), there) == os.path.join(there, "tierlist.db")
assert os.listdir(here) == [] and open(os.path.join(there, "tierlist.log")).read() == "there\nold lines\n"
assert open(os.path.join(there, S.WIKT_FILENAME)).read() == "download"

# ---- macOS: the new app is started as a new copy, even while this one (the same app) is still closing
started = []
real_platform, sys.platform = sys.platform, "darwin"
try:
    S.start("/Applications/Word Tierlister.app", popen=lambda cmd, **kw: started.append(cmd),
            args=["--db", "/x/tierlist.db"])
finally:
    sys.platform = real_platform
assert started == [["open", "-n", "/Applications/Word Tierlister.app", "--args", "--db", "/x/tierlist.db"]], started

shutil.rmtree(tmp, ignore_errors=True)
print("FOLDERS OK")
