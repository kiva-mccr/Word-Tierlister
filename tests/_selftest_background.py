import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""background.py: work on a worker thread handed to the Tk thread (Task), timers that repeat (Repeat); both stop when
their widget is destroyed, a worker's exception reaches the Tk thread (failed, or Tk's error handler), never lost."""
import threading, time
import tkinter as tk
from background import Repeat, Task

root = tk.Tk(); root.withdraw()
errors = []
root.report_callback_exception = lambda kind, exc, tb: errors.append(exc)


def pump(secs=0.3):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        root.update(); time.sleep(0.01)


def until(ok, secs=5.0):
    end = time.monotonic() + secs
    while not ok():
        assert time.monotonic() < end
        root.update(); time.sleep(0.01)


# a Task's answer arrives on the Tk thread
seen = []
t = Task(root, lambda: threading.current_thread() is not threading.main_thread() and 42,
         done=lambda r: seen.append((r, threading.current_thread() is threading.main_thread())), ms=10)
until(lambda: seen)
assert seen == [(42, True)] and not t.running()
# a worker that raises: failed(exc), or, with none, Tk's error handler (the friendly dialog); never a silent stop
got = []
Task(root, lambda: 1 / 0, done=got.append, failed=lambda e: got.append(type(e).__name__), ms=10)
until(lambda: got)
assert got == ["ZeroDivisionError"]
Task(root, lambda: [][1], done=got.append, ms=10)
until(lambda: errors)
assert isinstance(errors[0], IndexError) and got == ["ZeroDivisionError"]
# wait(): the answer is held while it is true (a long job writes the save)
busy, held = [True], []
Task(root, lambda: "x", done=held.append, ms=10, wait=lambda: busy[0])
pump(0.2); assert held == []
busy[0] = False; until(lambda: held); assert held == ["x"]
# thread=False: the work and its answer at once, on this thread
now = []
Task(root, lambda: 7, done=now.append, thread=False); assert now == [7]
# cancel: never handed over
late = []
c = Task(root, lambda: time.sleep(0.1) or 1, done=late.append, ms=10); c.cancel(); pump(0.4); assert late == []

# Repeat: until fn says False, or stop()
n = []
Repeat(root, 10, lambda: n.append(1) or len(n) < 3)
until(lambda: len(n) == 3); pump(0.1); assert len(n) == 3
r, m = None, []
r = Repeat(root, 10, lambda: m.append(1)); until(lambda: m); r.stop(); k = len(m); pump(0.1); assert len(m) == k
# a call that raises is reported and the timer carries on
raised = []
def bad():
    raised.append(1)
    if len(raised) == 1:
        raise ValueError("once")
    return len(raised) < 3
Repeat(root, 10, bad); until(lambda: len(raised) == 3)
assert any(isinstance(e, ValueError) for e in errors)

# both stop with their widget: no "invalid command name" from a timer left on a destroyed window
win = tk.Toplevel(root); ticks, answers = [], []
rp = Repeat(win, 10, lambda: ticks.append(1)); Task(win, lambda: time.sleep(0.15) or 1, done=answers.append, ms=10)
until(lambda: ticks)
errors.clear()
job = rp.job
win.destroy(); k = len(ticks)
assert job not in root.tk.splitlist(root.tk.call("after", "info"))     # (cancelled, not left to fire a deleted command)
pump(0.4)
assert len(ticks) == k and answers == [] and not errors, errors
# made on a widget already gone: nothing happens
gone = tk.Frame(root); gone.destroy(); Repeat(gone, 10, lambda: ticks.append(1)); pump(0.1); assert len(ticks) == k
root.destroy()
print("BACKGROUND OK")
