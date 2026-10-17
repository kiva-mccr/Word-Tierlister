"""Motion engine for the word tier list (UI-4): easing, colour blending and a tiny animator.

Rules every animation here follows (they are the promises in the roadmap guardrails):
    * short: callers pass <= 250 ms, with ease-out so things settle gently;
    * never blocks input: starting a new animation under the same key, or pressing a key
      (App.on_key calls finish_all), jumps the running one straight to its end state;
    * nothing runs while idle, and nothing loops;
    * "Reduce motion" (View menu, saved) makes run() jump to the end state with no frames;
    * per-frame callbacks must be tiny and must never query the database.

tkinter has no transparency, so a "fade" is a colour blend toward the background (lerp_color).
"""
import time


def ease_out_cubic(t):
    """Fast start, gentle landing. t and the result are 0..1 (t is clamped)."""
    t = min(1.0, max(0.0, t))
    return 1.0 - (1.0 - t) ** 3


def lerp_color(c1, c2, t):
    """Blend two #RRGGBB colours: t=0 gives c1, t=1 gives c2 (t is clamped)."""
    t = min(1.0, max(0.0, t))
    a, b = c1.lstrip("#"), c2.lstrip("#")
    out = []
    for i in (0, 2, 4):
        x, y = int(a[i:i + 2], 16), int(b[i:i + 2], 16)
        out.append(round(x + (y - x) * t))
    return "#%02X%02X%02X" % tuple(out)


class Animator:
    """Runs short animations on the Tk event loop (about 60 frames a second).

    animator.run("word", 180, on_frame, on_done) calls on_frame(p) with p easing from 0 to 1
    (the last call is always exactly 1.0), then on_done(). Animations are identified by `key`;
    at most one runs per key. Callbacks run on the UI thread, so they may touch widgets.
    """
    FRAME_MS = 16

    def __init__(self, root, reduce_motion=False, clock=time.perf_counter):
        self.root = root
        self.reduce_motion = reduce_motion
        self.clock = clock                 # injectable so tests need not wait in real time
        self._running = {}                 # key -> {"start", "ms", "frame", "done", "ease", "job"}

    @property
    def busy(self):
        """True while any animation is running."""
        return bool(self._running)

    def run(self, key, ms, on_frame, on_done=None, ease=ease_out_cubic):
        """Start an animation. Any animation already running under `key` is finished first.

        With reduce_motion on (or ms <= 0) there are no frames: on_frame(1.0) and on_done()
        are called immediately.
        """
        self.finish(key)
        if self.reduce_motion or ms <= 0:
            on_frame(1.0)
            if on_done:
                on_done()
            return
        anim = {"start": self.clock(), "ms": ms, "frame": on_frame, "done": on_done,
                "ease": ease, "job": None}
        self._running[key] = anim
        on_frame(ease(0.0))
        anim["job"] = self.root.after(self.FRAME_MS, lambda: self._tick(key, anim))

    def _tick(self, key, anim):
        """One frame: advance, or finish when the time is up. Ignores stale timers."""
        if self._running.get(key) is not anim:
            return
        p = (self.clock() - anim["start"]) * 1000.0 / anim["ms"]
        if p >= 1.0:
            self.finish(key)
            return
        try:
            anim["frame"](anim["ease"](p))
        except Exception:
            self._running.pop(key, None)   # a broken frame must never leave a timer looping
            raise
        anim["job"] = self.root.after(self.FRAME_MS, lambda: self._tick(key, anim))

    def finish(self, key):
        """Jump the animation under `key` to its end state (on_frame(1.0), then on_done). No-op if none."""
        anim = self._running.pop(key, None)
        if anim is None:
            return
        if anim["job"] is not None:
            self.root.after_cancel(anim["job"])
        anim["frame"](anim["ease"](1.0))
        if anim["done"]:
            anim["done"]()

    def finish_all(self):
        """Finish everything now (called on every key press so input is never held up)."""
        for key in list(self._running):
            self.finish(key)

    def cancel_all(self):
        """Stop everything where it is, without end states. For shutting down."""
        for anim in self._running.values():
            if anim["job"] is not None:
                try:
                    self.root.after_cancel(anim["job"])
                except Exception:
                    pass
        self._running.clear()
