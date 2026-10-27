import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""Asked for: the log keeps everything that goes wrong, freezes and crashes too (problems.start_session /
end_session, errors.watch_freezes). Each start is marked with what it runs on, a session that never closed is said
on the next start, a hard crash (no Python error to catch) writes every thread's stack, and a window that stops
answering is written down with where it was stuck, then again when it answers."""
import os, subprocess, sys, tempfile, time
import tkinter as tk
import errors as E
import problems as P

log = os.path.join(tempfile.mkdtemp(), "tierlist.log")
# ---- sessions: started, closed; a start after one that never closed says so
assert P.start_session(log, "1.0.0") is False
text = open(log).read()
assert "=== started" in text and "Word Tierlister 1.0.0" in text and "Python" in text
P.end_session(log)
assert P.start_session(log, "1.0.0") is False                      # (the last one closed)
assert P.start_session(log, "1.0.0") is True                       # (that one never closed: a crash, a kill)
assert "ended without closing" in open(log).read()

# ---- a hard crash (Python itself failing, as a crash inside Tk would): every thread's stack is in the log
crash_log = os.path.join(tempfile.mkdtemp(), "tierlist.log")
code = ("import sys; sys.path.insert(0, {src!r}); import problems, faulthandler; "
        "problems.start_session({log!r}, 'x'); faulthandler._sigsegv()").format(
            src=os.path.join(_paths.ROOT, "src"), log=crash_log)
r = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=60)
assert r.returncode != 0
crashed = open(crash_log).read()
assert "Fatal Python error" in crashed and "Current thread" in crashed, crashed[-800:]
assert P.start_session(crash_log, "x") is True                     # (and the next start says it never closed)

# ---- a freeze: the window not answering is written down with where it was stuck, then that it answers again
root = tk.Tk(); root.withdraw()
E.watch_freezes(root, log, every_ms=100, limit=1.5)
for _ in range(10):
    root.update(); time.sleep(0.05)
before = len(open(log).read())


def stuck_here():
    time.sleep(3.2)                                                # (the window cannot answer meanwhile)


stuck_here()
for _ in range(40):
    root.update(); time.sleep(0.05)
after = open(log).read()[before:]
assert "has not responded for" in after and "stuck_here" in after, after[-1500:]
assert "responds again" in after
# a closed window stops the watch (closing is not a freeze), and the next window takes it over
root.destroy(); time.sleep(2.5)
assert "has not responded" not in open(log).read()[before + len(after):]
root2 = tk.Tk(); root2.withdraw()
E.watch_freezes(root2, log, every_ms=100, limit=1.5)
for _ in range(30):
    root2.update(); time.sleep(0.05)
assert "has not responded" not in open(log).read()[before + len(after):]
root2.destroy()
print("HEALTH OK")
