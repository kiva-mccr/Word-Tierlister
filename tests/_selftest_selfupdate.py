import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""U-1: File > Source & Updates' Updates (one panel since U-4). The program updates itself: this computer's program
from the newest release is downloaded beside the running one (the release's names: RELEASE_ASSETS), swapped in (the
old one kept as .old until the new one removes it as it starts; a failed swap puts the old one back) and started on
the same save. A source folder is brought up to date: git pull in a git checkout (your own changes never touched:
git refuses instead), the release's source synced in otherwise. At start, at most once a day, a newer version is
told once in a toast. The first start after an update says so. (GitHub's answers, downloads and git are stand-ins:
the tests never go online.)"""
import io, json, os, tempfile, time, zipfile
os.environ["HOME"] = tempfile.mkdtemp()
import tkinter as tk
import tierlist as T
import sources
import standalone as S
from constants import VERSION

# ---- the release's programs ---------------------------------------------------------------------------------------
answer = {"tag_name": "v9.1.0", "zipball_url": "zip", "html_url": "page",
          "assets": [{"name": n, "browser_download_url": "https://dl/" + n, "size": 5} for n in S.RELEASE_ASSETS.values()]
          + [{"name": "odd"}]}
offline = os.environ.pop("WORD_TIERLIST_OFFLINE")
try:
    release = S.latest_release(lambda url, timeout=10: json.dumps(answer).encode())
finally:
    os.environ["WORD_TIERLIST_OFFLINE"] = offline
assert sorted(release["assets"]) == sorted(S.RELEASE_ASSETS.values()), release
assert S.program_download(release, "win32")["url"] == "https://dl/word-tierlist-windows.exe"
assert S.program_download(release, "linux")["size"] == 5 and S.program_download(release, "darwin")
assert S.program_download(release, "sunos5") is None and S.program_download(None) is None
assert S.running_program(frozen=False) is None                                     # (from source: no program)
assert S.running_program("linux", "/opt/w/word-tierlist", True) == "/opt/w/word-tierlist"
assert S.running_program("darwin", "/A/Word Tier List.app/Contents/MacOS/Word Tier List", True) == "/A/Word Tier List.app"

# downloading it: the Linux / Windows file made runnable; a short download refused; macOS: the .app out of its zip
def downloader(data):
    def download(url, dest, log):
        open(dest, "wb").write(data); log("  5 of 5 MB (100%)"); return len(data)
    return download
d = tempfile.mkdtemp()
got = S.fetch_program(release, d, log=lambda t: None, platform="linux", download=downloader(b"12345"))
assert got == os.path.join(d, "word-tierlist-linux") and os.access(got, os.X_OK)
for bad in (b"12", b""):
    try:
        S.fetch_program(release, tempfile.mkdtemp(), log=lambda t: None, platform="win32", download=downloader(bad))
        raise AssertionError("should have failed")
    except OSError as exc:
        assert "cut short" in str(exc)
try:
    S.fetch_program({"version": "9.1.0", "assets": {}}, d, log=lambda t: None, platform="linux")
    raise AssertionError("should have failed")
except OSError as exc:
    assert "no program for this computer" in str(exc)
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    info = zipfile.ZipInfo("Word Tier List.app/Contents/MacOS/Word Tier List"); info.external_attr = 0o755 << 16
    z.writestr(info, "app")
    z.writestr("Word Tier List.app/Contents/Info.plist", "plist")
mac = buf.getvalue()
release_mac = dict(release, assets=dict(release["assets"], **{"word-tierlist-macos.zip": {"url": "u", "size": len(mac)}}))
d = tempfile.mkdtemp()
got = S.fetch_program(release_mac, d, log=lambda t: None, platform="darwin", download=downloader(mac))
assert got == os.path.join(d, "Word Tier List.app") and os.listdir(d) == ["Word Tier List.app"]
assert os.access(S.executable(got, "darwin"), os.X_OK)

# swapping it in: the old one kept beside it, removed as the new one starts (with any download folder left over)
where = tempfile.mkdtemp()
prog = os.path.join(where, "word-tierlist")
open(prog, "w").write("old"); open(os.path.join(where, "tierlist.db"), "w").write("save")
folder = S.update_folder(prog)
assert os.path.dirname(folder) == where and os.path.basename(folder).startswith(S.UPDATE_DIR)
new = os.path.join(folder, "word-tierlist-linux"); open(new, "w").write("new")
old = S.replace_program(new, prog)
assert open(prog).read() == "new" and open(old).read() == "old" and old == prog + S.OLD_SUFFIX
assert S.remove_old_program(prog, tries=1) == 2                                     # (the .old and the folder)
assert sorted(os.listdir(where)) == ["tierlist.db", "word-tierlist"]
assert S.remove_old_program(prog, tries=1) == 0
# a swap that fails puts the old one back
real_move = S.shutil.move
S.shutil.move = lambda a, b: (_ for _ in ()).throw(OSError("disk full"))
new = os.path.join(S.update_folder(prog), "n"); open(new, "w").write("newer")
try:
    S.replace_program(new, prog); raise AssertionError("should have failed")
except OSError:
    pass
finally:
    S.shutil.move = real_move
assert open(prog).read() == "new" and not os.path.exists(prog + S.OLD_SUFFIX)
# a folder that cannot be written to: no update folder (then it says so before downloading anything)
try:
    S.update_folder(os.path.join(where, "missing", "word-tierlist")); raise AssertionError("should have failed")
except OSError:
    pass

# ---- git pull: in a git checkout only; what git said comes back -------------------------------------------------------
class R:
    def __init__(self, code, out="", err=""):
        self.returncode, self.stdout, self.stderr = code, out, err
ran = []
assert S.git_pull("/p", run=lambda args, **kw: (ran.append((args, kw["cwd"])), R(0, "Fast-forward\n"))[1]) == \
    (True, "Fast-forward")
assert ran == [(["git", "pull", "--ff-only"], "/p")]
ok, said = S.git_pull("/p", run=lambda args, **kw: R(1, "", "error: Your local changes would be overwritten"))
assert not ok and "local changes" in said
assert not S.git_checkout(tempfile.mkdtemp())


# ---- the dialog ---------------------------------------------------------------------------------------------------------
def pump(root, n=6):
    for _ in range(n):
        root.update(); time.sleep(0.02)


def window():
    s = T.Store(os.path.join(tempfile.mkdtemp(), "s.db")); s.insert_words(["alpha", "beta", "gamma"])
    s.set_meta("dealt_asked", "1")
    root = tk.Tk()
    app = T.App(root, s, T.Definitions(s))
    pump(root, 10)
    return root, app


def settle(d, root):
    for _ in range(30):
        if "Checking" not in d.line.cget("text"):
            return
        pump(root, 3)
    raise AssertionError("the check never answered")


def gone(root):
    try:
        return not root.winfo_exists()
    except tk.TclError:
        return True


errors_shown, links, asked, started = [], [], [], []
sources.show_error = lambda *a, **kw: errors_shown.append(kw.get("headline"))
sources.errors.open_link = links.append
sources.ask_yes_no = lambda *a, **kw: (asked.append(a[1]), True)[1]
S.start = lambda path, args=(): started.append((path, list(args)))
S.start_source = lambda folder, python, args=(): started.append((folder, list(args)))

root, app = window()
labels = [it[1] for it in dict(app._menu_items())["File"] if it[0] == "command"]
assert "Source & Updates..." in labels and "Check for updates..." not in labels          # (U-4: one panel)
Dialog = lambda **kw: sources.SourceDialog(app, source=None, platform="darwin", **kw)  # (nothing to unpack; no menu)
# offline / nothing newer: says so, and why; "Try again" asks again
S.last_error = "GitHub could not be reached: certificate verify failed"            # (U-3: why, when it is known)
d = Dialog(check=lambda: None, frozen=True); settle(d, root)
assert "Could not check" in d.line.cget("text") and list(d.buttons) == ["Close", "Try again"], list(d.buttons)
assert "certificate verify failed" in d.how.cget("text")
assert "nothing to unpack" in str([w.cget("text") for w in d.dlg.body.winfo_children() if hasattr(w, "cget")
                                    and "text" in w.keys()])
S.last_error = None
d.check = lambda: {"version": VERSION, "tag": "v" + VERSION, "source": "", "page": "", "assets": {}}
d.buttons["Try again"].invoke(); settle(d, root)
assert "the newest there is" in d.line.cget("text") and list(d.buttons) == ["Close"]
d.close()
# a newer one, but none built for this computer: the release page instead
d = Dialog(check=lambda: dict(release, assets={}), frozen=True); settle(d, root)
assert "9.1.0 is out" in d.line.cget("text") and "Update" not in d.buttons and "no program" in d.how.cget("text")
d.buttons["Open the release page"].invoke(); assert links == ["page"]
d.close()
# in the program: Update downloads beside it, swaps it in and starts it on the same save; this window closes
where = tempfile.mkdtemp()
prog = os.path.join(where, "word-tierlist.exe"); open(prog, "w").write("old")
fetched = []
def fetch(r, folder, log):
    fetched.append((r["version"], os.path.dirname(folder)))
    p = os.path.join(folder, "word-tierlist-windows.exe"); open(p, "w").write("new"); return p
S.running_program = lambda: prog
real_fetch, S.fetch_program = S.fetch_program, fetch
d = Dialog(check=lambda: release, frozen=True); settle(d, root)
assert list(d.buttons) == ["Close", "What's new", "Update"] and "same save" in d.how.cget("text")
assert d.dlg._default is d.buttons["Update"]                                 # (Enter updates)
save = app.store.path
d.buttons["Update"].invoke(); pump(root, 3)
assert fetched == [("9.1.0", where)] and open(prog).read() == "new" and open(prog + S.OLD_SUFFIX).read() == "old"
assert started == [(prog, ["--db", save])] and gone(root) and not errors_shown
assert sorted(os.listdir(where)) == ["word-tierlist.exe", "word-tierlist.exe.old"]          # (no download folder left)
s = T.Store(save); assert s.get_meta(sources.UPDATED_FROM) == VERSION; s.close()
# the download fails: says so, nothing changes, the window stays
root, app = window()
Dialog = lambda **kw: sources.SourceDialog(app, source=None, platform="darwin", **kw)
S.fetch_program = lambda r, folder, log: (_ for _ in ()).throw(OSError("no network"))
d = Dialog(check=lambda: release, frozen=True); settle(d, root)
d.buttons["Update"].invoke(); pump(root, 3)
assert errors_shown == ["Not updated"] and open(prog).read() == "new" and d.alive() and not gone(root)
assert sorted(os.listdir(where)) == ["word-tierlist.exe", "word-tierlist.exe.old"]
d.close()
# from source, a git checkout: git pull, then it starts again from the source on the same save
errors_shown.clear(); started.clear()
proj = tempfile.mkdtemp()
S.git_checkout = lambda root_dir: True
pulled = []
S.git_pull = lambda root_dir: (pulled.append(root_dir), (True, "Fast-forward"))[1]
d = Dialog(check=lambda: release, frozen=False, root_dir=proj); settle(d, root)
assert "git pull" in d.how.cget("text")
save = app.store.path
d.buttons["Update"].invoke(); pump(root, 3)
assert pulled == [proj] and asked[-1] == "Update the source to version 9.1.0?" and started == [(proj, ["--db", save])]
assert gone(root)
# git refuses (your own changes): what it said is shown, nothing starts
root, app = window()
Dialog = lambda **kw: sources.SourceDialog(app, source=None, platform="darwin", **kw)
started.clear()
S.git_pull = lambda root_dir: (False, "error: Your local changes would be overwritten")
d = Dialog(check=lambda: release, frozen=False, root_dir=proj); settle(d, root)
d.buttons["Update"].invoke(); pump(root, 3)
assert errors_shown == ["Not updated"] and not started and d.alive()
d.close()
# not a git checkout: the release's source synced in, shown first (_selftest_sources)
S.git_checkout = lambda root_dir: False
d = Dialog(check=lambda: release, frozen=False, root_dir=proj); settle(d, root)
assert "shows what it changes" in d.how.cget("text")
d.close()

# ---- after an update: said once; at start, a newer version told once a day at most ----------------------------------
app.store.set_meta(sources.UPDATED_FROM, "0.9.0")
assert app._after_update() == "0.9.0" and "Updated to version" in app.toast.cget("text")
assert app._after_update() is None and not app.store.get_meta(sources.UPDATED_FROM)
for w in root.winfo_children():                                             # (the start's anchor words page)
    if getattr(w, "styled_dialog", False):
        w.destroy()
asks = []
def check():
    asks.append(1); return release
app._check_for_update(check); pump(root, 60)
assert asks == [1] and "9.1.0 is out" in app.toast.cget("text") and app.store.get_meta("update_told") == "9.1.0"
app._check_for_update(check); pump(root, 10)
assert asks == [1]                                                          # (asked less than a day ago)
app.store.set_meta("update_checked", 0); app.flash("something else")
app._check_for_update(check); pump(root, 60)
assert asks == [1, 1] and app.toast.cget("text") == "something else"         # (this version was told already)
app.on_close()
S.fetch_program = real_fetch
print("SELF-UPDATE OK")
