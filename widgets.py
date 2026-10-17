"""Small reusable tk widgets: RoundButton (UI-5), WordCard (UI-6), TierRow (UI-7) and friends.

Both are canvases drawn with smoothed rounded corners. Canvas (not tk.Button or ttk) because the
colours then look the same on macOS, Windows and Linux, and corners can be round everywhere.
After a shared Font object is resized, call refresh_widgets(window) so they re-measure.
"""
import tkinter as tk
import tkinter.font as tkfont

from theme import PALETTE, TIER_COLORS
from ui_motion import lerp_color

HOVER_MS = 120          # colour fade when the pointer enters or leaves
DIP = 2                 # pixels the button sinks while pressed
_CUSTOM = ("text", "hint", "font", "wraplength", "bg", "fg")


def _rounded_points(x1, y1, x2, y2, r):
    """Polygon outline of a rounded rectangle; drawn with smooth=True it gives round corners."""
    return [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r,
            x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1]


class RoundButton(tk.Canvas):
    """A rounded, pastel button with a hover tint, a pressed 'dip', a disabled look and a key hint.

        RoundButton(parent, "Better", command, bg=PALETTE["better"], hint="Up / B", animator=app.anim)

    * `hint` is a small muted caption under the text (usually the keyboard shortcut).
    * It follows the Label-style options the app already uses: .config(text=, hint=, font=,
      wraplength=, bg=, fg=) and .cget("text"); size comes from the text plus padx / pady, and the
      shape fills whatever space the layout gives it (pair cards stretch).
    * The command runs when the mouse is released over the button, or from invoke().
    * set_enabled(False) greys it out; it stays visible but ignores clicks.
    * refresh() re-measures after the shared Font object was resized (call it after a font change).
    * With an Animator the hover tint fades over HOVER_MS; without one (or with reduce motion) it jumps.
    * `lift` (pixels, default 0): on hover the button rises by that much over a soft shadow (UI-7).
    """

    def __init__(self, parent, text, command, bg=PALETTE["neutral"], fg=PALETTE["text"], font=None,
                 padx=14, pady=8, hint=None, wraplength=0, radius=14, animator=None, canvas_bg=None, lift=0):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["bg"],
                         cursor="hand2", takefocus=0)
        self._command = command
        self._text, self._hint, self._wrap = text, hint, wraplength
        self._fill, self._fg = bg, fg
        self._padx, self._pady, self._radius = padx, pady, radius
        self._lift, self._lifted = lift, False
        self._anim = animator
        self._font = font if isinstance(font, tkfont.Font) else tkfont.Font(root=self, font=font or "TkDefaultFont")
        self._hint_font = tkfont.Font(root=self, font=self._font)
        self._enabled, self._hover, self._pressed = True, False, False
        self._look = self._target()          # the colours currently drawn: (fill, outline, outline width, text colour)
        self._draw()
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda e: self._draw())

    # ---- options ------------------------------------------------------------------------------
    def configure(self, cnf=None, **kw):
        """Label-style options (text, hint, font, wraplength, bg, fg) plus the normal Canvas ones."""
        kw = dict(cnf or {}, **kw)
        mine = {k: kw.pop(k) for k in _CUSTOM if k in kw}
        if kw:
            super().configure(**kw)
        if mine:
            if "text" in mine:
                self._text = mine["text"]
            if "hint" in mine:
                self._hint = mine["hint"]
            if "wraplength" in mine:
                self._wrap = mine["wraplength"]
            if "bg" in mine:
                self._fill = mine["bg"]
            if "fg" in mine:
                self._fg = mine["fg"]
            if "font" in mine:
                f = mine["font"]
                self._font = f if isinstance(f, tkfont.Font) else tkfont.Font(root=self, font=f)
            self._look = self._target()
            self._draw()

    config = configure

    def cget(self, key):
        return {"text": self._text, "hint": self._hint, "wraplength": self._wrap, "bg": self._fill,
                "fg": self._fg, "font": self._font}[key] if key in _CUSTOM else super().cget(key)

    def set_enabled(self, enabled):
        """Grey out / re-enable (a disabled button stays visible but ignores clicks)."""
        self._enabled = enabled
        if not enabled:
            self._pressed = self._hover = False
            self._set_lift(False)
        self.tk.call(str(self), "configure", "-cursor", "hand2" if enabled else "arrow")
        self._go(self._target())

    @property
    def enabled(self):
        return self._enabled

    def refresh(self):
        """Re-measure and redraw (after the Font object it uses was resized)."""
        self._draw()

    # ---- looks ----------------------------------------------------------------------------------
    def _target(self):
        """(fill, outline, outline width, text colour) for the current state."""
        fill, fg = self._fill, self._fg
        edge = lerp_color(fill, PALETTE["text"], 0.14)
        if not self._enabled:
            return (lerp_color(fill, PALETTE["bg"], 0.6), lerp_color(edge, PALETTE["bg"], 0.6), 1, PALETTE["disabled"])
        if self._pressed:
            return (lerp_color(fill, PALETTE["text"], 0.10), edge, 1, fg)
        if self._hover:
            return (lerp_color(fill, "#FFFFFF", 0.45), PALETTE["accent"], 2, fg)
        return (fill, edge, 1, fg)

    def _go(self, target):
        """Move the drawn colours to `target`, fading when an Animator is available."""
        start = self._look
        if self._anim is None or self._anim.reduce_motion:
            self._look = target
            self._paint()
            return

        def frame(p):
            self._look = (lerp_color(start[0], target[0], p), lerp_color(start[1], target[1], p),
                          target[2], lerp_color(start[3], target[3], p))
            self._paint()
        try:
            self._anim.run(f"rb{id(self)}", HOVER_MS, frame)
        except tk.TclError:
            pass

    def _paint(self):
        """Apply self._look to the items (colours only; geometry is _draw)."""
        fill, edge, width, fg = self._look
        try:
            self.itemconfigure("shape", fill=fill, outline=edge, width=width)
            self.itemconfigure("label", fill=fg)
            self.itemconfigure("hint", fill=lerp_color(fg, fill, 0.3))
        except tk.TclError:
            pass

    def _draw(self):
        """Measure the text, request a size, and draw the shape and labels to fill the current size."""
        self.delete("all")
        wrap = self._wrap if self._wrap > 0 else 0
        s = self._font.cget("size")
        hs = int(round(s * 0.72))
        self._hint_font.configure(family=self._font.cget("family"), weight="normal",
                                  size=max(7, hs) if s > 0 else min(-9, hs))
        label = self.create_text(0, 0, text=self._text, font=self._font, width=wrap, justify="center",
                                 tags=("label", "body"), anchor="n")
        lb = self.bbox(label)
        tw, th = (lb[2] - lb[0], lb[3] - lb[1]) if lb else (0, 0)
        hw = hh = 0
        if self._hint:
            h = self.create_text(0, 0, text=self._hint, font=self._hint_font, width=wrap, justify="center",
                                 tags=("hint", "body"), anchor="n")
            hb = self.bbox(h)
            hw, hh = hb[2] - hb[0], hb[3] - hb[1]
        gap = 1 if self._hint else 0
        need_w = max(tw, hw) + 2 * self._padx
        lift = self._lift
        need_h = th + gap + hh + 2 * self._pady + DIP + 1 + lift
        super().configure(width=need_w, height=need_h)
        w, h = max(self.winfo_width(), need_w), max(self.winfo_height(), need_h)   # (1 x 1 before it is laid out)
        body_h = h - DIP - 1 - lift
        r = max(4, min(self._radius, body_h // 2))
        if lift:     # the shadow stays put; the body sits on it and rises off it on hover
            self.create_polygon(_rounded_points(2, 1 + lift + 1, w - 2, 1 + lift + body_h, r), smooth=True,
                                fill=super().cget("bg"), outline="", tags="shadow")
        self.create_polygon(_rounded_points(1, 1 + lift, w - 1, 1 + lift + body_h, r), smooth=True, tags=("shape", "body"))
        top = 1 + lift + (body_h - (th + gap + hh)) / 2
        self.coords(label, w / 2, top)
        if self._hint:
            self.coords("hint", w / 2, top + th + gap)
        self.tag_raise("label")
        self.tag_raise("hint")
        self._lifted = False
        self._paint()
        if self._pressed:
            self.move("body", 0, DIP)
        elif self._hover:
            self._set_lift(True)

    def _set_lift(self, up):
        """Raise the body off its shadow (hover) or set it back down. Only for buttons made with lift=."""
        if not self._lift or up == self._lifted:
            return
        self._lifted = up
        self.move("body", 0, -self._lift if up else self._lift)
        self.itemconfigure("shadow", fill=PALETTE["shadow"] if up else super().cget("bg"))

    # ---- mouse ----------------------------------------------------------------------------------
    def _set_hover(self, on):
        self._hover = on and self._enabled
        if not self._pressed:
            self._go(self._target())
            self._set_lift(self._hover)

    def _on_press(self, _e):
        if not self._enabled:
            return
        self._pressed = True
        self._set_lift(False)
        self._go(self._target())
        self.move("body", 0, DIP)

    def _on_release(self, e):
        if not self._pressed:
            return
        self._pressed = False
        self.move("body", 0, -DIP)
        self._set_lift(self._hover)
        self._go(self._target())
        if 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
            self._command()

    def invoke(self):
        """Run the command as if clicked (with the pressed look, for keyboard shortcuts). No-op if disabled."""
        if self._enabled:
            self.flash()
            self._command()

    def flash(self, ms=110):
        """Show the pressed look briefly (used to give keyboard shortcuts visible feedback)."""
        if not self._enabled or self._pressed:
            return
        self._pressed = True
        self._set_lift(False)
        self._go(self._target())
        self.move("body", 0, DIP)

        def undo():
            if self._pressed:
                self._pressed = False
                try:
                    self.move("body", 0, -DIP)
                    self._set_lift(self._hover)
                    self._go(self._target())
                except tk.TclError:
                    pass
        self.after(ms, undo)


class TierRow(tk.Frame):
    """The six tier pills S..F, each with its key hint (1-6), a hover lift and the pressed dip (UI-7).

        row = TierRow(parent, ["S", "A", "B", "C", "D", "F"], on_pick, font("tier"), animator=app.anim)
        row.press(2)        # what the "3" key does: the B pill dips, then on_pick(2) runs

    `buttons` are the RoundButtons (App.tier_btns), in tier order. on_pick(tier) runs on a click too.
    """

    def __init__(self, parent, tiers, on_pick, font=None, animator=None, colors=TIER_COLORS, gap=5):
        super().__init__(parent, bg=PALETTE["bg"])
        self.buttons = []
        for t, name in enumerate(tiers):
            b = RoundButton(self, name, lambda t=t: on_pick(t), bg=colors[t], font=font, padx=22, pady=10,
                            hint=str(t + 1), radius=999, animator=animator, lift=3)
            b.grid(row=0, column=t, padx=gap)
            self.buttons.append(b)
        self._on_pick = on_pick

    def press(self, tier):
        """The keyboard version of a click: the action runs first (input is never delayed), then the pill
        shows its pressed dip. Out-of-range tiers and disabled pills do nothing."""
        if 0 <= tier < len(self.buttons) and self.buttons[tier].enabled:
            self._on_pick(tier)
            try:
                self.buttons[tier].flash()
            except tk.TclError:
                pass

    def set_enabled(self, enabled):
        for b in self.buttons:
            b.set_enabled(enabled)


class WordCard(tk.Canvas):
    """The word being sorted: big text on a soft rounded white card with a faint shadow, and a muted
    sub-line under it (frequency rank, "skipped", "compound").

        card = WordCard(parent, font("word"), font("body"))
        card.set("serendipity", "frequency rank #4,321")

    * The card is at least as wide as `min_chars` letters of the word font, so it does not jump in
      width from word to word; longer words widen it (up to `wraplength`, then they wrap).
    * `word` / `sub` read the current text. configure(wraplength=) sets where text wraps.
    * refresh() re-measures after the shared fonts were resized.
    """
    SHADOW = 4
    MIN_CHARS = 6

    def __init__(self, parent, word_font, sub_font, wraplength=0, radius=26, canvas_bg=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["bg"])
        self._wfont, self._sfont = word_font, sub_font
        self._word, self._sub, self._wrap = "", "", wraplength
        self._radius = radius
        self.bind("<Configure>", lambda e: self._draw())
        self._draw()

    @property
    def padx(self):
        """Side padding in pixels; it follows the word font, so the card shrinks with the text."""
        return int(self._wfont.metrics("linespace") * 0.6)

    @property
    def _pady(self):
        return int(self._wfont.metrics("linespace") * 0.28)

    @property
    def word(self):
        return self._word

    @property
    def sub(self):
        return self._sub

    def set(self, word, sub=""):
        """Show `word` with the muted line `sub` under it."""
        self._word, self._sub = word, sub
        self._draw()

    def configure(self, cnf=None, **kw):
        kw = dict(cnf or {}, **kw)
        if "wraplength" in kw:
            self._wrap = kw.pop("wraplength")
            self._draw()
        if kw:
            super().configure(**kw)

    config = configure

    def cget(self, key):
        if key == "wraplength":
            return self._wrap
        if key == "font":
            return self._wfont
        return super().cget(key)

    def refresh(self):
        self._draw()

    @staticmethod
    def _text_width(text, fnt, wrap):
        """Width of `text` on one line, capped at the wrap width (a wrapped canvas text reports the
        full wrap width as its box, which would make every card as wide as the window)."""
        natural = fnt.measure(text)
        return min(natural, wrap) if wrap else natural

    def _draw(self):
        self.delete("all")
        wrap = self._wrap if self._wrap > 0 else 0
        word = self.create_text(0, 0, text=self._word, font=self._wfont, fill=PALETTE["text"], width=wrap,
                                justify="center", anchor="n", tags="word")
        wb = self.bbox(word)
        th = wb[3] - wb[1] if wb else 0
        tw = self._text_width(self._word, self._wfont, wrap)
        sw = sh = 0
        if self._sub:
            sub = self.create_text(0, 0, text=self._sub, font=self._sfont, fill=PALETTE["muted"], width=wrap,
                                   justify="center", anchor="n", tags="sub")
            sb = self.bbox(sub)
            sh = sb[3] - sb[1]
            sw = self._text_width(self._sub, self._sfont, wrap)
        gap = int(self._sfont.metrics("linespace") * 0.4) if self._sub else 0
        min_w = self._wfont.measure("n" * self.MIN_CHARS)
        need_w = max(tw, sw, min_w) + 2 * self.padx + self.SHADOW
        need_h = th + gap + sh + 2 * self._pady + self.SHADOW
        super().configure(width=need_w, height=need_h)
        w, h = max(self.winfo_width(), need_w), max(self.winfo_height(), need_h)
        bw, bh = w - self.SHADOW, h - self.SHADOW
        r = max(6, min(self._radius, bh // 2))
        self.create_polygon(_rounded_points(1 + self.SHADOW, 1 + self.SHADOW, bw + self.SHADOW - 1, bh + self.SHADOW - 1, r),
                            smooth=True, fill=PALETTE["shadow"], outline="", tags="shadow")
        self.create_polygon(_rounded_points(1, 1, bw - 1, bh - 1, r), smooth=True, fill=PALETTE["surface"],
                            outline=PALETTE["border"], tags="card")
        top = (bh - (th + gap + sh)) / 2
        self.coords(word, bw / 2, top)
        if self._sub:
            self.coords("sub", bw / 2, top + th + gap)
        self.tag_raise("word")
        self.tag_raise("sub")


def refresh_widgets(widget):
    """Re-measure every RoundButton and WordCard under `widget` (after shared fonts were resized)."""
    for child in widget.winfo_children():
        if isinstance(child, (RoundButton, WordCard)):
            child.refresh()
        else:
            refresh_widgets(child)
