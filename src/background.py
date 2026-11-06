"""Work on a worker thread handed back to the Tk thread, and timers that stop with their window.

Tk may only be touched from the thread that runs its event loop, so work that takes a while (asking GitHub or
Syncthing, reading Wiktionary, reshuffling the queue, running a developer tool) runs on a worker thread and the window
polls for its answer. Before this module, each place wrote that poll itself, with its own flags; an exception in the
worker left some of them polling for ever (a sync round never ended, "Checking..." stayed), and a timer left on a
window that had closed fired a deleted command ("invalid command name ...reload").

    Task(widget, work, done=..., failed=..., ms=100, wait=None)
        work() on a worker thread (never touching Tk); then, on the Tk thread, done(result), or failed(exc) when it
        raised. With no `failed` the exception goes to Tk's error handler (errors.py: the log and the friendly
        dialog), never lost. `wait()`: while it is true the answer is held (a long job is writing the save).
    Repeat(widget, ms, fn)
        fn() on the Tk thread every `ms` until it returns False or stop() is called.

Both stop when `widget` is destroyed: their pending timer is cancelled, and nothing is called after.
"""
import threading
import tkinter as tk


class Repeat:
    """fn() on the Tk thread every `ms` (the first after `first` ms, by default `ms`) until it returns False, stop()
    is called or `widget` is destroyed. A call that raises still schedules the next (the error goes to Tk's handler)."""

    def __init__(self, widget, ms, fn, first=None):
        self.widget, self.ms, self.fn = widget, ms, fn
        self.job = None
        self.stopped = False
        try:
            widget.bind("<Destroy>", self._destroyed, add="+")
        except tk.TclError:                 # (already gone)
            self.stopped = True
            return
        self._schedule(ms if first is None else first)

    def _schedule(self, ms):
        if self.stopped:
            return
        try:
            self.job = self.widget.after(ms, self._run)
        except tk.TclError:
            self.stopped = True

    def _run(self):
        self.job = None
        if self.stopped:
            return
        again = True
        try:
            again = self.fn() is not False
        finally:
            if again:
                self._schedule(self.ms)
            else:
                self.stopped = True

    def stop(self):
        self.stopped = True
        if self.job is not None:
            try:
                self.widget.after_cancel(self.job)
            except (tk.TclError, ValueError):
                pass
            self.job = None

    def _destroyed(self, e):
        if e.widget is self.widget:
            self.stop()


class Task:
    """work() on a worker thread, its answer handed to the Tk thread (see the module's note). `thread=False` runs
    work() at once on this thread and hands the answer over at once too (tests, and callers that run it inline)."""

    def __init__(self, widget, work, done=None, failed=None, ms=100, wait=None, thread=True):
        self.done_fn, self.failed_fn, self.wait = done, failed, wait
        self.finished = False                # the work has returned (or raised)
        self.delivered = False               # done / failed has been called
        self.result = self.error = None
        self.repeat = None
        if not thread:
            self._work(work)
            if self._check() is not False:   # (held by wait(): handed over once it lets go)
                self.repeat = Repeat(widget, ms, self._check)
            return
        threading.Thread(target=self._work, args=(work,), daemon=True).start()
        self.repeat = Repeat(widget, ms, self._check)

    def _work(self, work):                   # (the worker thread: no Tk here)
        try:
            self.result = work()
        except BaseException as exc:         # (handed to the Tk thread, never lost on the worker's)
            self.error = exc
        self.finished = True

    def running(self):
        return not self.delivered

    def _check(self):
        if self.delivered:
            return False
        if not self.finished or (self.wait is not None and self.wait()):
            return True
        self.delivered = True
        if self.error is not None:
            if self.failed_fn is None:
                raise self.error
            self.failed_fn(self.error)
        elif self.done_fn is not None:
            self.done_fn(self.result)
        return False

    def cancel(self):
        """Never hand the answer over (the work itself carries on to its end: a thread cannot be stopped)."""
        self.delivered = True
        if self.repeat is not None:
            self.repeat.stop()
