"""What went wrong, in plain language (ST-2). No tkinter here, so any layer can use it.

    SetupError           raise this (instead of sys.exit("...")) for a problem the user can fix; the message
                         says what happened and what to do next. main() shows it in a dialog.
    STOPPED_MESSAGE      the quiet SystemExit message used when the user closes the set-up window.
    describe(exc)        (headline, advice) for an exception: disk full, no internet, save file busy, ...
    open_log / append_log / ensure_streams
                         small helpers so messages are never lost when there is no console.
"""
import errno
import os
import socket
import sqlite3
import sys
import time
import urllib.error

STOPPED_MESSAGE = "Set-up stopped. Run the program again to continue where it left off."


class SetupError(Exception):
    """A problem the user can fix. str(exc) is the full, friendly message (what happened, what to do)."""


def describe(exc):
    """(headline, advice) in plain words for an exception. Unknown errors get a generic pair."""
    text = str(exc).lower()
    if isinstance(exc, SetupError):
        return "The program can't start yet", str(exc)
    if isinstance(exc, sqlite3.Error):
        if "locked" in text or "busy" in text:
            return ("Your save file is busy",
                    "Another copy of the program may be open. Close it and try again.")
        if "unable to open" in text:
            return ("Your save file can't be opened",
                    "Check that the file's folder exists and that you're allowed to use it, "
                    "or choose another file with --db.")
        if "readonly" in text or "read-only" in text:
            return ("Your save file can't be written to",
                    "Check that the file and its folder aren't read-only, then restart the program.")
        if "not a database" in text or "malformed" in text or "corrupt" in text:
            return ("Your save file looks damaged",
                    "Copy it somewhere safe, then restart; the program can import progress "
                    "from a copy (File > Import earlier progress).")
        if "full" in text or "disk" in text:
            return "The disk is full", "Free up some space and try again; nothing was lost."
    if isinstance(exc, OSError):
        if exc.errno == errno.ENOSPC:
            return "The disk is full", "Free up some space and try again; nothing was lost."
        if isinstance(exc, PermissionError):
            where = f" ({exc.filename})" if getattr(exc, "filename", None) else ""
            return ("The program isn't allowed to use a file" + where,
                    "Move the program to a folder you own (such as Documents) or check the file's permissions.")
        if isinstance(exc, (urllib.error.URLError, socket.gaierror, ConnectionError, TimeoutError)):
            return ("Couldn't reach the internet",
                    "Check your connection and run the program again; downloads pick up where they stopped.")
    if isinstance(exc, MemoryError):
        return "The computer ran out of memory", "Close other programs and try again."
    return "Something unexpected went wrong", "You can keep going; if it keeps happening, the details below help."


def open_log(path):
    """Append-mode text log (restarted when it passes 1 MB); falls back to the null device."""
    try:
        if os.path.exists(path) and os.path.getsize(path) > 1_000_000:
            open(path, "w").close()
        return open(path, "a", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        return open(os.devnull, "w")


def append_log(path, text):
    """Add `text` to the log file at `path`; never raises (a broken log must not hide the real error)."""
    try:
        with open(path, "a", encoding="utf-8", errors="replace") as f:
            f.write(text if text.endswith("\n") else text + "\n")
    except OSError:
        pass


SESSION_START, SESSION_END = "=== started", "=== closed"
_crash_log = []                       # the open file the crash handler writes into (it must stay open)


def start_session(log_path, version="", now=None):
    """Mark the program's start in the log (asked for: everything that goes wrong is in it), with what it runs on;
    say so when the last session never closed (a crash, a freeze killed by hand, the power going); and have a hard
    crash (Python or Tk itself failing: no Python error to catch) write every thread's stack there
    (faulthandler). Returns True if the last session ended without closing."""
    import faulthandler
    import platform
    unclosed = _last_session_unclosed(log_path)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
    if unclosed:
        append_log(log_path, f"--- {stamp}\nThe last session ended without closing (a crash, the program stopped "
                             "from outside, or the computer shutting down): anything it logged is above.")
    append_log(log_path, f"{SESSION_START} {stamp}: Word Tier List {version}, Python {platform.python_version()}, "
                         f"{platform.platform()}{' (built program)' if getattr(sys, 'frozen', False) else ''}")
    try:
        handle = open(log_path, "a", encoding="utf-8", errors="replace")
        faulthandler.enable(file=handle, all_threads=True)
        _crash_log[:] = [handle]
    except (OSError, ValueError, RuntimeError):
        pass
    return unclosed


def end_session(log_path, now=None):
    """Mark a clean close in the log (start_session looks for it next time)."""
    append_log(log_path, f"{SESSION_END} {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))}")


def _last_session_unclosed(log_path):
    """True if the log's last session start has no close after it."""
    try:
        with open(log_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 200_000))
            tail = f.read().decode("utf-8", "replace")
    except OSError:
        return False
    start, end = tail.rfind(SESSION_START), tail.rfind(SESSION_END)
    return start != -1 and end < start


def ensure_streams(log_path):
    """If started without a console (pythonw, a double-clicked launcher) the standard streams are None
    and print() would crash: send them to the log instead."""
    if sys.stdout is None or sys.stderr is None:
        sys.stdout = sys.stderr = open_log(log_path)
