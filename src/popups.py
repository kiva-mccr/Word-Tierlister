"""The two small notes that float over the page: Toast (UI-11: a message that fades in, stays a moment and fades out;
each is its own, the newest on top) and Tooltip (UI-13: a hover note just below what it describes).
"""
import math
import tkinter as tk

from sizing import clamp_to_monitor, monitor_at
from smooth import SmoothCanvas
from theme import PALETTE
from ui_motion import HURRY_MS, lerp_color


class Toast(SmoothCanvas):
    """A small rounded message that fades in near the bottom of the page, stays a moment, and fades out (UI-11).

        toast = Toast(root, font("label"), animator=app.anim, on_gone=forget)
        toast.show("serendipity  ->  S", tint=("#FFB3C1", "#3D3A4B"), ms=1500, in_=app.center)

    It floats (place), so showing it never moves anything else. Each message is its own Toast: when a new
    one starts, the app calls hurry() on the older ones so they speed out of the way underneath it.
    fling() is the placement version: the message rises out of the word card, rests while it pales a
    little, then shrinks into a drop that flies to a landing point (its tier's bar), fading out.
    "Fades" are colour blends from the page colour (FADE_IN_MS / FADE_OUT_MS; they jump with Reduce
    motion). cget("text") is the message on screen ("" once it is gone); cget("font") its Font.
    on_gone(toast) is called when it has fully gone.
    """
    FADE_IN_MS, FADE_OUT_MS = 160, 220
    RISE_MS, SETTLE_MS, FLY_MS = 200, 250, 240        # fling(): rise out of the card, settle, fly to the bar

    def __init__(self, parent, font=None, animator=None, page_bg=None, on_gone=None):
        page = page_bg or PALETTE["bg"]
        super().__init__(parent, bd=0, highlightthickness=0, bg=page)
        self._font, self._anim, self._page = font, animator, page
        self._home = page              # the page colour (fling may borrow another backdrop for a moment)
        self._text, self._tint = "", (PALETTE["info"][0], PALETTE["info"][1])
        self._job = self._next = None  # the pending timer, and what it will start (hurry() starts it now)
        self._hurried = False
        self._wrap = 600
        self._gen = 0                  # bumped by every show / fling, so stale stages of an old one stop
        self._in = None
        self._on_gone = on_gone
        self._key = f"toast{id(self)}"

    def cget(self, key):
        if key == "text":
            return self._text
        if key == "font":
            return self._font
        return super().cget(key)

    def _later(self, ms, fn):
        self._next = fn
        self._job = self.after(ms, self._fire)

    def _fire(self):
        fn, self._job, self._next = self._next, None, None
        if fn:
            fn()

    def hurry(self):
        """A newer message has started: get out of the way quickly (within HURRY_MS of each stage),
        finishing the same way as normal (a fling still lands in its bar)."""
        if not self._text or self._hurried:
            return
        self._hurried = True
        if self._anim is not None:
            self._anim.hurry(self._key, HURRY_MS)
        if self._job is not None:
            self.after_cancel(self._job)
            self._fire()

    def show(self, text, tint=None, ms=3500, in_=None, wraplength=None):
        """Show `text` on a pill coloured `tint` = (background, text colour) for `ms` milliseconds."""
        self._reset()
        self._text = text
        self._tint = tint or self._tint
        if wraplength:
            self._wrap = wraplength
        self._draw()
        self._in = in_ or self.master
        self.place(in_=self._in, relx=0.5, rely=1.0, y=-10, anchor="s")   # near the bottom: never over the card
        self._on_top()
        self._fade(0.0, 1.0, self.FADE_IN_MS)
        self._later(ms, self.hide)

    WIGGLE_MS = 320

    def wiggle(self, ms=1500):
        """A little side-to-side "no" shake of the message on screen (a repeated refusal, like a zoom that cannot
        go further), and it stays `ms` longer. Nothing moves with Reduce motion; it only stays longer."""
        if not self._text or self._next is None:
            return False
        if self._job is not None:
            self.after_cancel(self._job)
        self._later(ms, self.hide)

        def frame(p):
            self.place_configure(x=int(round(7 * math.sin(p * 3 * 2 * math.pi) * (1 - p))))
        if self._anim is not None and not self._anim.reduce_motion:
            self._anim.run(f"wiggle{id(self)}", self.WIGGLE_MS, frame, lambda: self.place_configure(x=0),
                           ease=lambda t: t)
        return True

    def fling(self, text, tint, start_bottom, rest_bottom, target, hold_ms=550, in_=None, wraplength=None,
              under=None, on_arrive=None, clear=None):
        """The placement message (UI-11, UI-17): rise from its bottom edge at y=start_bottom until it is at
        y=rest_bottom, fading in; rest for hold_ms while paling slightly; then shrink into a small drop that
        flies to `target` = (x offset from the centre of `in_`, y of the landing point: it stops just above
        it), fading out, and call on_arrive(). y values are inside `in_`. Every stage is <= 250 ms; hurry()
        speeds it all up, a replaced one never arrives. With Reduce motion it stays put, then goes. Shrinking matters: tk has no
        transparency, so a full-size pill would be an opaque box passing over the chart.
        `under(x0, y0, x1, y1)` returns the colour behind the toast's rectangle (inside `in_`); the toast takes
        that colour as its own background and blends toward it. It is asked every frame, with the whole
        rectangle: a backdrop picked by height alone painted a white box over the page beside the card.
        `clear` (a y inside `in_`, the top of the tallest bar): the drop flies in an arc over that height and
        drops onto its landing point from above, so it never crosses a bar (being opaque, its corners showed
        as a pale square on the bars it brushed)."""
        self._reset()
        gen = self._gen
        self._text, self._tint = text, tint
        if wraplength:
            self._wrap = wraplength
        self._draw()
        self._in = in_ or self.master
        self._on_top()
        key = self._key
        alive = lambda: gen == self._gen
        w0, h0 = int(self.cget("width")), int(self.cget("height"))
        from_y, to_y = start_bottom - h0, rest_bottom - h0

        def backdrop(x, y, w, h):
            if under is not None:
                cx = self._in.winfo_width() / 2 + x
                c = under(cx - w / 2, y, cx + w / 2, y + h)
                if c != self._page:
                    self._page = c
                    super(Toast, self).configure(bg=c)

        def rise(p):
            if alive():
                y = from_y + (to_y - from_y) * p
                backdrop(0, y, w0, h0)
                self._put(0, y)
                self._paint(p)

        def settle(p):
            if alive():
                self._paint(1.0 - 0.3 * p)

        y0 = to_y + h0 / 2

        def path(p, h):
            """Where the drop's middle is, for its size h. The drop is a little opaque window 2 px bigger than
            itself, so its bottom stays a pixel clear of a bar's top (and the bar's soft edge above that): it
            ends resting just above its bar. With `clear` it first rises just above the tallest bar (by its own
            size: it is shrinking), crosses to straight above its bar, then drops onto it."""
            land = target[1] - h / 2 - 4
            if clear is None:
                return target[0] * p, y0 + (land - y0) * p
            a = min(1.0, p / 0.7)
            x = target[0] * a * a * (3 - 2 * a)                      # across (eased in and out)
            top = min(y0, clear - h / 2 - 4)
            if p < 0.7:
                b = min(1.0, p / 0.45)
                return x, y0 + (top - y0) * (1 - (1 - b) ** 2)      # up first (eased out), ahead of across
            c = (p - 0.7) / 0.3
            return x, top + (land - top) * c * c                     # then it drops (eased in)

        def fly(p):
            if alive():
                scale = 1.0 - 0.85 * p                         # shrinks to a small drop
                # ...and narrows to a round drop by the time its text has gone (p = 0.4): a long word's pill
                # stayed wide all the way and covered the chart bars as an opaque box
                h = max(4, h0 * scale)
                w = max(4, h + (w0 * scale - h) * max(0.0, 1.0 - p * 2.5))
                x, y_mid = path(p, h)
                backdrop(x, y_mid - h / 2, w, h)
                self._resize(w, h, text_alpha=max(0.0, 1.0 - p * 2.5))
                self._put(x, y_mid - h / 2)
                self._paint(0.7 * (1.0 - 0.6 * p), text=max(0.0, 0.7 - p * 2.5))

        def gone():
            if alive():
                self._gone()
                if on_arrive is not None:
                    on_arrive()

        def to_fly():
            if alive():
                self._anim_run(key, HURRY_MS if self._hurried else self.FLY_MS, fly, gone)

        def after_rise():
            if alive():
                if self._hurried:
                    to_fly()
                    return
                self._later(hold_ms, to_fly)
                self._anim_run(key, self.SETTLE_MS, settle)
        self._anim_run(key, HURRY_MS if self._hurried else self.RISE_MS, rise, after_rise)

    def _gone(self):
        self._text = ""
        self.place_forget()
        self._page = self._home
        super().configure(bg=self._home)
        if self._on_gone is not None:
            self._on_gone(self)

    def _anim_run(self, key, ms, frame, done=None):
        if self._anim is None:
            frame(1.0)
            if done:
                done()
        else:
            self._anim.run(key, ms, frame, done)

    def _reset(self):
        """Stop whatever the previous message was doing (its pending stages see a new generation)."""
        self._gen += 1
        self._hurried = False
        if self._page != self._home:
            self._page = self._home
            super().configure(bg=self._home)
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = self._next = None
        if self._anim is not None:
            self._anim.finish(self._key)

    def _put(self, x, y):
        self.place(in_=self._in, relx=0.5, rely=0, x=int(x), y=int(y), anchor="n")

    def _on_top(self):
        """Raise above everything once, when a message starts (not every frame: then a newer message,
        started later, stays above an older one still flying out)."""
        self.tk.call("raise", self._w)          # (Canvas.lift raises canvas items, not the widget)

    def hide(self):
        """Fade out now (also what happens when the time is up)."""
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = self._next = None
        if not self._text:
            return
        gen = self._gen
        self._fade(1.0, 0.0, HURRY_MS if self._hurried else self.FADE_OUT_MS,
                   lambda: gen == self._gen and self._gone())

    def _draw(self):
        self.delete("all")
        f = self._font
        line = f.metrics("linespace") if f else 16
        padx, pady = int(line * 1.1), int(line * 0.45)
        t = self.create_text(0, 0, text=self._text, font=f, width=self._wrap, justify="center", anchor="n",
                             tags="text")
        x1, y1, x2, y2 = self.bbox(t)
        w = min(x2 - x1, self._wrap) + 2 * padx
        h = (y2 - y1) + 2 * pady
        self._line, self._pady = line, pady
        super().configure(width=w + 2, height=h + 2)
        self.round_rect(1, 1, w, h, min(h // 2, line), tags="pill")
        self.coords(t, 1 + w / 2, 1 + pady)
        self.tag_raise("text")

    def _resize(self, w, h, text_alpha=1.0):
        """Redraw the pill at another size (the flying drop); the text stays centred, then fades away."""
        w, h = int(w), int(h)
        super().configure(width=w + 2, height=h + 2)
        self.round_rect_coords("pill", 1, 1, w, h, r=max(2, min(h // 2, self._line)))
        self.coords("text", 1 + w / 2, 1 + max(0, (h - self._line) / 2))
        self.itemconfigure("text", state="normal" if text_alpha > 0 else "hidden")

    def _paint(self, a, text=None):
        bg, fg = self._tint
        try:
            self.itemconfigure("pill", fill=lerp_color(self._page, bg, a),
                               outline=lerp_color(self._page, lerp_color(bg, PALETTE["text"], 0.12), a))
            self.itemconfigure("text", fill=lerp_color(self._page, fg, a if text is None else text))
        except tk.TclError:
            pass

    def _fade(self, a, b, ms, done=None):
        if self._anim is None:
            self._paint(b)
            if done:
                done()
            return
        self._anim.run(self._key, ms, lambda p: self._paint(a + (b - a) * p), done)


class Tooltip:
    """A small hover note (UI-13 / UI-15 / UI-33): appears after DELAY_MS of hovering, just below what it
    describes, and stays there (only its text changes over another part of the same widget); it goes when the
    pointer leaves or a key or button is pressed.

        Tooltip(widget, lambda e: "1,234 words")    # text_fn(event) -> text, or None for "nothing here"
        Tooltip(label, text_fn, side="right")        # beside it instead (when something sits below it)
        Tooltip(tick, text_fn, wrap=360)             # a longer note: wrapped at 360 pixels

    text_fn gets the Motion event, so one tooltip can say different things over different parts of a canvas
    (each segment of the progress bar). It looks like the rest of the theme: a rounded card in the faint lilac
    with a hairline, in the shared font. (tk windows cannot be see-through, so the corners are painted in the
    page colour.)
    """
    DELAY_MS = 350

    def __init__(self, widget, text_fn, font=None, side="below", wrap=0):
        self.widget, self.text_fn, self.font, self.side, self.wrap = widget, text_fn, font, side, wrap
        self.win = self._canvas = None
        self._text = ""
        self._job = None
        self._last = None
        widget.bind("<Motion>", self._on_motion, add="+")
        widget.bind("<Leave>", lambda e: self.hide(), add="+")
        widget.bind("<ButtonPress>", lambda e: self.hide(), add="+")

    @property
    def text(self):
        """What is showing now ("" when hidden)."""
        return self._text if self.win is not None else ""

    def _on_motion(self, e):
        self._last = e
        text = self.text_fn(e)
        if not text:
            self.hide()
            return
        if self.win is not None:
            if text != self._text:
                self._draw(text)                  # same place, new words (UI-33: it does not chase the pointer)
            return
        if self._job is None:
            self._job = self.widget.after(self.DELAY_MS, self._show)

    def _show(self):
        self._job = None
        e = self._last
        text = self.text_fn(e) if e is not None else None
        if not text:
            return
        win = self.win = tk.Toplevel(self.widget, bg=PALETTE["bg"])
        win.withdraw()                    # drawn and placed first: no blank box flashing at the corner
        win.overrideredirect(True)
        # (not "-topmost": that kept it in front of other programs after switching away, UI-43)
        self._canvas = SmoothCanvas(win, bd=0, highlightthickness=0, bg=PALETTE["bg"])
        self._canvas.pack()
        self._draw(text)
        self._place(e)
        win.deiconify()

    def _draw(self, text):
        self._text = text
        c, f = self._canvas, self.font
        c.delete("all")
        line = f.metrics("linespace") if f else 16
        pad_x, pad_y = max(8, line // 2), max(4, line // 4)
        t = c.create_text(pad_x + 1, pad_y + 1, text=text, font=f, fill=PALETTE["text"], anchor="nw",
                          justify="left", width=self.wrap, tags="text")
        x1, y1, x2, y2 = c.bbox(t)
        w, h = x2 + pad_x + 1, y2 + pad_y + 1
        c.configure(width=w + 1, height=h + 1)
        c.round_rect(1, 1, w, h, min(10, h // 2), fill=PALETTE["surface2"], outline=PALETTE["border"], tags="card")
        c.tag_raise("text")

    def show_at(self, e):
        """Show now for this event (tests)."""
        self._last = e
        self._show()

    def _place(self, e):
        """Just below the widget, starting near the pointer (or just right of it, centred), kept on the screen."""
        self.win.update_idletasks()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        if self.side == "right":
            x = self.widget.winfo_rootx() + self.widget.winfo_width() + 8
            y = self.widget.winfo_rooty() + (self.widget.winfo_height() - h) // 2
        else:
            x = self.widget.winfo_rootx() + e.x - 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        at = (self.widget.winfo_rootx(), self.widget.winfo_rooty())
        mx, my, mw, mh = monitor_at(self.widget, *at)
        if y + h > my + mh:
            y = self.widget.winfo_rooty() - h - 6           # no room below: above it instead
        x, y = clamp_to_monitor(self.widget, x, y, w, h, at=at)
        self.win.geometry(f"+{x}+{y}")

    def hide(self):
        if self._job is not None:
            self.widget.after_cancel(self._job)
            self._job = None
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = self._canvas = None
