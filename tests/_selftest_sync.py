import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""Syncing between devices (SY-1): the Store's stamps and apply_sync, the sync files (syncfiles.py), Syncthing's side
(syncthing_api.py, against a pretend Syncthing), AutoSync between two saves, and File > Sync with other devices."""
import gzip, io, json, os, sqlite3, tempfile, time, urllib.error
import tkinter as tk

import syncfiles, syncthing_api as st
from store import Store
from fonts import init_fonts
from ui_style import apply_ttk_style

TMP = tempfile.mkdtemp()
WORDS = ["cat", "dog", "eel", "fox", "gnu", "hen", "ant", "bee"]


def new_store(name):
    s = Store(os.path.join(TMP, name))
    s.insert_words(WORDS)
    return s


def changed(s, w):
    return s.db.execute("SELECT changed FROM words WHERE word=?", (w,)).fetchone()[0]


def rows_of(s):
    con = sqlite3.connect(s.path)
    try:
        return Store.sync_rows(con)
    finally:
        con.close()


# ---- the stamps: every change to a word's progress, never a queue key -------------------------------------------
a = new_store("a.db")
assert changed(a, "cat") is None                                  # (new words: no progress, no stamp)
t0 = time.time()
a.place("cat", 0); a.place("dog", 0)
assert changed(a, "cat") >= t0 and changed(a, "dog") >= t0
before = changed(a, "eel")
a.reshuffle(seed=3)                                               # (queue keys only)
assert changed(a, "eel") == before is None
a.skip("eel"); assert changed(a, "eel") is not None
c = changed(a, "cat"); time.sleep(0.01)
a.record_comparison("cat", "dog", "a", "within")                  # (ratings and duels change: stamped)
assert changed(a, "cat") > c
c = changed(a, "cat"); time.sleep(0.01)
a.undo()                                                          # (an undo is a change too: it travels)
assert changed(a, "cat") > c
assert a.get_meta("anchors_changed") is None
a.set_anchors(WORDS[:6]); assert float(a.get_meta("anchors_changed")) >= t0
# the triggers are TEMP: the file itself keeps none (an older version opens it as ever)
con = sqlite3.connect(a.path)
assert not con.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall(); con.close()

# ---- apply_sync: the newer change wins; an untouched word fills in; missing words are added ----------------------
a = new_store("a2.db"); b = new_store("b2.db")
a.place("cat", 0); a.place("dog", 1); a.record_comparison("cat", "dog", "a", "boundary")
time.sleep(0.01); b.place("cat", 3)                              # b's cat is newer
res = b.apply_sync("A", *rows_of(a))
assert res["words"] == 1 and res["comparisons"] == 1 and not res["added"]
assert b.get_word("cat")["tier"] == 3 and b.get_word("dog")["tier"] == 1
assert changed(b, "dog") == changed(a, "dog")                     # (keeps the time it changed there: no echo)
assert b.tier_counts() == {3: 1, 1: 1}                            # (the tallies follow)
v = b.version
assert b.apply_sync("A", *rows_of(a)) == {"words": 0, "added": 0, "anchors": False, "comparisons": 0}
assert b.version == v                                             # (nothing new: nothing changes, no refresh)
res = a.apply_sync("B", *rows_of(b))
assert a.get_word("cat")["tier"] == 3 and res["words"] == 1       # a takes b's newer cat
assert a.apply_sync("B", *rows_of(b))["words"] == 0 and b.apply_sync("A", *rows_of(a))["words"] == 0   # settled
# progress from before syncing (time 0 on both sides): a placed word here stays, an untouched one fills in
old = new_store("old.db")
old.place("eel", 2); old.place("fox", 4)
old.db.execute("UPDATE words SET changed=NULL"); old.db.commit()
mine = new_store("mine.db"); mine.place("eel", 5); mine.db.execute("UPDATE words SET changed=NULL"); mine.db.commit()
res = mine.apply_sync("OLD", *rows_of(old))
assert mine.get_word("eel")["tier"] == 5 and mine.get_word("fox")["tier"] == 4 and res["words"] == 1
# an unplaced word travels as an unplacing; a word this list lacks is added at the back
time.sleep(0.01); a.unplace("dog")
rows, anchors, when, comps = rows_of(a)
rows.append(["zebu", 2, 1600.0, 3, 0, time.time()])
res = b.apply_sync("A", rows, anchors, when, comps)
assert b.get_word("dog")["tier"] is None and res["added"] == 1 and b.get_word("zebu")["tier"] == 2
assert b.get_word("zebu")["rank"] >= 10_000_000 and b.get_word("zebu")["qkey"] >= 1e17
# the anchors follow when theirs changed later
time.sleep(0.01); a.set_anchors(["cat", "dog", "eel", "fox", "gnu", "hen"])
res = b.apply_sync("A", *rows_of(a))
assert res["anchors"] and b.get_anchors() == ["cat", "dog", "eel", "fox", "gnu", "hen"]
assert b.get_meta("anchors_changed") == a.get_meta("anchors_changed")
# the duels made there are mirrored: one taken back there (undo) goes here too; synced ones are never sent on
n = b.db.execute("SELECT COUNT(*) FROM comparisons WHERE origin='A'").fetchone()[0]
a.record_comparison("eel", "fox", "b", "within")
b.apply_sync("A", *rows_of(a))
assert b.db.execute("SELECT COUNT(*) FROM comparisons WHERE origin='A'").fetchone()[0] == n + 1
a.undo()
b.apply_sync("A", *rows_of(a))
assert b.db.execute("SELECT COUNT(*) FROM comparisons WHERE origin='A'").fetchone()[0] == n
assert all(c[0] != "eel" or c[1] != "fox" for c in rows_of(b)[3])   # (b writes only its own duels)
# a damaged row's tier is left out, not written
assert b.apply_sync("A", [["gnu", 9, 1500.0, 0, 0, time.time()]])["words"] == 0

# ---- the files ---------------------------------------------------------------------------------------------------
folder = os.path.join(TMP, "sync")
syncfiles.prepare_folder(folder)
assert "*.tmp" in open(os.path.join(folder, ".stignore")).read()
data = syncfiles.snapshot(a.path, "m1-s1", "laptop")              # (read through its own connection)
assert data["device"] == "m1-s1" and data["name"] == "laptop" and data["words"] == rows_of(a)[0]
path = syncfiles.write_file(folder, "m1-s1" + syncfiles.SUFFIX, data)
assert os.path.basename(path) == "m1-s1.wtsync" and not [n for n in os.listdir(folder) if n.endswith(".tmp")]
got = syncfiles.read_file(path)
assert got["name"] == "laptop" and got["words"] == data["words"] and got["anchors"] == data["anchors"]
assert syncfiles.apply(b, got)["words"] == 0                      # (b has all of it already)
for bad, why in ((b"not gzip", "readable"), (gzip.compress(b'{"program": "Other"}'), "not a Word Tierlister"),
                 (gzip.compress(json.dumps({"program": "Word Tierlister", "format": 99}).encode()), "newer version"),
                 (gzip.compress(json.dumps({"program": "Word Tierlister", "words": [["x", 1]]}).encode()), "damaged")):
    p = os.path.join(TMP, "bad.wtsync"); open(p, "wb").write(bad)
    try:
        syncfiles.read_file(p); raise AssertionError(why)
    except ValueError as exc:
        assert why in str(exc), exc
for n in ("m2-s1.wtsync", "m1-s2.wtsync", "m2-s1.sync-conflict-20260101-000000-ABCDEFG.wtsync", ".~m2.wtsync.tmp",
          "notes.txt"):
    open(os.path.join(folder, n), "w").close()
assert sorted(os.path.basename(p) for p in syncfiles.other_files(folder, "m1")) == ["m2-s1.wtsync"]
data_dir = os.path.join(TMP, "data")
mid = syncfiles.machine_id(data_dir)
assert len(mid) == 12 and syncfiles.machine_id(data_dir) == mid           # (made once, kept)
assert syncfiles.save_id(a) == syncfiles.save_id(a) == a.get_meta("sync_save_id")

# ---- Syncthing: finding, starting, its config ----------------------------------------------------------------------
ID1 = "GDEL2S5-LIIGXCZ-2H7UZVE-NSFZHQ3-VYEHDKV-JYNDVWU-COCZZQB-EANPXQC"
ID2 = "7ZFARQL-AMNDDQN-RBC6TYW-TP4R5JQ-MLV3XBE-YOHCTPQ-YESYRAI-64CEYQC"
assert st.clean_id(ID1.lower().replace("-", " ")) == ID1 and st.clean_id(" " + ID1 + "\n") == ID1
assert st.clean_id("ABC") is None and st.clean_id(ID1.replace("G", "1")) is None and st.short_id(ID1) == "GDEL2S5"
assert st.find_syncthing(which=lambda n: "/usr/bin/syncthing") == "/usr/bin/syncthing"
assert st.find_syncthing(which=lambda n: None, platform="darwin", exists=lambda p: p == "/opt/homebrew/bin/syncthing") \
    == "/opt/homebrew/bin/syncthing"
assert st.find_syncthing(which=lambda n: None, platform="win32", env={"LOCALAPPDATA": r"C:\L"},
                         exists=lambda p: "Links" in p).endswith("syncthing.exe")
assert st.find_syncthing(which=lambda n: None, platform="linux", exists=lambda p: False) is None
assert st.serve_args("st", (1, 27, 2), "linux") == ["st", "serve", "--no-browser"]
assert st.serve_args("st", (1, 18, 0), "linux") == ["st", "-no-browser"]                   # (Ubuntu 22.04's)
assert st.serve_args("st", (2, 0, 0), "win32") == ["st", "serve", "--no-browser", "--no-console"]


class Ran:
    def __init__(self, stdout="", code=0):
        self.stdout, self.returncode, self.stderr = stdout, code, ""


paths_out = "Configuration file:\n\t/home/u/.local/state/syncthing/config.xml\n\nDevice private key:\n\t/x\n"
assert st.config_path("st", run=lambda *a, **k: Ran(paths_out)) == "/home/u/.local/state/syncthing/config.xml"
assert st.config_path("st", run=lambda *a, **k: Ran(""), platform="linux", env={}, home="/h") \
    == "/h/.local/state/syncthing/config.xml"
assert st.version("st", run=lambda *a, **k: Ran('syncthing v1.27.2-ds4 "Gold Grasshopper"')) == (1, 27, 2)
cfg = os.path.join(TMP, "config.xml")
open(cfg, "w").write('<configuration><gui tls="false"><address>0.0.0.0:8384</address><apikey>KEY</apikey></gui>'
                     '</configuration>')
assert st.read_gui(cfg) == ("http://127.0.0.1:8384", "KEY")
open(cfg, "w").write('<configuration><gui tls="true"><address>127.0.0.1:9000</address><apikey>K</apikey></gui>'
                     '</configuration>')
assert st.read_gui(cfg) == ("https://127.0.0.1:9000", "K")
open(cfg, "w").write('<configuration><gui><address>127.0.0.1:9000</address></gui></configuration>')
assert st.read_gui(cfg) is None and st.read_gui(os.path.join(TMP, "none.xml")) is None
# starting at log-in: Linux without the service writes an autostart entry (once), with no ~/Sync made
home = os.path.join(TMP, "home")
os.environ.pop("XDG_CONFIG_HOME", None)
no_service = lambda cmd, **k: Ran("syncthing v1.27.2", 1 if cmd[0] == "systemctl" else 0)
p = st.start_at_login("/usr/bin/syncthing", platform="linux", home=home, run=no_service)
text = open(p).read()
assert p.endswith("autostart/syncthing-start.desktop") and "Exec=env STNODEFAULTFOLDER=1 /usr/bin/syncthing serve " \
    "--no-browser" in text
assert st.start_at_login("/usr/bin/syncthing", platform="linux", home=home, run=no_service) is None
p = st.start_at_login("/opt/st/syncthing", platform="darwin", home=home, run=no_service)
assert p.endswith("LaunchAgents/net.syncthing.wordtierlister.plist") and "<string>serve</string>" in open(p).read()
# connect(): not running -> started once, then reached
calls = {"start": 0}
open(cfg, "w").write('<configuration><gui><address>127.0.0.1:9</address><apikey>K</apikey></gui></configuration>')
st.config_path, real_config_path = (lambda exe: cfg), st.config_path
st.Client.ping, real_ping = (lambda self: calls["start"] > 0), st.Client.ping
st.start, real_start = (lambda exe, **k: calls.__setitem__("start", calls["start"] + 1)), st.start
assert isinstance(st.connect("st", sleep=lambda s: None), st.Client) and calls["start"] == 1
try:
    st.connect("st", start_it=False, wait=0) if not calls.update(start=0) else None; raise AssertionError
except st.SyncthingError as exc:
    assert "not running" in str(exc)
try:
    st.connect(None, wait=0) if not st.__dict__.update(find_syncthing=lambda: None) else None; raise AssertionError
except st.SyncthingError as exc:
    assert "not installed" in str(exc)
st.config_path, st.Client.ping, st.start = real_config_path, real_ping, real_start


# ---- Syncthing's API, against a pretend Syncthing -------------------------------------------------------------------
class FakeSyncthing:
    """Enough of Syncthing's REST API for linking: config folders and devices, pending requests, connections."""

    def __init__(self, me):
        self.me, self.folders, self.devices = me, {}, {me: {"deviceID": me, "name": "this"}}
        self.pending, self.connected, self.discovered, self.log = {}, set(), {}, []

    def __call__(self, req, timeout):
        method, url = req.get_method(), req.full_url
        assert req.headers.get("X-api-key") == "KEY"
        path, _, query = url.split("://", 1)[1].partition("/")[2].partition("?")
        path = "/" + path
        body = json.loads(req.data) if req.data else None
        self.log.append((method, path))
        out = self.answer(method, path, body, query)
        if out is None:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))
        return io.BytesIO(json.dumps(out).encode())

    def answer(self, method, path, body, query):
        parts = path.split("/")
        if path == "/rest/system/ping":
            return {"ping": "pong"}
        if path == "/rest/system/status":
            return {"myID": self.me}
        if path.startswith("/rest/config/defaults/"):
            return {"rescanIntervalS": 3600, "fsWatcherEnabled": False} if parts[-1] == "folder" else {"compression": "metadata"}
        if path == "/rest/config/folders":
            return list(self.folders.values())
        if path == "/rest/config/devices":
            return list(self.devices.values())
        if parts[1:4] == ["rest", "config", "folders"]:
            if method == "PUT":
                self.folders[parts[4]] = body; return {}
            return self.folders.get(parts[4])
        if parts[1:4] == ["rest", "config", "devices"]:
            if method == "PUT":
                self.devices[parts[4]] = body; return {}
            if method == "DELETE":
                return {} if self.devices.pop(parts[4], None) else None
            return self.devices.get(parts[4])
        if path == "/rest/system/connections":
            return {"connections": {d: {"connected": d in self.connected} for d in self.devices}}
        if path == "/rest/cluster/pending/devices":
            if method == "DELETE":
                self.pending.pop(query.split("=")[1], None); return {}
            return self.pending
        if path == "/rest/system/discovery":
            return self.discovered
        if path == "/rest/db/scan":
            return {}
        if path == "/rest/db/status":
            return {"state": "idle"}
        return None


fake = FakeSyncthing(ID1)
client = st.Client("http://127.0.0.1:8384", "KEY", opener=fake)
assert client.ping() and client.my_id() == ID1
f = client.ensure_folder("/data/sync")
assert f["id"] == st.FOLDER_ID and f["path"] == "/data/sync" and f["fsWatcherEnabled"] and f["devices"] == [{"deviceID": ID1}]
assert f["rescanIntervalS"] == 300                                # (from the defaults, with ours on top)
client.ensure_folder("/moved/sync"); assert fake.folders[st.FOLDER_ID]["path"] == "/moved/sync"
fake.pending[ID2] = {"name": "laptop", "address": "192.168.1.9:22000"}
assert client.pending_devices() == [{"id": ID2, "name": "laptop", "address": "192.168.1.9:22000"}]
fake.discovered = {ID2: {"addresses": ["tcp://192.168.1.9:22000"]}, "X": {"addresses": ["tcp://8.8.8.8:22000"]}}
assert client.nearby_devices() == [ID2]                           # (only ones on this network)
assert client.link(ID2.lower(), "laptop") == ID2
assert fake.devices[ID2]["autoAcceptFolders"] and fake.devices[ID2]["name"] == "laptop"
assert fake.devices[ID2]["compression"] == "metadata"             # (a new device starts from the defaults)
assert {"deviceID": ID2} in fake.folders[st.FOLDER_ID]["devices"] and not fake.pending
assert client.nearby_devices() == []                              # (linked now)
fake.connected.add(ID2)
assert client.devices() == [{"id": ID2, "name": "laptop", "connected": True, "shares": True}]
for bad, why in (("nonsense", "not a device code"), (ID1, "own code")):
    try:
        client.link(bad); raise AssertionError(why)
    except st.SyncthingError as exc:
        assert why in str(exc)
fake.folders["other"] = {"id": "other", "devices": [{"deviceID": ID2}]}
client.unlink(ID2)                                                # (it shares another folder: only ours lets go)
assert ID2 in fake.devices and {"deviceID": ID2} not in fake.folders[st.FOLDER_ID]["devices"]
del fake.folders["other"]; client.link(ID2); client.unlink(ID2)
assert ID2 not in fake.devices
def refuse(req, timeout):
    raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b"CSRF Error"))
def down(req, timeout):
    raise urllib.error.URLError("Connection refused")
for opener, why in ((refuse, "refused it (403: CSRF Error)"), (down, "could not be reached")):
    try:
        st.Client("http://x:1", "KEY", opener=opener).my_id(); raise AssertionError
    except st.SyncthingError as exc:
        assert why in str(exc), exc
assert not st.Client("http://x:1", "KEY", opener=down).ping()

# ---- AutoSync: two saves, one folder, both ways ----------------------------------------------------------------------
from syncdialog import AutoSync, SyncDialog
root = tk.Tk(); root.withdraw(); init_fonts(root); apply_ttk_style(root)


class FakeApp:
    def __init__(self, store):
        self.root, self.store, self.anim, self.busy, self.shut = root, store, None, False, False
        self.flashes, self.refreshed = [], 0

    def flash(self, text, kind="ok", ms=0):
        self.flashes.append(text)

    def after_external_change(self):
        self.refreshed += 1


def settle(sync):
    while sync.working:
        root.update(); time.sleep(0.01)


one, two = new_store("one.db"), new_store("two.db")
share = os.path.join(TMP, "shared")
for s in (one, two):
    s.set_meta("sync_folder", share)
app1, app2 = FakeApp(one), FakeApp(two)
s1 = AutoSync(app1, data_dir=os.path.join(TMP, "d1"), start=False)
s2 = AutoSync(app2, data_dir=os.path.join(TMP, "d2"), start=False)
s1.started = s2.started = True                                   # (never the real Syncthing in a test)
assert s1.auto and s1.machine != s2.machine
calls = []
AutoSync(app1, data_dir=os.path.join(TMP, "d1"), start=False).start_syncthing(connect=lambda: calls.append(1))
end = time.time() + 5
while not calls and time.time() < end:
    time.sleep(0.01)
assert calls == [1]
one.place("cat", 0); one.place("dog", 2)
assert s1.sync(force=True); settle(s1)
assert os.path.exists(os.path.join(share, s1.device() + ".wtsync")) and s1.written == one.version
assert not s1.sync(force=True)                                    # (nothing changed: nothing to do)
assert s2.sync(); settle(s2)
assert two.get_word("cat")["tier"] == 0 and two.get_word("dog")["tier"] == 2
assert app2.refreshed == 1 and app2.flashes[-1] == f"Synced 2 words from {syncfiles.device_name()}"
assert "Last synced just now" in s2.last()
time.sleep(0.01); two.place("cat", 4)
assert s2.sync(force=True); settle(s2)                            # (writes its own; the other's is seen already)
assert s1.sync(); settle(s1)
assert one.get_word("cat")["tier"] == 4 and app1.flashes[-1].startswith("Synced 1 word from")
# writes wait WRITE_GAP while things keep changing; reads never wait
one.place("eel", 1); s1.wrote_at = time.time()
assert not s1.sync() and s1.written != one.version
s1.flush(); assert s1.written == one.version                      # (closing writes at once)
assert s2.sync(); settle(s2); assert two.get_word("eel")["tier"] == 1
# a long job writing the save: folded in only afterwards
one.place("fox", 3); s1.flush()
app2.busy = True
assert not s2.sync()
app2.busy = False
# auto off: the timer leaves it alone (Sync now still works)
two.set_meta("sync_auto", "0"); assert not s2.auto
s2._tick(); assert not s2.working and two.get_word("fox")["tier"] is None
assert s2.sync(force=True); settle(s2); assert two.get_word("fox")["tier"] == 3
two.set_meta("sync_auto", "1")
# a file this version cannot read is said, not fatal
bad = os.path.join(share, "zzzz-yyyy.wtsync"); open(bad, "wb").write(b"junk")
assert s2.sync(); settle(s2)
assert "zzzz-yyyy.wtsync" in s2.last()
os.remove(bad)

# ---- File > Sync with other devices ----------------------------------------------------------------------------------
fake = FakeSyncthing(ID1)
started = []
app1.autosync = s1
one.set_meta("sync_folder", "")
import syncdialog
syncdialog.default_folder = lambda: os.path.join(TMP, "dialog-sync")


def texts(widget):
    out, stack = [], [widget]
    while stack:
        w = stack.pop(); stack.extend(w.winfo_children())
        try:
            out.append(str(w.cget("text")))
        except tk.TclError:
            pass
    return "\n".join(out)


def wait_for(cond, what):
    end = time.time() + 10
    while not cond():
        root.update(); time.sleep(0.01)
        assert time.time() < end, what


# not installed: asked to install it first (then the window opens); with nothing to install it with, its page
asks = []
def answer(reply):
    def ask(title, headline, message, yes="OK", no="Cancel", parent=None, wrap_chars=44):
        asks.append((headline, message, yes)); return reply
    return ask
syncdialog.deps.system_install_command = lambda what, window=False: ["pkexec", "apt-get", "install", "-y", what]
syncdialog.errors.ask_yes_no = answer(False)
d = SyncDialog(app1, find=lambda: None, show=False)
assert d.dlg is None and asks[-1][0] == "Install Syncthing first?" and "apt-get install -y syncthing" in asks[-1][1]
installed = []
SyncDialog.install, real_install = (lambda self, cmd, runner=None: installed.append(cmd)), SyncDialog.install
syncdialog.errors.ask_yes_no = answer(True)
SyncDialog(app1, find=lambda: None, show=False); assert installed == [["pkexec", "apt-get", "install", "-y", "syncthing"]]
SyncDialog.install = real_install
syncdialog.deps.system_install_command = lambda what, window=False: None
opened = []; syncdialog.errors.open_link = opened.append
SyncDialog(app1, find=lambda: None, show=False)
assert asks[-1][0] == "Get Syncthing first?" and opened == [syncdialog.DOWNLOAD_PAGE]
# the first time: asked once whether Syncthing starts at log-in (no tick box); "no" is kept
syncdialog.errors.ask_yes_no = answer(False)
d = SyncDialog(app1, find=lambda: "/usr/bin/syncthing", show=False,
               connect=lambda exe: st.Client("http://127.0.0.1:8384", "KEY", opener=fake),
               autostart=lambda exe: started.append(exe))
assert asks[-1][0] == syncdialog.AUTOSTART_HEADLINE and one.get_meta("sync_autostart") == "0"
wait_for(lambda: d.client is not None, "reached Syncthing"); assert started == []
for line in syncdialog.LIMITS + syncdialog.PROTECTIONS:
    assert line in texts(d.dlg.win)
assert "switched on" in syncdialog.LIMITS[0] and "same time" in syncdialog.LIMITS[0]
d.dlg.close(); n = len(asks)
one.set_meta("sync_autostart", ""); one.db.execute("DELETE FROM meta WHERE key='sync_autostart'"); one.db.commit()
syncdialog.errors.ask_yes_no = answer(True)
# installed: started, the folder shared, set to start at log-in (once), this device's code shown
d = SyncDialog(app1, find=lambda: "/usr/bin/syncthing", show=False,
               connect=lambda exe: st.Client("http://127.0.0.1:8384", "KEY", opener=fake),
               autostart=lambda exe: started.append(exe))
wait_for(lambda: d.client is not None and d.shown is not None, "the dialog reached Syncthing")
assert d.code.get() == ID1 and started == ["/usr/bin/syncthing"] and one.get_meta("sync_autostart") == "1"
assert len(asks) == n + 1                                         # (asked once: not again once answered)
assert fake.folders[st.FOLDER_ID]["path"] == os.path.join(TMP, "dialog-sync") == one.get_meta("sync_folder")
assert os.path.exists(os.path.join(TMP, "dialog-sync", ".stignore"))
assert "None yet." in texts(d.devices) and d.auto_var.get()      # (auto-sync on to start with)
d.copy(); assert root.clipboard_get() == ID1
# pasting a wrong code says so; a right one links
d.paste.set("hello"); d.link_pasted(); assert "not a device code" in d.link_msg.cget("text")
d.paste.set(ID2.replace("-", " ")); d.link_pasted()
wait_for(lambda: ID2 in fake.devices, "linked")
wait_for(lambda: "not connected now" in texts(d.devices), "the linked device listed")
fake.connected.add(ID2); d.refresh()
wait_for(lambda: ": connected" in texts(d.devices), "shown connected")
# a request from another device: Accept links it
ID3 = "AAAAAAA-BBBBBBB-CCCCCCC-DDDDDDD-EEEEEEE-FFFFFFF-GGGGGGG-HHHHHHH"
fake.pending[ID3] = {"name": "desktop", "address": "192.168.1.5:22000"}
d.refresh(); wait_for(lambda: "desktop" in texts(d.requests) and "code AAAAAAA" in texts(d.requests), "the request shown")
d.dlg.buttons["Accept " + ID3].invoke()
wait_for(lambda: ID3 in fake.devices and not fake.pending, "accepted")
assert fake.devices[ID3]["name"] == "desktop"
# the tick turns auto-sync off (saved)
d.auto_var.set(False); d.toggle_auto()
assert one.get_meta("sync_auto") == "0" and "only Sync now" in d.last.cget("text")
d.auto_var.set(True); d.toggle_auto()
d.sync_now(); settle(s1); root.update()
assert d.last.cget("text").startswith(("Last synced", "Not synced"))
d.dlg.close(); root.update()
assert d.show_last not in s1.listeners                            # (a closed dialog is not told any more)
print("SYNC OK")
