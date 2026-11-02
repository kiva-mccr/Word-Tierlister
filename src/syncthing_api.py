"""Syncthing, the free program that keeps a folder the same on several computers (SY-1): finding it, starting it
(and at every log-in), and talking to it through its own local web API to link devices and share the sync folder.

Word Tierlister uses the Syncthing everyone else on the computer would: its usual configuration and folder (its
config.xml, found with `syncthing --paths`, holds the address and key of its API). If it is not running it is
started in the background, and set to start at log-in, so devices sync whenever both are on, not only while the
program is open. The shared folder has its own ID (FOLDER_ID): two devices that both share it with each other sync
it without either being asked to accept it.

Linking: this device adds the other's device ID; Syncthing then tries to connect, and the other device sees a
request (pending_devices) that it accepts by adding this one. Devices on the same network find each other
(nearby_devices); elsewhere they meet through Syncthing's free relays.

No tkinter here: calls block for a moment (a local HTTP request), so the dialog runs them on a worker thread.
"""
import glob
import json
import os
import re
import shlex
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import deps

FOLDER_ID = "word-tierlister"
FOLDER_LABEL = "Word Tierlister"
TIMEOUT = 5                       # seconds a call waits for Syncthing's answer
START_WAIT = 30                   # seconds starting it may take (its first start makes keys)
_ID = re.compile(r"^[A-Z2-7]{7}(-[A-Z2-7]{7}){7}$")


class SyncthingError(Exception):
    """Syncthing could not be reached, or refused a change (the message says which, in words)."""


def find_syncthing(which=None, platform=None, env=None, exists=os.path.exists):
    """The Syncthing program's path, or None when it is not installed. Beyond PATH: where winget, Homebrew and a
    user's own copy put it (a program installed while this one runs is not on its PATH yet)."""
    which = which or shutil.which
    platform = platform or sys.platform
    env = os.environ if env is None else env
    got = which("syncthing")
    if got:
        return got
    places = []
    if platform.startswith("win"):
        local = env.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        places.append(os.path.join(local, "Microsoft", "WinGet", "Links", "syncthing.exe"))
        places += sorted(glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages", "Syncthing.Syncthing*",
                                                "*", "syncthing.exe")))
    elif platform == "darwin":
        places += ["/opt/homebrew/bin/syncthing", "/usr/local/bin/syncthing"]
    else:
        places += ["/usr/bin/syncthing", "/usr/local/bin/syncthing", os.path.expanduser("~/.local/bin/syncthing"),
                   "/snap/bin/syncthing"]
    return next((p for p in places if exists(p)), None)


def _hidden():
    """Windows: run with no console window flashing up."""
    if sys.platform.startswith("win"):
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def version(exe, run=subprocess.run):
    """Syncthing's version as a tuple (1, 27, 2), or (0,) when it cannot be told."""
    try:
        out = run([exe, "--version"], capture_output=True, text=True, timeout=15, **_hidden()).stdout
    except (OSError, subprocess.SubprocessError):
        return (0,)
    m = re.search(r"v(\d+)\.(\d+)\.(\d+)", out or "")
    return tuple(int(x) for x in m.groups()) if m else (0,)


def serve_args(exe, ver, platform=None):
    """The command that runs Syncthing in the background: no browser opening, no console (Windows). Before 1.19
    there was no "serve" and the options had one dash."""
    platform = platform or sys.platform
    if ver and ver < (1, 19):
        return [exe, "-no-browser"] + (["-no-console"] if platform.startswith("win") else [])
    return [exe, "serve", "--no-browser"] + (["--no-console"] if platform.startswith("win") else [])


def config_path(exe, run=subprocess.run, platform=None, env=None, home=None):
    """Where Syncthing keeps its config.xml: what `syncthing --paths` says (1.21 and later), else the usual place,
    the first one that exists (or the first, for a Syncthing never started)."""
    try:
        out = run([exe, "--paths"], capture_output=True, text=True, timeout=15, **_hidden()).stdout or ""
        lines = out.splitlines()
        for i, line in enumerate(lines):
            if line.strip().lower().startswith("configuration file") and i + 1 < len(lines):
                return lines[i + 1].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    platform = platform or sys.platform
    env = os.environ if env is None else env
    home = home or os.path.expanduser("~")
    if platform.startswith("win"):
        local = env.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        places = [os.path.join(local, "Syncthing", "config.xml")]
    elif platform == "darwin":
        places = [os.path.join(home, "Library", "Application Support", "Syncthing", "config.xml")]
    else:
        state = env.get("XDG_STATE_HOME") or os.path.join(home, ".local", "state")
        conf = env.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
        places = [os.path.join(state, "syncthing", "config.xml"), os.path.join(conf, "syncthing", "config.xml")]
    return next((p for p in places if os.path.exists(p)), places[0])


def read_gui(path):
    """(the API's address, its key) from Syncthing's config.xml, or None while it has none."""
    try:
        gui = ET.parse(path).getroot().find("gui")
    except (OSError, ET.ParseError):
        return None
    if gui is None:
        return None
    address = (gui.findtext("address") or "127.0.0.1:8384").strip()
    key = (gui.findtext("apikey") or "").strip()
    if not key:
        return None
    if address.startswith("/"):                         # (a Unix socket: not something urllib can talk to)
        return None
    scheme = "https" if (gui.get("tls") or "").lower() == "true" else "http"
    host, _, port = address.rpartition(":")
    if host in ("", "0.0.0.0", "[::]", "::"):
        host = "127.0.0.1"
    return f"{scheme}://{host}:{port}", key


def clean_id(text):
    """A device ID as typed or pasted: capitals, dashes in place, spaces and line breaks gone. None when it cannot
    be one (eight groups of seven letters A-Z and digits 2-7)."""
    raw = re.sub(r"[^A-Za-z0-9]", "", text or "").upper()
    if len(raw) != 56:
        return None
    got = "-".join(raw[i:i + 7] for i in range(0, 56, 7))
    return got if _ID.match(got) else None


def short_id(device_id):
    """The first group of a device ID: what Syncthing itself shows to tell devices apart."""
    return (device_id or "").split("-")[0]


class Client:
    """Syncthing's local API (REST): every call sends the key; an https API's own certificate is accepted, since
    the address is this computer's."""

    def __init__(self, base, key, opener=None):
        self.base, self.key = base.rstrip("/"), key
        self._open = opener or self._urlopen

    @staticmethod
    def _urlopen(req, timeout):
        ctx = None
        if req.full_url.startswith("https://"):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE             # (Syncthing's own certificate, on this computer only)
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)

    def call(self, method, path, body=None, query=None):
        url = self.base + path + ("?" + urllib.parse.urlencode(query) if query else "")
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"X-API-Key": self.key, "Content-Type": "application/json"})
        try:
            with self._open(req, TIMEOUT) as r:
                text = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace").strip() if exc.fp else ""
            if exc.code == 404:
                return None
            raise SyncthingError(f"Syncthing refused it ({exc.code}{': ' + detail if detail else ''})") from None
        except (urllib.error.URLError, OSError) as exc:
            raise SyncthingError(f"Syncthing could not be reached ({getattr(exc, 'reason', exc)})") from None
        if not text.strip():
            return {}
        try:
            return json.loads(text)
        except ValueError:
            return {"text": text}

    def get(self, path, **query):
        return self.call("GET", path, query=query or None)

    # ---- what it knows ------------------------------------------------------------------------------------------
    def ping(self):
        try:
            return (self.get("/rest/system/ping") or {}).get("ping") == "pong"
        except SyncthingError:
            return False

    def my_id(self):
        return (self.get("/rest/system/status") or {}).get("myID", "")

    def devices(self):
        """The devices linked to this one: [{"id", "name", "connected", "shares"}] (shares: the sync folder is
        shared with it)."""
        me = self.my_id()
        folder = self.folder() or {}
        sharing = {d.get("deviceID") for d in folder.get("devices", [])}
        conns = (self.get("/rest/system/connections") or {}).get("connections", {})
        out = []
        for d in self.get("/rest/config/devices") or []:
            did = d.get("deviceID")
            if did and did != me:
                out.append({"id": did, "name": d.get("name") or short_id(did),
                            "connected": bool(conns.get(did, {}).get("connected")), "shares": did in sharing})
        return out

    def pending_devices(self):
        """Devices that asked to link to this one: [{"id", "name", "address"}]."""
        got = self.get("/rest/cluster/pending/devices") or {}
        return [{"id": did, "name": v.get("name") or short_id(did), "address": v.get("address", "")}
                for did, v in got.items()]

    def nearby_devices(self):
        """Device IDs Syncthing has seen on this network (local discovery), not linked to this one yet."""
        me = self.my_id()
        linked = {d.get("deviceID") for d in self.get("/rest/config/devices") or []}
        found = self.get("/rest/system/discovery") or {}
        out = []
        for did, v in found.items():
            addresses = v.get("addresses", []) if isinstance(v, dict) else []
            local = any(_is_local(a) for a in addresses)
            if did != me and did not in linked and local:
                out.append(did)
        return sorted(out)

    def folder(self):
        return self.get(f"/rest/config/folders/{FOLDER_ID}")

    # ---- changes ------------------------------------------------------------------------------------------------
    def _defaults(self, kind):
        return dict(self.get(f"/rest/config/defaults/{kind}") or {})

    def ensure_folder(self, path):
        """Share `path` as the sync folder (made once; its path follows if it moved). Returns the folder's config."""
        got = self.folder()
        if got:
            if os.path.normcase(got.get("path", "")) != os.path.normcase(path):
                got["path"] = path
                self.call("PUT", f"/rest/config/folders/{FOLDER_ID}", got)
            return got
        me = self.my_id()
        cfg = self._defaults("folder")
        cfg.update({"id": FOLDER_ID, "label": FOLDER_LABEL, "path": path, "type": "sendreceive",
                    "devices": [{"deviceID": me}], "fsWatcherEnabled": True, "fsWatcherDelayS": 2,
                    "rescanIntervalS": 300, "paused": False})
        self.call("PUT", f"/rest/config/folders/{FOLDER_ID}", cfg)
        return cfg

    def link(self, device_id, name=""):
        """Link a device (or accept its request): add it, accept folders it shares, and share the sync folder with
        it. Raises SyncthingError with what went wrong."""
        did = clean_id(device_id)
        if not did:
            raise SyncthingError("That is not a device code: it is eight groups of seven letters and digits.")
        if did == self.my_id():
            raise SyncthingError("That is this device's own code: paste the code shown on the other device.")
        have = self.get(f"/rest/config/devices/{did}")
        cfg = dict(have) if have else self._defaults("device")
        cfg.update({"deviceID": did, "autoAcceptFolders": True})
        if name or not cfg.get("name"):
            cfg["name"] = name or cfg.get("name") or short_id(did)
        self.call("PUT", f"/rest/config/devices/{did}", cfg)
        folder = self.folder()
        if folder is None:
            raise SyncthingError("The sync folder is not set up in Syncthing.")
        if did not in {d.get("deviceID") for d in folder.get("devices", [])}:
            folder.setdefault("devices", []).append({"deviceID": did})
            self.call("PUT", f"/rest/config/folders/{FOLDER_ID}", folder)
        try:
            self.call("DELETE", "/rest/cluster/pending/devices", query={"device": did})
        except SyncthingError:
            pass
        return did

    def unlink(self, device_id):
        """Stop syncing with a device: it is taken out of the sync folder (and forgotten if it shares nothing else
        with this one, so Syncthing's other folders are left as they were)."""
        folder = self.folder()
        if folder:
            folder["devices"] = [d for d in folder.get("devices", []) if d.get("deviceID") != device_id]
            self.call("PUT", f"/rest/config/folders/{FOLDER_ID}", folder)
        others = [f for f in self.get("/rest/config/folders") or [] if f.get("id") != FOLDER_ID and
                  device_id in {d.get("deviceID") for d in f.get("devices", [])}]
        if not others:
            self.call("DELETE", f"/rest/config/devices/{device_id}")

    def dismiss(self, device_id):
        """Turn down a device's request to link."""
        self.call("DELETE", "/rest/cluster/pending/devices", query={"device": device_id})

    def rescan(self):
        """Ask Syncthing to look at the sync folder now (it would within seconds anyway)."""
        self.call("POST", "/rest/db/scan", query={"folder": FOLDER_ID})


def _is_local(address):
    """True for an address on this network (local discovery reports the IP it heard from)."""
    m = re.search(r"://\[?([0-9a-fA-F:.]+)\]?:\d+", address or "")
    if not m:
        return False
    ip = m.group(1)
    return (ip.startswith(("10.", "192.168.", "169.254.", "fe80", "fd", "fc")) or
            bool(re.match(r"^172\.(1[6-9]|2\d|3[01])\.", ip)))


# ---- starting it ------------------------------------------------------------------------------------------------
def _systemd_unit(run=subprocess.run):
    """True when Syncthing's own user service is there to use (the Linux packages ship syncthing.service)."""
    if not shutil.which("systemctl"):
        return False
    try:
        r = run(["systemctl", "--user", "cat", "syncthing.service"], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def start(exe, popen=subprocess.Popen, run=subprocess.run, platform=None):
    """Start Syncthing in the background, on its own (it keeps running when Word Tierlister closes). Linux with
    systemd: its own user service, started, not enabled (start_at_login does that, if you let it). Returns how
    ("service" or "process")."""
    platform = platform or sys.platform
    if platform.startswith("linux") and _systemd_unit(run):
        try:
            r = run(["systemctl", "--user", "start", "syncthing.service"], capture_output=True, timeout=30)
            if r.returncode == 0:
                return "service"
        except (OSError, subprocess.SubprocessError):
            pass
    env = dict(os.environ, STNODEFAULTFOLDER="1")      # (its first start would make a ~/Sync folder otherwise)
    kw = {"start_new_session": True} if os.name == "posix" else {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    popen(serve_args(exe, version(exe, run), platform), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL, env=env, close_fds=True, **kw)
    return "process"


def connect(exe=None, start_it=True, wait=START_WAIT, clock=time.monotonic, sleep=time.sleep, **how):
    """A Client for this computer's Syncthing, started first if it is not running (`start_it`). Raises
    SyncthingError (not installed, or it did not come up in `wait` seconds)."""
    exe = exe or find_syncthing()
    if not exe:
        raise SyncthingError("Syncthing is not installed.")
    path = config_path(exe)
    started = False
    end = clock() + wait
    while True:
        gui = read_gui(path)
        if gui:
            client = Client(*gui)
            if client.ping():
                return client
        if not start_it:
            raise SyncthingError("Syncthing is not running.")
        if not started:
            start(exe, **how)
            started = True
        if clock() > end:
            raise SyncthingError("Syncthing did not start (it gave no answer for half a minute).")
        sleep(0.5)
        if not gui:
            path = config_path(exe)                     # (a first start writes it, maybe somewhere new)


def autostart_path(platform=None, home=None, appdata=None):
    """Where the start-at-log-in entry goes when there is no service to enable: Linux's autostart folder, the
    Windows Startup folder, macOS's LaunchAgents."""
    platform = platform or sys.platform
    home = home or os.path.expanduser("~")
    if platform.startswith("win"):
        appdata = appdata or os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "Syncthing.lnk")
    if platform == "darwin":
        return os.path.join(home, "Library", "LaunchAgents", "net.syncthing.wordtierlister.plist")
    conf = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return os.path.join(conf, "autostart", "syncthing-start.desktop")


PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>net.syncthing.wordtierlister</string>
<key>ProgramArguments</key><array>{args}</array>
<key>EnvironmentVariables</key><dict><key>STNODEFAULTFOLDER</key><string>1</string></dict>
<key>RunAtLoad</key><true/>
</dict></plist>
"""


def start_at_login(exe, platform=None, home=None, appdata=None, run=subprocess.run):
    """Make Syncthing start at every log-in (asked for: sync should not wait for Word Tierlister to be open).
    Linux: its own service if there is one, else an autostart entry; Windows: a shortcut in the Startup folder;
    macOS: Homebrew's service, else a LaunchAgent. Returns the path written, "service", or None if it was already
    set up. Raises OSError when it could not be done."""
    platform = platform or sys.platform
    if platform.startswith("linux") and _systemd_unit(run):
        r = run(["systemctl", "--user", "is-enabled", "syncthing.service"], capture_output=True, text=True,
                timeout=10)
        if r.returncode == 0:
            return None
        r = run(["systemctl", "--user", "enable", "syncthing.service"], capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return "service"
    if platform == "darwin" and shutil.which("brew") and "brew" in os.path.realpath(exe).lower() + exe:
        r = run(["brew", "services", "start", "syncthing"], capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            return "service"
    path = autostart_path(platform, home, appdata)
    if os.path.exists(path):
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    args = serve_args(exe, version(exe, run), platform)
    if platform.startswith("win"):
        env = dict(os.environ, WTL_LNK=path, WTL_TARGET=exe, WTL_ARGS=subprocess.list2cmdline(args[1:]),
                   WTL_DIR=os.path.dirname(exe), WTL_ICON=exe + ",0")
        r = run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
                 deps.SHORTCUT_PS.replace("Tier-list every English word, at your own pace", "Syncthing")],
                env=env, capture_output=True, text=True, timeout=60, **_hidden())
        if r.returncode != 0 or not os.path.exists(path):
            raise OSError((r.stderr or r.stdout or "").strip() or "the shortcut was not written")
    elif platform == "darwin":
        from xml.sax.saxutils import escape
        with open(path, "w", encoding="utf-8") as f:
            f.write(PLIST.format(args="".join(f"<string>{escape(a)}</string>" for a in args)))
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write("[Desktop Entry]\nType=Application\nName=Syncthing\nComment=Keeps folders in sync "
                    "(started for Word Tierlister)\nExec=env STNODEFAULTFOLDER=1 " + shlex.join(args) +
                    "\nNoDisplay=true\nX-GNOME-Autostart-enabled=true\n")
    return path
