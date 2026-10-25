"""Small reusable tk widgets: RoundButton (UI-5), WordCard (UI-6), TierRow (UI-7) and friends.

Both are canvases drawn with smoothed rounded corners. Canvas (not tk.Button or ttk) because the
colours then look the same on macOS, Windows and Linux, and corners can be round everywhere.
After a shared Font object is resized, call refresh_widgets(window) so they re-measure.
"""
import math
import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from constants import QUEUE_AXIS, QUEUE_MEDIAN, queue_weight
from rudeness import GLOSS_KEY
from fonts import font
from sizing import clamp_to_monitor, keep_on_screen, monitor_at, place_dialog
from smooth import ICONS, SmoothCanvas, curve_image
from theme import PALETTE, TIER_COLORS, TIER_TEXT, ink_on, is_light
from ui_motion import HURRY_MS, lerp_color

HOVER_MS = 120          # colour fade when the pointer enters or leaves
DIP = 2                 # pixels the button sinks while pressed
_CUSTOM = ("text", "hint", "font", "wraplength", "bg", "fg", "censor")
UNSMEAR_MS = 260        # a censored word un-smears this fast under the pointer (ST-6), and smears again as fast
SMEAR_SPREAD = 0.625    # how far a censored word is smeared sideways, in letter widths (the user's pick)
SMEAR_TONE = 0.55       # how pale the smear is (0 = the text colour, 1 = the card)
SMEAR_BODY = 0.48       # the band filling the letters' body, in em up from the baseline (about the x-height of
                        # the roundest fonts used; a more generous one would show a flat top over round letters)
_TEXT_OPTS = ("text", "font", "anchor", "justify", "width")


def smear_items(canvas, item, ink, paper, amount=1.0, tags=()):
    """Smear the text `item` sideways (ST-6): copies of it side by side over SMEAR_SPREAD letter widths, in one
    pale tone (so none of them stays crisp on top), cut off straight at its first and last letter by strips in the
    `paper` colour. A band in the same tone fills the letters' body behind them (else the space inside an "e", the
    gaps between the curves of "ss" and the open side of a last "c" show as white slivers and notches). `amount`
    (0..1) narrows it and darkens it toward `ink` (un-smearing; the band fades out). Tk cannot blur, so the copies
    are plain canvas text: cheap enough to redraw every frame. Returns nothing; the items carry `tags`."""
    c = canvas
    box = c.bbox(item)
    if not box:
        return
    x, y = c.coords(item)[:2]
    opts = {k: c.itemcget(item, k) for k in _TEXT_OPTS}
    half = SMEAR_SPREAD * float(c.tk.call("font", "measure", opts["font"], "n")) / 2 * amount
    col = lerp_color(ink, paper, SMEAR_TONE * amount)
    size = float(c.tk.call("font", "actual", opts["font"], "-size"))
    em = -size if size < 0 else size * float(c.tk.call("tk", "scaling"))
    lines = max(1, round((box[3] - box[1]) / float(c.tk.call("font", "metrics", opts["font"], "-linespace"))))
    band = max(0.0, (amount - 0.75) / 0.25)    # gone a quarter of the way into un-smearing (else a pale box shows
    if lines == 1 and band > 0:                 # behind the letters closing in); not on a word wrapped over two lines
        base = box[1] + float(c.tk.call("font", "metrics", opts["font"], "-ascent"))
        c.create_rectangle(box[0], base - SMEAR_BODY * em, box[2], base - 0.02 * em, outline="",
                           fill=lerp_color(paper, col, band), tags=tags)
    steps = max(4, int(2 * half))              # (a pixel apart at most: wider gaps show as combs on small text)
    # one copy per whole pixel (Tk draws text at whole pixels: copies landing on the same one stack up and look
    # bold on small text, reported in the definitions pane); near the end the side copies fade into the paper and
    # the middle one, drawn last, becomes the word itself, so the last frames end where the plain word starts
    offsets = sorted({round(-half + 2 * half * k / steps) for k in range(steps + 1)} - {0}, key=abs, reverse=True)
    side = lerp_color(paper, col, min(1.0, max(0.0, (half - 0.5) / 1.5)))   # (faded out by half a pixel apart)
    for dx in offsets:
        c.create_text(x + dx, y, fill=side, tags=tags, **opts)
    c.create_text(x, y, fill=col, tags=tags, **opts)
    room = int(half) + 3
    for x0, x1 in ((box[0] - room, box[0]), (box[2], box[2] + room)):
        c.create_rectangle(x0, box[1], x1, box[3], fill=paper, outline="", tags=tags)


class Unsmear:
    """A censored word (ST-6) on one of our canvases: its text item is hidden behind a sideways smear
    (smear_items); `clear` (0 = smeared, 1 = the word itself) eases toward 1 while the pointer is over it, the
    smear narrowing and darkening into the word, and back when it leaves. The canvas calls place(text item, word,
    ink, paper) after drawing the word, paint() after moving or recolouring it, and hover(on, animator) from its
    pointer events."""

    def __init__(self, canvas, tag):
        self.canvas, self.tag = canvas, tag
        self.word = None
        self.clear, self._target = 0.0, 0.0
        self._item, self._ink, self._paper = None, None, None

    def place(self, item, word, ink, paper):
        """Smear text `item` (showing `word`), or nothing when `word` is None."""
        self.canvas.delete(self.tag)
        self._item, self.word, self._ink, self._paper = item, word, ink, paper
        if word is None:
            self.clear = self._target = 0.0
            return
        self.paint()

    def paint(self):
        c = self.canvas
        if self.word is None or self._item is None:
            return
        try:
            c.delete(self.tag)
            if self.clear >= 1.0:
                c.itemconfigure(self._item, state="normal", fill=self._ink)
                return
            c.itemconfigure(self._item, state="normal")         # (a hidden item has no box to measure)
            tags = (self.tag,) + tuple(t for t in c.gettags(self._item) if t not in ("word", "label"))
            smear_items(c, self._item, self._ink, self._paper, 1.0 - self.clear, tags)
            c.itemconfigure(self._item, state="hidden")
            c.tag_raise(self.tag, self._item)
        except tk.TclError:
            pass

    def hover(self, on, animator=None):
        """Un-smear (on) or smear again, easing from where it is now."""
        target = 1.0 if on else 0.0
        if self.word is None or target == self._target:
            return
        self._target = target
        if animator is None or animator.reduce_motion:
            self.clear = target
            self.paint()
            return
        start = self.clear

        def frame(p):
            self.clear = start + (target - start) * p
            self.paint()
        try:
            animator.run(f"unsmear{id(self)}", int(UNSMEAR_MS * abs(target - start)) or 1, frame)
        except tk.TclError:
            pass


class RoundButton(SmoothCanvas):
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
    * `hint_font`: a Font for the caption (default: 72% of the label font, which is too big on big cards).
    * `flat=True` is a quiet text button: no fill or outline until hovered (UI-8). `ring` is the
      width of the accent outline on hover (2; the duel cards use 3).
    * config(censor=True): the text is smeared sideways until hovered (ST-6, the duel cards; see Unsmear).
    """

    def __init__(self, parent, text, command, bg=None, fg=None, font=None,
                 padx=14, pady=8, hint=None, wraplength=0, radius=14, animator=None, canvas_bg=None, lift=0,
                 flat=False, ring=2, hint_font=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["bg"],
                         cursor="hand2", takefocus=0)
        self._command = command
        self._text, self._hint, self._wrap = text, hint, wraplength
        self._fill = PALETTE["neutral"] if bg is None else bg       # (read now, not at import: the look can change)
        self._fg = fg                    # None: the ink that reads on the fill (theme.ink_on: dark on a pastel)
        self._padx, self._pady, self._radius = padx, pady, radius
        self._lift, self._lifted = lift, False
        self._minwidth = 0               # ChoiceButton keeps a steady width
        self._flat, self._ring = flat, ring
        self._selected = False
        self._anim = animator
        self._font = font if isinstance(font, tkfont.Font) else tkfont.Font(root=self, font=font or "TkDefaultFont")
        self._own_hint_font = hint_font is None          # else a shared font: never resize it here
        self._hint_font = hint_font if hint_font is not None else tkfont.Font(root=self, font=self._font)
        self._enabled, self._hover, self._pressed = True, False, False
        self._censor, self.smear = False, Unsmear(self, "smear")
        self._look = self._target()          # the colours currently drawn: (fill, outline, outline width, text colour)
        self._draw()
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        # (a censored word that came up under a resting pointer un-smears when the pointer moves)
        self.bind("<Motion>", lambda e: self._censor and self._hover and self.smear.hover(True, self._anim))
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
            if "censor" in mine or "text" in mine:
                censor = bool(mine.get("censor", self._censor))
                if censor != self._censor or "text" in mine:     # a new word starts smeared
                    self.smear.clear = self.smear._target = 0.0
                self._censor = censor
            if "font" in mine:
                f = mine["font"]
                self._font = f if isinstance(f, tkfont.Font) else tkfont.Font(root=self, font=f)
            self._look = self._target()
            self._draw()
            if self._censor and self._hover:        # (and un-smears at once under a pointer already on it)
                self.smear.hover(True, self._anim)

    config = configure

    def cget(self, key):
        return {"text": self._text, "hint": self._hint, "wraplength": self._wrap, "bg": self._fill,
                "fg": self._fg or ink_on(self._fill), "font": self._font, "censor": self._censor}[key] if key in _CUSTOM else super().cget(key)

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

    def set_selected(self, on):
        """Flat buttons only: keep the 'open' look (a header menu button while its menu is shown)."""
        self._selected = bool(on)
        self._go(self._target())

    def refresh(self):
        """Re-measure and redraw (after the Font object it uses was resized)."""
        self._draw()

    # ---- looks ----------------------------------------------------------------------------------
    def _target(self):
        """(fill, outline, outline width, text colour) for the current state."""
        fill = self._fill
        fg = self._fg or ink_on(fill)
        edge = lerp_color(fill, PALETTE["text"], 0.14)
        if self._flat:
            base = super().cget("bg")
            if not self._enabled:
                return (base, base, 1, PALETTE["disabled"])
            if self._selected:
                return (PALETTE["select_bg"], PALETTE["select_bg"], 1, fg)
            if self._pressed:
                return (PALETTE["select_bg"], PALETTE["select_bg"], 1, fg)
            if self._hover:
                return (PALETTE["surface2"], PALETTE["surface2"], 1, fg)
            return (base, base, 1, PALETTE["muted"])
        if not self._enabled:
            return (lerp_color(fill, PALETTE["bg"], 0.6), lerp_color(edge, PALETTE["bg"], 0.6), 1, PALETTE["disabled"])
        if self._pressed:
            return (lerp_color(fill, PALETTE["text"], 0.10), edge, 1, fg)
        if self._hover:
            return (lerp_color(fill, "#FFFFFF", 0.45 if is_light(fill) else 0.14), PALETTE["accent"], self._ring, fg)
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
            self.itemconfigure("hint", fill=lerp_color(fg, fill, 0.3))
            if self._censor:                       # (the smear follows the button's colours as they fade)
                self.smear._paper, self.smear._ink = fill, fg
                self.smear.paint()
            else:
                self.itemconfigure("label", fill=fg)
        except tk.TclError:
            pass

    def _draw(self):
        """Measure the text, request a size, and draw the shape and labels to fill the current size."""
        self.delete("all")
        wrap = self._wrap if self._wrap > 0 else 0
        s = self._font.cget("size")
        hs = int(round(s * 0.72))
        if self._own_hint_font:
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
        need_w = max(tw + 2 * self._padx, hw + 2 * self._padx, self._minwidth)
        lift = self._lift
        need_h = th + gap + hh + 2 * self._pady + DIP + 1 + lift
        super().configure(width=need_w, height=need_h)
        w, h = max(self.winfo_width(), need_w), max(self.winfo_height(), need_h)   # (1 x 1 before it is laid out)
        body_h = h - DIP - 1 - lift
        r = max(4, min(self._radius, body_h // 2))
        if lift:     # the shadow stays put; the body sits on it and rises off it on hover
            self.round_rect(2, 1 + lift + 1, w - 2, 1 + lift + body_h, r, fill=super().cget("bg"), tags="shadow")
        self.round_rect(1, 1 + lift, w - 1, 1 + lift + body_h, r, tags=("shape", "body"))
        top = 1 + lift + (body_h - (th + gap + hh)) / 2
        self.coords(label, w / 2, top)
        if self._hint:
            self.coords("hint", w / 2, top + th + gap)
        self.tag_raise("label")
        self.tag_raise("hint")
        self._lifted = False
        self.smear.place(label, self._text if self._censor else None, self._look[3], self._look[0])
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
        if self._censor:
            self.smear.hover(on, self._anim)
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
        """Show the pressed look briefly (used to give keyboard shortcuts visible feedback). Not on a disabled
        button, and not with Reduce motion (UI-18: the action still happens, only the dip is skipped)."""
        if not self._enabled or self._pressed or (self._anim is not None and self._anim.reduce_motion):
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
        self._root().after(ms, undo)         # on the root: the button may close its own window


class TierRow(tk.Frame):
    """The six tier pills S..F, each with its key hint (1-6), a hover lift and the pressed dip (UI-7).

        row = TierRow(parent, ["S", "A", "B", "C", "D", "F"], on_pick, font("tier"), animator=app.anim)

    `buttons` are the RoundButtons (App.tier_btns), in tier order; on_pick(tier) runs on a click. The 1-6
    keys come from the keymap (App.on_key, UI-48), which runs the action and then the pill's flash().
    """

    def __init__(self, parent, tiers, on_pick, font=None, animator=None, colors=TIER_COLORS, gap=5):
        super().__init__(parent, bg=PALETTE["bg"])
        self.buttons = []
        for t, name in enumerate(tiers):
            b = RoundButton(self, name, lambda t=t: on_pick(t), bg=colors[t], font=font, padx=22, pady=10,
                            hint=str(t + 1), radius=999, animator=animator, lift=3)
            b.grid(row=0, column=t, padx=gap)
            self.buttons.append(b)


class TierChip(SmoothCanvas):
    """A small tier label drawn like the tier pills (rounded, pastel, a faint edge of the same hue), for
    places that name a tier without being a button: the Anchor words dialog (UI-28).

        TierChip(parent, "S", TIER_COLORS[0], font("head")).grid(row=0, column=0)
    """

    def __init__(self, parent, text, color, font, canvas_bg=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["bg"])
        self._text, self._color, self._font = text, color, font
        self._draw()

    def _draw(self):
        self.delete("all")
        line = self._font.metrics("linespace")
        h = int(line * 1.5)
        w = max(h, self._font.measure(self._text) + line)
        super().configure(width=w + 2, height=h + 2)
        self.round_rect(1, 1, w, h, h // 2 - 1, fill=self._color, outline=lerp_color(self._color, TIER_TEXT, 0.14))
        self.create_text(1 + w / 2, 1 + h / 2, text=self._text, font=self._font, fill=TIER_TEXT)   # (dark ink on a
                                                                                                 # pastel, dark mode too)

    def refresh(self):
        self._draw()

    def set_color(self, color):
        """Another tier colour (Tier colours, UI-61: the pill as it will look)."""
        self._color = color
        self._draw()


class DuelCards(tk.Frame):
    """The duel view's controls (UI-8): two big word cards side by side, each with a hover ring and its
    key hint, and quiet Tie / Skip text buttons under them.

        duel = DuelCards(parent, on_answer, font("pair"), font("body"), animator=app.anim)
        duel.show("apple", "pear")

    on_answer(side) gets "left", "right", "tie" or "skip" on a click; the keys come from the keymap (App.on_key).
    `left`, `right`, `tie` and `skip` are the RoundButtons (also App.left_btn and friends).
    """

    def __init__(self, parent, on_answer, card_font=None, small_font=None, animator=None):
        super().__init__(parent, bg=PALETTE["bg"])
        self.columnconfigure((0, 1), uniform="duel")
        self.grid_anchor("n")                # centred when the frame is wider than the cards (a long context line)
        self.left = RoundButton(self, "", lambda: on_answer("left"), bg=PALETTE["left"], font=card_font,
                                padx=40, pady=40, radius=24, hint="\u2190  A", animator=animator, ring=3, lift=self.LIFT,
                                hint_font=small_font)
        self.left.grid(row=0, column=0, padx=12, sticky="nsew")
        self.right = RoundButton(self, "", lambda: on_answer("right"), bg=PALETTE["right"], font=card_font,
                                 padx=40, pady=40, radius=24, hint="L  \u2192", animator=animator, ring=3, lift=self.LIFT,
                                 hint_font=small_font)
        self.right.grid(row=0, column=1, padx=12, sticky="nsew")
        small = tk.Frame(self, bg=PALETTE["bg"])
        small.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        self.tie = RoundButton(small, "Tie / can't decide", lambda: on_answer("tie"), font=small_font,
                               hint="\u2193  T", animator=animator, flat=True)
        self.tie.grid(row=0, column=0, padx=8)
        self.skip = RoundButton(small, "Skip pair", lambda: on_answer("skip"), font=small_font, hint="S",
                                animator=animator, flat=True)
        self.skip.grid(row=0, column=1, padx=8)

    @property
    def buttons(self):
        return {"left": self.left, "right": self.right, "tie": self.tie, "skip": self.skip}

    RESOLVE_MS = 120
    LIFT = 4                                 # the cards rise this much on hover and when they win

    def resolve(self, side, animator, on_done):
        """UI-19: the winning card ("left" / "right") lifts a few pixels and the other dims (it fades to its
        disabled look), then on_done() shows the next pair. A key press (Animator.finish_all) or Reduce
        motion goes straight to on_done."""
        win, lose = (self.left, self.right) if side == "left" else (self.right, self.left)
        lose.set_enabled(False)              # fades to its disabled look
        win._set_lift(True)                  # rises off its shadow, as on hover
        animator.run(self.anim_key, self.RESOLVE_MS, lambda p: None, on_done)

    @property
    def anim_key(self):
        """The Animator key of the result animation (a key press finishes it: the next pair waits on it)."""
        return f"duel{id(self)}"

    def show(self, left, right, colors=None, censor=(False, False)):
        """Show a new pair (and enable everything). `colors` = (left fill, right fill), e.g. each word's tier
        colour; without it the cards keep their own pastel blue / peach. `censor`: each word smeared until
        hovered (ST-6)."""
        left_bg, right_bg = colors or (PALETTE["left"], PALETTE["right"])
        self.left.config(text=left, bg=left_bg, censor=censor[0])
        self.right.config(text=right, bg=right_bg, censor=censor[1])
        self.set_enabled(True)

    def set_enabled(self, enabled):
        for b in self.buttons.values():
            b.set_enabled(enabled)


class AnchorLadder(SmoothCanvas):
    """The S..F strip shown while a word is placed by comparing it to anchors (UI-9).

        ladder = AnchorLadder(parent, ["S", "A", "B", "C", "D", "F"], font("head"), animator=app.anim)
        ladder.update_range(0, 5, 2)    # every tier still possible; asking about B's anchor

    Tiers still possible (lo..hi) keep their pastel colour; ruled-out ones fade toward the background.
    The tier whose anchor is being asked about gets an accent ring and a small caret under it. Changes
    blend over LADDER_MS with the Animator (they jump with Reduce motion).
    """
    LADDER_MS = 180

    def __init__(self, parent, tiers, font=None, animator=None, colors=TIER_COLORS, canvas_bg=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["bg"])
        self._tiers, self._colors, self._font, self._anim = list(tiers), list(colors), font, animator
        self.lo, self.hi, self.mid = 0, len(self._tiers) - 1, None
        self._amount = [1.0] * len(self._tiers)      # 1 = still possible (full colour), 0 = ruled out
        self._draw()

    def _cell(self):
        f = self._font
        line = f.metrics("linespace") if f else 16
        return int(line * 1.9), int(line * 1.5), max(4, line // 3)   # pill width, height, gap

    def _draw(self):
        self.delete("all")
        w, h, gap = self._cell()
        caret = max(6, h // 4)
        total = len(self._tiers) * w + (len(self._tiers) - 1) * gap
        super().configure(width=total + 6, height=h + caret + 8)
        for i, name in enumerate(self._tiers):
            x = 3 + i * (w + gap)
            self.round_rect(x, 3, x + w, 3 + h, h // 2, tags=("pill", f"pill{i}"), width=1)
            self.create_text(x + w / 2, 3 + h / 2, text=name, font=self._font, tags=("txt", f"txt{i}"))
        self._caret_size = (w, h, gap, caret)
        self._paint()

    def _paint(self):
        bg = super().cget("bg")
        w, h, gap, caret = self._caret_size
        self.delete("caret")
        for i in range(len(self._tiers)):
            a = self._amount[i]
            fill = lerp_color(lerp_color(self._colors[i], bg, 0.82), self._colors[i], a)
            ring = i == self.mid
            self.itemconfigure(f"pill{i}", fill=fill, outline=PALETTE["accent"] if ring else lerp_color(fill, PALETTE["text"], 0.12),
                               width=3 if ring else 1)
            self.itemconfigure(f"txt{i}", fill=lerp_color(PALETTE["disabled"], PALETTE["text"], a))
        if self.mid is not None:
            cx = 3 + self.mid * (w + gap) + w / 2
            y = 3 + h + 3
            self.create_polygon(cx - caret, y + caret, cx + caret, y + caret, cx, y, fill=PALETTE["accent"],
                                outline="", tags="caret")

    def update_range(self, lo, hi, mid):
        """Show that tiers lo..hi are still possible and the anchor of tier `mid` is being asked about."""
        self.lo, self.hi, self.mid = lo, hi, mid
        start = list(self._amount)
        goal = [1.0 if lo <= i <= hi else 0.0 for i in range(len(self._tiers))]

        def frame(p):
            self._amount = [a + (b - a) * p for a, b in zip(start, goal)]
            self._paint()
        if self._anim is None:
            frame(1.0)
        else:
            self._anim.run(f"ladder{id(self)}", self.LADDER_MS, frame)

    def possible(self):
        """The tier indexes drawn as still possible (for tests)."""
        return [i for i in range(len(self._tiers)) if self.lo <= i <= self.hi]

    def refresh(self):
        self._draw()


class TabBar(SmoothCanvas):
    """Folder-style tabs over a page (UI-10): a hairline runs the full width under the tabs, and the
    chosen tab is drawn in the page colour with its sides and rounded top outlined, open at the bottom,
    so it looks joined to the page below.

        tabs = TabBar(parent, [("place", "Place new words"), ...], on_change, font("label"),
                      animator=app.anim, page_bg=PALETTE["bg"])
        tabs.pack(fill="x")
        tabs.set("refine")        # move to a tab without calling on_change (e.g. after a key)
        tabs.show_only({"place", "refine"})   # the other tabs fold away (UI-46)

    A click on another tab slides the open tab there (SLIDE_MS, ease-out; jumps with Reduce motion) and
    calls on_change(key). Tabs are all as wide as the widest label and sit centred. A tab that is shown or
    hidden grows or folds over SLIDE_MS too; its label shows once its tab is wide enough for it.
    """
    SLIDE_MS = 180

    def __init__(self, parent, options, on_change, font=None, animator=None, canvas_bg=None, page_bg=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["surface"], takefocus=0)
        self.options = list(options)
        self._keys = [k for k, _ in self.options]
        self._on_change, self._font, self._anim = on_change, font, animator
        self._page = page_bg or PALETTE["bg"]
        self.value = self._keys[0]
        self.visible = set(self._keys)
        self._open = {k: 1.0 for k in self._keys}   # how open each tab is, 0 (folded away) .. 1 (animated)
        self._x = 0.0                        # left edge of the open tab, in tab widths (animated)
        self._sliding = False
        self._hover = None
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<ButtonRelease-1>", self._on_click)
        self.bind("<Configure>", lambda e: self._draw())
        self._draw()

    def _metrics(self):
        f = self._font
        line = f.metrics("linespace") if f else 16
        widest = max((f.measure(lbl) if f else 8 * len(lbl)) for _, lbl in self.options)
        tab_w = widest + 2 * int(line * 1.1)
        h = int(line * 2.1)
        n = len(self.options)
        width = max(self.winfo_width(), n * tab_w + 20)
        shown = sum(self._open.values())
        return tab_w, h, (width - shown * tab_w) / 2, width   # tab width, height, left edge of the tabs, width

    def _slot(self, key):
        """Left edge of a tab, in tab widths from the left edge of the tabs."""
        return sum(self._open[k] for k in self._keys[:self._keys.index(key)])

    def _draw(self):
        self.delete("all")
        tab_w, h, x0, width = self._metrics()
        super().configure(height=h + 1, cursor="hand2")
        super().configure(width=len(self.options) * tab_w + 20)
        self.round_rect(0, 0, 0, 0, 0, fill=PALETTE["surface2"], tags="hoverfill")
        # the open tab: page coloured with a hairline, round on top; its bottom edge sits just below the canvas,
        # so it is open at the bottom (it runs into the page)
        self.round_rect(0, 0, 0, 0, 0, fill=self._page, outline=PALETTE["border"], tags="tabfill")
        self.create_line(0, 0, 0, 0, fill=PALETTE["border"], state="hidden", tags="tabedge")   # (its outline, for tests)
        self.create_line(0, 0, 0, 0, fill=PALETTE["border"], tags="baseline_left")
        self.create_line(0, 0, 0, 0, fill=PALETTE["border"], tags="baseline_right")
        for key, label in self.options:
            self.create_text(0, 2 + h / 2, text=label, font=self._font, tags=("label", f"label_{key}"))
        self._place_tab()

    @staticmethod
    def _tab_shape(x1, x2, top, bottom, r):
        """Outline of a tab with rounded top corners and square bottom corners (points doubled at the
        bottom so a smoothed polygon keeps them sharp)."""
        return [x1, bottom, x1, bottom, x1, top + r, x1, top, x1 + r, top, x2 - r, top, x2, top,
                x2, top + r, x2, bottom, x2, bottom]

    def _place_tab(self):
        tab_w, h, x0, width = self._metrics()
        base = h                                     # y of the page line
        top = 4
        r = max(4, h // 4)
        x1 = x0 + self._x * tab_w + 2
        x2 = x1 + self._open[self.value] * tab_w - 4
        shape = self._tab_shape(x1, max(x2, x1 + 2 * r), top, base + 1, r)
        self.round_rect_coords("tabfill", x1, top, max(x2, x1 + 2 * r), base + 3, radii=(r, r, 0, 0))
        self.coords("tabedge", *shape[2:-2])       # sides and top only: open at the bottom
        self.coords("baseline_left", 0, base, x1, base)
        self.coords("baseline_right", x2, base, width, base)
        hov = self._hover if self._hover != self.value else None
        if hov is not None:
            hx1 = x0 + self._slot(hov) * tab_w + 6
            self.round_rect_coords("hoverfill", hx1, top + 4, hx1 + tab_w - 12, base - 1, radii=(r, r, 0, 0))
            self.itemconfigure("hoverfill", state="normal")
        else:
            self.itemconfigure("hoverfill", state="hidden")
        for key, label in self.options:
            on = key == self.value or key == self._hover
            w = self._open[key] * tab_w
            fits = w >= (self._font.measure(label) if self._font else 8 * len(label)) + 4
            self.coords(f"label_{key}", x0 + self._slot(key) * tab_w + w / 2, 2 + h / 2)
            self.itemconfigure(f"label_{key}", fill=PALETTE["text"] if on else PALETTE["muted"],
                               state="normal" if fits else "hidden")
        self.tag_raise("label")

    def _index_at(self, x):
        tab_w, _h, x0, _w = self._metrics()
        for key in self._keys:
            left = x0 + self._slot(key) * tab_w
            if key in self.visible and left <= x < left + self._open[key] * tab_w:
                return key
        return None

    def tab_x(self, key):
        """Centre x of a tab, in canvas pixels (for tests)."""
        tab_w, _h, x0, _w = self._metrics()
        return x0 + (self._slot(key) + self._open[key] / 2) * tab_w

    def _on_motion(self, e):
        self._set_hover(self._index_at(e.x))

    def _set_hover(self, key):
        if key != self._hover:
            self._hover = key
            self._place_tab()

    def _on_click(self, e):
        key = self._index_at(e.x)
        if key is not None and key != self.value:
            self.set(key)
            self._on_change(key)

    def set(self, key):
        """Show `key` as the open tab (slides; does not call on_change)."""
        if key not in self._keys:
            return
        self.value = key
        start = self._x

        def frame(p):
            self._sliding = p < 1
            self._x = start + (self._slot(self.value) - start) * p   # follows tabs that fold meanwhile
            self._place_tab()
        if self._anim is None:
            frame(1.0)
        else:
            self._anim.run(f"tabs{id(self)}", self.SLIDE_MS, frame)

    def show_only(self, keys, animate=True):
        """Show just these tabs (the open one always stays): the others fold away and new ones grow in
        (UI-46). animate=False sets them at once (when the window is first built)."""
        keys = set(keys) | {self.value}
        if keys == self.visible:
            return
        self.visible = keys
        start = dict(self._open)

        def frame(p):
            for k in self._keys:
                goal = 1.0 if k in self.visible else 0.0
                self._open[k] = start[k] + (goal - start[k]) * p
            if not self._sliding:
                self._x = self._slot(self.value)
            if self._hover not in self.visible:
                self._hover = None
            self._place_tab()
        if self._anim is None or not animate:
            frame(1.0)
        else:
            self._anim.run(f"tabfold{id(self)}", self.SLIDE_MS, frame)

    def get(self):
        return self.value

    def refresh(self):
        self._draw()


class DropMenu:
    """A styled drop-down menu (UI-10): a borderless window with roomy rows, the pastel highlight, check
    marks and shortcut hints, used by the header's File / Edit / View / Settings buttons.

        items = [("command", "Export tier list...", app.export, None),
                 ("check", "Reduce motion", app.motion_var, app.toggle_motion),
                 ("radio", "Tier S", app.filter_var, "S", app.refresh),
                 ("separator",),
                 ("command", "Undo", app.undo, "Ctrl+Z")]
        DropMenu(root, items, font("body")).open(x, y, on_close)

    Mouse: hover highlights, click runs the item and closes. Keys: Up / Down move, Return runs, Escape
    closes. It never grabs input (unlike tk's own menus and ttk drop-down lists), so switching to another
    program closes it (watch_focus -> close_popups, UI-43); a click elsewhere in the window does too.
    """
    open_menus = set()                 # every DropMenu showing right now (close_popups closes them all)

    def __init__(self, root, items, font=None):
        self.root, self.items, self.font = root, list(items), font
        self.win = None
        self._rows, self._active, self._on_close = [], None, None
        self._prev_focus = ""
        self.on_side = None              # called with -1 / +1 for Left / Right (HeaderMenus: the next menu)

    @staticmethod
    def labels(items):
        """The labels of the clickable items (for tests and docs)."""
        return [it[1] for it in items if it[0] in ("command", "check", "radio")]

    def is_open(self):
        return self.win is not None

    def open(self, x, y, on_close=None):
        """Show the menu with its top-left corner at screen position (x, y)."""
        self.close()
        self._on_close = on_close
        self._prev_focus = str(self.root.tk.call("focus"))    # given back on close (UI-27)
        win = self.win = tk.Toplevel(self.root, bg=PALETTE["border"])
        win.withdraw()
        win.overrideredirect(True)
        # (not "-topmost": that kept it in front of other programs after switching away, UI-43)
        body = tk.Frame(win, bg=PALETTE["surface"], padx=6, pady=6)
        body.pack(padx=1, pady=1)                 # the 1 px border is the window's own colour
        self._rows = []
        for it in self.items:
            if it[0] == "separator":
                tk.Frame(body, height=1, bg=PALETTE["border"]).pack(fill="x", padx=8, pady=5)
                continue
            kind, label, target = it[0], it[1], it[2]
            extra = it[3] if len(it) > 3 else None
            row = tk.Frame(body, bg=PALETTE["surface"], cursor="hand2")
            row.pack(fill="x")
            mark = ""
            if kind == "check":
                mark = "\u2713" if target.get() else ""
            elif kind == "radio":
                mark = "\u2713" if target.get() == extra else ""
            parts = [tk.Label(row, text=mark, width=2, bg=PALETTE["surface"], fg=PALETTE["accent_text"],
                              font=self.font, anchor="w"),
                     tk.Label(row, text=label, bg=PALETTE["surface"], fg=PALETTE["text"], font=self.font,
                              anchor="w", padx=4, pady=5)]
            accel = extra if kind == "command" else None
            if accel:
                parts.append(tk.Label(row, text=accel, bg=PALETTE["surface"], fg=PALETTE["muted"],
                                      font=self.font, anchor="e", padx=10))
            parts[0].pack(side="left", padx=(6, 0))
            parts[1].pack(side="left")
            if accel:
                parts[2].pack(side="right")
            i = len(self._rows)
            self._rows.append((row, parts, it))
            for w in [row] + parts:
                w.bind("<Enter>", lambda e, i=i: self._highlight(i))
                w.bind("<ButtonRelease-1>", lambda e, i=i: self.invoke(i))
        win.bind("<Escape>", lambda e: self.close())
        win.bind("<Up>", lambda e: self._step(-1))
        win.bind("<Down>", lambda e: self._step(1))
        win.bind("<Return>", lambda e: self._active is not None and self.invoke(self._active))
        win.bind("<Left>", lambda e: self.on_side and self.on_side(-1))
        win.bind("<Right>", lambda e: self.on_side and self.on_side(1))
        win.update_idletasks()
        # keep it on screen
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        x, y = clamp_to_monitor(win, x, y, w, h)     # on the monitor it opens from, not the main one
        win.geometry(f"+{x}+{y}")
        win.deiconify()
        win.lift()
        DropMenu.open_menus.add(self)
        try:
            win.focus_force()
        except tk.TclError:
            pass

    def _highlight(self, i):
        self._active = i
        for j, (row, parts, _it) in enumerate(self._rows):
            bg = PALETTE["select_bg"] if j == i else PALETTE["surface"]
            for w in [row] + parts:
                w.configure(bg=bg)

    def _step(self, d):
        if not self._rows:
            return
        i = 0 if self._active is None and d > 0 else (len(self._rows) - 1 if self._active is None else
                                                      (self._active + d) % len(self._rows))
        self._highlight(i)

    def invoke(self, i):
        """Run row `i` (0 = first clickable item) and close the menu."""
        _row, _parts, it = self._rows[i]
        self.close()
        if it[0] == "check":
            var, command = it[2], (it[3] if len(it) > 3 else None)
            var.set(not var.get())
            if command:
                command()
        elif it[0] == "radio":
            var, value, command = it[2], it[3], (it[4] if len(it) > 4 else None)
            var.set(value)
            if command:
                command()
        else:
            it[2]()

    def close(self):
        """Close it. If it had the keyboard focus, the focus goes back to where it was before it opened, so
        keys keep working (closing with Escape used to leave no focus at all); not when the program has
        lost the focus to another one."""
        DropMenu.open_menus.discard(self)
        if self.win is not None:
            try:
                had_focus = str(self.win.tk.call("focus")).startswith(str(self.win))
                self.win.destroy()
                if had_focus:                # forced: the window manager does not hand focus back from a
                    self.root.nametowidget(self._prev_focus or ".").focus_force()   # borderless window
            except (tk.TclError, KeyError):
                pass
            self.win = None
            self._rows, self._active = [], None
            cb, self._on_close = self._on_close, None
            if cb:
                cb()


class ChoiceButton(RoundButton):
    """A drop-down choice (UI-43): a soft button showing the current value and a little arrow; a click opens a
    DropMenu with the choices (a check mark on the current one). Replaces ttk.Combobox, whose list grabs all
    input and so stayed in front of other programs.

        ChoiceButton(parent, app.filter_var, ["All tiers", "S", "A"], on_change=app.refresh, font=font("body"))

    It is as wide as its longest choice, so it does not change size when the value does.
    """

    def __init__(self, parent, variable, values, on_change=None, font=None, animator=None, canvas_bg=None):
        self.var, self.values, self._on_change = variable, list(values), on_change
        super().__init__(parent, "", self.toggle, bg=PALETTE["surface"], font=font, padx=12, pady=5, radius=10,
                         animator=animator, canvas_bg=canvas_bg)
        self.menu = DropMenu(self.winfo_toplevel(), [], font)
        variable.trace_add("write", lambda *_: self._show())
        self._show()

    def set_values(self, values):
        self.values = list(values)
        self._show()

    def _show(self):
        """Label it with the current value; the minimum width fits the longest choice."""
        f = self._font
        self._minwidth = max((f.measure(f"{v}   \u25be") for v in self.values), default=0) + 2 * self._padx + 4
        self.config(text=f"{self.var.get()}   \u25be")

    def toggle(self):
        if self.menu.is_open():
            self.menu.close()
            return
        self.menu.items = [("radio", v, self.var, v, self._picked) for v in self.values]
        self.menu.open(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height() + 2)

    def _picked(self):
        if self._on_change:
            self._on_change()

    def refresh(self):
        self._show()


class HeaderMenus(tk.Frame):
    """The row of header menu buttons (File, Edit, View, Settings) with their DropMenus (UI-10).

        HeaderMenus(parent, [("File", items), ("Edit", items), ...], font("body"), animator=app.anim)

    Clicking a button opens its menu under it (clicking again closes it); while one menu is open,
    hovering another button switches to that menu, like a desktop menu bar, and so do Left / Right.
    open_menu(name) opens one from the keyboard (Alt+F and friends, F10).
    """

    def __init__(self, parent, menus, font=None, animator=None, bg=None):
        bg = bg or PALETTE["surface"]
        super().__init__(parent, bg=bg)
        self.menus, self.buttons, self.drops = dict(menus), {}, {}
        self._open = None
        for name, items in menus:
            b = RoundButton(self, name, lambda n=name: self.toggle(n), font=font, padx=12, pady=5, radius=10,
                            animator=animator, canvas_bg=bg, flat=True)
            b.pack(side="left", padx=(0, 2))
            b.bind("<Enter>", lambda e, n=name: self._hover_switch(n), add="+")
            self.buttons[name] = b
            self.drops[name] = DropMenu(self.winfo_toplevel(), items, font)
            self.drops[name].on_side = lambda d, n=name: self._side(n, d)
        top = self.winfo_toplevel()
        top.bind("<ButtonPress-1>", self._click_outside, add="+")
        top.bind("<Configure>", lambda e: e.widget is top and self.close(), add="+")
        top.bind("<Unmap>", lambda e: e.widget is top and self.close(), add="+")

    def _click_outside(self, e):
        """A click anywhere in the main window closes the open menu (its own button toggles it instead)."""
        if self._open is not None and e.widget not in self.buttons.values():
            self.close()

    @property
    def open_name(self):
        return self._open

    def toggle(self, name):
        if self._open == name:
            self.close()
        else:
            self.open_menu(name)

    def open_menu(self, name):
        self.close()
        b = self.buttons[name]
        self._open = name
        b.set_selected(True)
        self.drops[name].open(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height() + 2,
                              on_close=lambda n=name: self._closed(n))

    def _closed(self, name):
        if self._open == name:
            self._open = None
        try:
            self.buttons[name].set_selected(False)
        except tk.TclError:
            pass

    def _side(self, name, d):
        """Left / Right in an open menu: open the neighbouring one (wrapping round, like a menu bar)."""
        names = list(self.buttons)
        self.open_menu(names[(names.index(name) + d) % len(names)])

    def _hover_switch(self, name):
        if self._open is not None and self._open != name:
            self.open_menu(name)

    def close(self):
        if self._open is not None:
            self.drops[self._open].close()


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


def definition_tags(t, body):
    """The text tags a definition pane uses (fill_definitions): the word in bold, muted numbers, the part of
    speech and examples in italics, senses indented."""
    italic = (body.cget("family"), body.cget("size"), "italic")   # follows the body size
    t.tag_configure("num", foreground=PALETTE["muted"])
    t.tag_configure("pos", foreground=PALETTE["muted"], font=italic)
    t.tag_configure("sense", lmargin1=6, lmargin2=26, spacing1=2)
    t.tag_configure("ex", foreground=PALETTE["muted"], lmargin1=26, lmargin2=26, font=italic)
    t.tag_configure("wait", foreground=PALETTE["muted"])
    t.tag_configure("base", foreground=PALETTE["muted"], lmargin1=26, lmargin2=26, spacing1=1, spacing3=2)
    t.tag_configure("link", underline=True, foreground=PALETTE["text"])     # (W-1: the word under the pointer)
    t.tag_configure("back", foreground=PALETTE["muted"], underline=True, spacing3=4)
    t.tag_raise("link")


class LinkButton(SmoothCanvas):
    """A small icon (smooth.ICONS) that does something when clicked, muted until hovered, with a hover note: the
    Wiktionary link at the top right of a definition (asked for).

        LinkButton(parent, "external", command, note="Open on Wiktionary", size=16, bg=PALETTE["surface"])
    """

    def __init__(self, parent, icon, command, note=None, size=16, bg=None):
        bg = bg or PALETTE["surface"]
        super().__init__(parent, width=size + 6, height=size + 6, bd=0, highlightthickness=0, bg=bg, cursor="hand2")
        self.icon, self.command, self.size = icon, command, size
        self._hover = False
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", lambda e: self.command and self.command())
        if note:
            Tooltip(self, lambda e: note)
        self._draw()

    def _set_hover(self, on):
        self._hover = on
        self._draw()

    def _draw(self):
        self.delete("all")
        ink = PALETTE["accent"] if self._hover else PALETTE["muted"]
        self.create_image(3, 3, image=self.icon_image(self.icon, self.size, ink), anchor="nw")

    def refresh(self):
        self._draw()


WIKTIONARY_NOTE = "Open on Wiktionary: where the word comes from, and more"


def _place_link(t, word, link):
    """The Wiktionary link at the top right of the pane `t` for `word` (link(word) opens it), or none: no word, or
    `link` None (offline: it only shows while Wiktionary can be reached)."""
    button = getattr(t, "_link_button", None)
    if not word or link is None:
        if button is not None:
            button.place_forget()
        t._link_word = None
        t.tag_configure("head", rmargin=0)
        return
    if button is None:
        size = max(12, int(tkfont.Font(font=t.cget("font")).metrics("linespace") * 0.8))
        button = t._link_button = LinkButton(t, "external", lambda: t._link and t._link_word and t._link(t._link_word),
                                             note=WIKTIONARY_NOTE, size=size, bg=t.cget("bg"))
    t._link, t._link_word = link, word
    t.tag_configure("head", rmargin=button.size + 12)    # (a long word's line never runs under it)
    button.place(relx=1.0, x=-6, y=6, anchor="ne")
    tk.Misc.lift(button)                         # (above the text; a canvas's own lift() raises items)


def fill_definitions(t, entries, body, censor=False, animator=None, base=None, on_word=None, back=None, link=None):
    """Fill the definition pane `t` (a tk.Text) with [(word, definition text or None while it is being looked up,
    the keys of its meanings to smear, True if the word itself is censored)]: the word in bold, then each sense
    numbered, its part of speech, its text and example. `censor` (OB-2, OB-6): a meaning the rules found rude of a
    censored kind (its first rudeness.GLOSS_KEY characters among the keys: Store.smeared_meanings) shows its labels,
    and its text smeared sideways like a censored word, un-smearing under the pointer. A censored word is smeared
    the same way (not masked), and un-smears while the pointer is anywhere over the pane. `base` (F-3): base(word)
    -> the same four for another word; under a meaning that only names one ("Alternative form of bull dyke"), that
    word's own first meaning, muted. `on_word` (W-1): on_word(word) when a word in a meaning is clicked (it is
    underlined under the pointer); `back`: (text, command), a quiet line on top that goes back (after a lookup).
    `link`: link(word) opens the first word's Wiktionary page, from a small icon at the top right (None: no icon,
    as while Wiktionary cannot be reached)."""
    from definitions import form_target, main_sense, parse_definition
    for c in getattr(t, "_smears", ()):          # the smeared senses of the last fill (tk keeps them otherwise)
        c.destroy()
    _place_link(t, entries[0][0] if entries else None, link)
    t._smears, t._words, t._animator, t._on_word = [], [], animator, on_word
    _watch_pane(t)
    _watch_links(t)
    inside = _pointer_inside(t)
    definition_tags(t, body)
    t.config(state="normal")
    t.delete("1.0", "end")
    t.tag_unbind("back", "<Button-1>")
    if back:
        t.insert("end", back[0] + "\n", "back")
        t.tag_bind("back", "<Button-1>", lambda e: back[1]())

    def word(name, hide, font_, tag):
        """The word `name` (a censored one smeared, un-smearing while the pointer is over the pane)."""
        if not hide:
            t.insert("end", name, tag)
            return
        c = smeared_label(t, name, font_, t.cget("bg"), animator, hover=False)
        t.window_create("end", window=c, align="center")
        t._smears.append(c)
        t._words.append(c)
        if inside:
            c.unsmear.hover(True)
    for i, (heading, text, smeared, hide) in enumerate(entries):
        if i:
            t.insert("end", "\n")
        word(heading, hide, t.tag_cget("head", "font") or body, "head")
        t.insert("end", "\n", "head")
        if text is None:
            t.insert("end", "Looking up definition...\n", "wait")
            continue
        shown = set()
        for sense in parse_definition(text):
            prefix = ""
            if sense["num"]:
                t.insert("end", sense["num"] + ".  ", ("num", "sense"))
                prefix += sense["num"] + ".  "
            if sense["pos"]:
                t.insert("end", sense["pos"] + "  ", ("pos", "sense"))
                prefix += sense["pos"] + "  "
            _insert_gloss(t, sense, "sense", censor and sense["gloss"][:GLOSS_KEY] in smeared, body, animator, prefix)
            if sense["example"]:
                t.insert("end", "\u201c" + sense["example"] + "\u201d\n", "ex")
            target = form_target(sense["gloss"]) if base else None
            if target and target not in shown:          # (each word once: "plural of X" and "past of X" share it)
                shown.add(target)
                name, other, keys, hidden = base(target)
                main = main_sense(other) if other else None
                word(name, hidden, body, "base")
                after = (f" ({main['pos']})" if main and main["pos"] else "") + ": "
                t.insert("end", after, "base")
                if other is None:
                    t.insert("end", "Looking up definition...\n", "base")
                elif main is None:
                    t.insert("end", "No definition found.\n", "base")
                else:
                    _insert_gloss(t, main, "base", censor and main["gloss"][:GLOSS_KEY] in keys, body, animator,
                                  " " * 6 + name + after)
    t.config(state="disabled")


LINK_TAGS = ("sense", "ex", "base")     # where a word can be clicked to look it up (W-1): meanings, examples, forms
_WORD = re.compile(r"[^\W\d_]+(?:['\u2019-][^\W\d_]+)*")


def word_at(t, x, y):
    """(start index, end index, the word) under the point x, y of the definition pane `t`, inside a meaning,
    an example or a form's line (LINK_TAGS), or None (a heading, a label, a number, or no letters there)."""
    try:
        idx = t.index(f"@{x},{y}")
        box = t.bbox(idx)
    except tk.TclError:
        return None
    if not box or not (box[0] <= x < box[0] + box[2] + 1 and box[1] <= y < box[1] + box[3]):
        return None                                  # (past the end of a line: the nearest letter is not under it)
    tags = set(t.tag_names(idx))
    if not tags & set(LINK_TAGS) or tags & {"num", "pos", "head", "back"}:
        return None
    line, col = (int(v) for v in idx.split("."))
    text = t.get(f"{line}.0", f"{line}.end")
    for m in _WORD.finditer(text):
        if m.start() <= col < m.end():
            return f"{line}.{m.start()}", f"{line}.{m.end()}", m.group(0).lower()
    return None


def _watch_links(t):
    """Once per pane (W-1): the word under the pointer underlined, with a hand, while the pane has an on_word; a
    click on it calls on_word(word)."""
    if getattr(t, "_links_watched", False):
        return
    t._links_watched = True

    def motion(e):
        t.tag_remove("link", "1.0", "end")
        hit = word_at(t, e.x, e.y) if getattr(t, "_on_word", None) else None
        if hit:
            t.tag_add("link", hit[0], hit[1])
        over_back = "back" in t.tag_names(f"@{e.x},{e.y}")
        t.config(cursor="hand2" if hit or over_back else "arrow")

    def leave(e):
        t.tag_remove("link", "1.0", "end")
        t.config(cursor="arrow")

    def click(e):
        hit = word_at(t, e.x, e.y) if getattr(t, "_on_word", None) else None
        if hit:
            t._on_word(hit[2])
            return "break"
        return None
    t.bind("<Motion>", motion, add="+")
    t.bind("<Leave>", leave, add="+")
    t.bind("<Button-1>", click, add="+")


def _pointer_inside(w):
    """True if the pointer is over `w` or anything inside it."""
    try:
        over = w.winfo_containing(*w.winfo_pointerxy())
    except (tk.TclError, KeyError):
        return False
    while over is not None:
        if over is w:
            return True
        over = over.master
    return False


def _watch_pane(t):
    """Once per pane: while the pointer is anywhere over it, its censored words un-smear (asked for); moving onto
    a smeared meaning inside it is still over the pane."""
    if getattr(t, "_watched", False):
        return
    t._watched = True

    def over(on):
        for c in getattr(t, "_words", ()):
            c.unsmear.hover(on, t._animator)
    t.bind("<Enter>", lambda e: over(True), add="+")
    t.bind("<Leave>", lambda e: None if _pointer_inside(t) else over(False), add="+")


def _insert_gloss(t, sense, tag, smear, body, animator, prefix):
    """A sense's text and a line end into the pane `t` under `tag`; `smear`: its labels, then its gloss smeared
    (smeared_label, wrapped to the room left on its line; `prefix`: the text already on it)."""
    if not smear:
        t.insert("end", sense["text"] + "\n", tag)
        return
    label = "(" + ", ".join(sense["labels"]) + ") " if sense["labels"] else ""
    t.insert("end", label, ("pos", tag))
    pad = int(t.cget("padx") or 0)
    room = (t.winfo_width() if t.winfo_ismapped() else int(t.cget("width")) * body.measure("0")) - 2 * pad - 30
    width = max(body.measure("n" * 12), room - body.measure(prefix + label))
    c = smeared_label(t, sense["gloss"].strip(), body, t.cget("bg"), animator, width=width)
    t.window_create("end", window=c, align="top")
    t.insert("end", "\n", tag)
    t._smears.append(c)


def smeared_label(parent, text, font_, bg, animator=None, width=0, fg=None, hover=True):
    """A small canvas showing `text` smeared (smear_items; wrapped at `width` pixels, 0: one line), for the places
    that are not our own canvases (the definition panes, Browse's list). It un-smears while the pointer is over it
    (`hover`), or when the caller says so: canvas.unsmear.hover(on, animator)."""
    fg = PALETTE["text"] if fg is None else fg
    c = tk.Canvas(parent, bg=bg, highlightthickness=0, bd=0, cursor="arrow")
    item = c.create_text(0, 0, text=text, font=font_, width=width, anchor="nw", fill=fg, tags="gloss")
    x0, y0, x1, y1 = c.bbox(item) or (0, 0, 0, 0)          # (no box for an empty text)
    c.configure(width=x1 + 1, height=y1 + 1)
    smear = c.unsmear = Unsmear(c, "smear")
    smear.place(item, text, fg, bg)
    if hover:
        c.bind("<Enter>", lambda e: smear.hover(True, animator))
        c.bind("<Leave>", lambda e: smear.hover(False, animator))
    return c


class TreeSmears:
    """Censored words in one column of a ttk.Treeview (Browse's list), smeared as everywhere else (asked for: no
    more b\u2022\u2022\u2022\u2022\u2022d). A Treeview cell holds only plain text, so the word's cell is left blank and a small
    canvas with the word smeared is placed over it while its row is on screen; it un-smears under the pointer,
    and clicks, double-clicks and the mouse wheel go on to the list.

        smears = TreeSmears(tree, "word", font, colors=lambda row_id: (ink, paper), animator=anim)
        smears.words = {row ids of censored words}; smears.refresh() after anything that moves or recolours the
        rows (scrolling, resizing, selecting, a new font size, rows added or removed)
    """
    PAD = 6                                      # (the cell's own text inset, about)

    def __init__(self, tree, column, font_, colors, animator=None, inset=None):
        self.tree, self.column, self.font, self.colors, self.anim = tree, column, font_, colors, animator
        self.inset = inset                       # (pixels kept clear at the row's top and bottom: the selection)
        self.words = set()
        self._marks = {}                         # row id -> (canvas, what it was drawn for)

    def _visible(self):
        """[(row id, cell box)] for the rows on screen."""
        t = self.tree
        rows = t.get_children()
        if not rows:
            return []
        i = max(0, int(float(t.yview()[0]) * len(rows)) - 1)
        out, seen = [], False
        for iid in rows[i:i + 400]:
            box = t.bbox(iid, self.column)
            if box:
                seen = True
                out.append((iid, box))
            elif seen:
                break
        return out

    def refresh(self):
        try:
            boxes = {iid: box for iid, box in self._visible() if iid in self.words}
        except tk.TclError:
            return
        for iid in set(self._marks) - set(boxes):
            self._marks.pop(iid)[0].destroy()
        inset = self.inset if self.inset is not None else 2
        for iid, (x, y, w, h) in boxes.items():
            ink, paper = self.colors(iid)
            key = (w, h, ink, paper, self.font.actual("size"))
            c, drawn = self._marks.get(iid, (None, None))
            if c is None:
                c = self._mark(iid)
            if drawn != key:
                c.configure(bg=paper, width=w - 2, height=h - 2 * inset)
                c.delete("all")
                item = c.create_text(self.PAD, (h - 2 * inset) / 2, text=iid, font=self.font, anchor="w", fill=ink)
                c.unsmear.place(item, iid, ink, paper)
            self._marks[iid] = (c, key)
            c.place(x=x + 1, y=y + inset, width=w - 2, height=h - 2 * inset)

    def _mark(self, iid):
        t = self.tree
        c = tk.Canvas(t, highlightthickness=0, bd=0, cursor="arrow")
        c.unsmear = Unsmear(c, "smear")
        c.bind("<Enter>", lambda e: c.unsmear.hover(True, self.anim))
        c.bind("<Leave>", lambda e: c.unsmear.hover(False, self.anim))

        def click(e, double=False):
            t.focus_set()
            t.selection_set(iid)
            t.focus(iid)
            if double:
                t.event_generate("<Double-1>", x=e.x + c.winfo_x(), y=e.y + c.winfo_y())
        c.bind("<Button-1>", click)
        c.bind("<Double-1>", lambda e: click(e, True))
        c.bind("<MouseWheel>", lambda e: t.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Button-4>", lambda e: t.yview_scroll(-1, "units"))
        c.bind("<Button-5>", lambda e: t.yview_scroll(1, "units"))
        return c


class DefinitionDrawer(tk.Frame):
    """The definition pane (UI-12): eases open and closed instead of snapping, and shows each word in bold
    with its senses numbered, the part of speech in italics and examples muted.

        drawer = DefinitionDrawer(root, fonts={"body": font("body"), "head": font("head")}, animator=app.anim)
        drawer.show_words(["apple"], lambda w: "1. (noun) a fruit\n      e.g. \"an apple a day\"")
        drawer.open() / drawer.close()      # the caller packs it first / unpacks it after on_closed

    `text` is the tk.Text inside (its height in lines is what the window-fitting code shortens).
    """
    SLIDE_MS = 200

    def __init__(self, parent, fonts, animator=None):
        super().__init__(parent, bg=PALETTE["bg"])
        self._anim = animator
        body, head = fonts["body"], fonts["head"]
        self._body = body
        inner = self._inner = tk.Frame(self, bg=PALETTE["surface"], highlightthickness=1,
                                       highlightbackground=PALETTE["border"])
        inner.pack(fill="x", anchor="n")
        # one column, or two side by side for a duel's two words (asked for: each under its own card)
        self.texts = [tk.Text(inner, height=9, wrap="word", state="disabled", font=body, bd=0, highlightthickness=0,
                              padx=14, pady=10, bg=PALETTE["surface"], cursor="arrow") for _ in range(2)]
        self.text, self.text2 = self.texts
        self._rule = tk.Frame(inner, width=1, bg=PALETTE["border"])
        for t in self.texts:
            t.tag_configure("head", font=head, spacing1=2, spacing3=4)
            definition_tags(t, body)
        self.text.grid(row=0, column=0, sticky="nsew")
        inner.columnconfigure(0, weight=1)
        self._columns = 1
        self._shown = False

    COLUMN_CHARS = 80                     # the one column's width in characters; two share it (the window's size
                                          # never changes for them)

    def _set_columns(self, n):
        """One column (the left text) or two equal ones side by side with a hairline between."""
        if n == self._columns:
            return
        self._columns = n
        inner = self._inner
        if n == 2:                                   # (each half, less its own side padding and the hairline, so
            c = max(1, self._body.measure("0"))      # the two together ask no more room than the one column)
            pad = 2 * int(self.text.cget("padx")) + 1
            for t in self.texts:
                t.config(width=max(10, (self.COLUMN_CHARS * c - 2 * pad) // (2 * c) - 1))
            self._rule.grid(row=0, column=1, sticky="ns", pady=10)
            self.text2.grid(row=0, column=2, sticky="nsew")
            inner.columnconfigure(0, weight=1, uniform="defs")
            inner.columnconfigure(2, weight=1, uniform="defs")
        else:
            self._rule.grid_remove()
            self.text2.grid_remove()
            self.text.config(width=self.COLUMN_CHARS)
            inner.columnconfigure(0, weight=1, uniform="")
            inner.columnconfigure(2, weight=0, uniform="")

    @property
    def columns(self):
        return self._columns

    def set_lines(self, n):
        """The pane's height in lines (both columns)."""
        for t in self.texts:
            t.config(height=n)

    def lines(self):
        return int(self.text.cget("height"))

    def show_words(self, words, get_def, censored=None, smeared=None, on_word=None, back=None, link=None):
        """Fill the pane: for each word, its senses (get_def(word) -> text, or None while it is still being looked
        up). `censored(word)`: True for a word shown smeared (until the pointer is over the pane); `smeared`: while
        censoring, smeared(word) -> the keys of its meanings smeared until hovered (OB-2, OB-6). A meaning that only
        names another word shows that word's first meaning under it, looked up the same way (F-3). `on_word`,
        `back`, `link`: see fill_definitions (W-1; the Wiktionary link on each column's word)."""
        def entry(w):
            return w, get_def(w), smeared(w) if smeared else (), bool(censored and censored(w))
        two = len(words) == 2 and back is None       # (a duel: each word's meanings on its card's side)
        self._set_columns(2 if two else 1)
        for t, ws, bk in ((self.text, words[:1] if two else words, back), (self.text2, words[1:] if two else [], None)):
            if t is self.text2 and not two:
                continue
            fill_definitions(t, [entry(w) for w in ws], self._body, censor=smeared is not None,
                             animator=self._anim, base=entry, on_word=on_word, back=bk, link=link)

    @property
    def is_open(self):
        return self._shown

    def settle(self):
        """Jump a running open / close to its end now (before the layout around it is measured)."""
        if self._anim is not None:
            self._anim.finish(f"drawer{id(self)}")

    def set_open(self, on):
        """Mark as open / shut with no animation (the caller packs or unpacks it)."""
        self._shown = bool(on)
        self._natural()

    def _natural(self):
        """Back to sizing from the contents. The explicit height left by the slide must go too (0 = none):
        with both set, Tk flips between the two sizes on every relayout."""
        try:
            if self._inner.winfo_manager() == "place":          # (folded: back in the packed layout)
                self._inner.place_forget()
                self._inner.pack(fill="x", anchor="n")
            super().configure(height=0)
            self.pack_propagate(True)
            self._inner.update_idletasks()      # (mapped again now: left to the next idle moment, a frame could
                                                # show the pane empty, a flicker as it opened; reported, worst with
                                                # the Wiktionary link inside it)
        except tk.TclError:
            pass

    def collapse(self):
        """Fold to nothing before it is packed for opening, so it never shows at full height first. The contents
        are placed, not packed, while folded: clipped rather than unmapped, so the text keeps its real width and
        can say how tall it needs to be before the pane opens (F-2: it opened at its usual 9 lines, measured 0)."""
        self.pack_propagate(False)
        super().configure(height=1)
        self._inner.pack_forget()
        self._inner.place(x=0, y=0, relwidth=1)

    def lines_needed(self):
        """How many lines tall the text must be to show all of it at its present width (0 before it is laid
        out). Headings and smeared senses are taller than a body line; this counts their pixels."""
        self.update_idletasks()
        need = 0
        for t in self.texts[:self._columns]:        # (two columns: the taller one)
            if t.winfo_width() <= 1:
                return 0
            pixels = t.count("1.0", "end", "update", "ypixels")
            pixels = pixels[0] if isinstance(pixels, tuple) else pixels
            need = max(need, -(-int(pixels or 0) // max(1, self._body.metrics("linespace"))))
        return need

    def natural_height(self):
        """The height the contents want (whether or not it is folded right now)."""
        self.update_idletasks()
        return self._inner.winfo_reqheight()

    def open(self):
        """Ease open from nothing to the height the contents want (the caller has packed it already)."""
        self._shown = True
        self._slide(0, self.natural_height(), self._natural)

    def close(self, on_closed=None):
        """Ease shut, then call on_closed (the caller unpacks it there)."""
        self._shown = False

        def done():
            self._natural()
            if on_closed:
                on_closed()
        self._slide(max(1, self.winfo_height()), 0, done)

    def _slide(self, a, b, done=None):
        self.pack_propagate(False)

        def frame(p):
            try:
                super(DefinitionDrawer, self).configure(height=max(1, int(a + (b - a) * p)))
            except tk.TclError:
                pass
        if self._anim is None:
            frame(1.0)
            if done:
                done()
        else:
            self._anim.run(f"drawer{id(self)}", self.SLIDE_MS, frame, done)


class ShapeCard(SmoothCanvas):
    """One of the queue dialog's two shape choices (UI-41): a little card with the shape's soft pastel curve
    (how likely a word is to come up early, from rank #1 to QUEUE_AXIS), its name under it, and for the
    chosen card a dotted line at the rank above which half the early words come from. The chosen card is
    white with a lilac hairline and a filled curve; the other is faint. A click calls on_pick(shape).

        card = ShapeCard(parent, "exp", "Exponential", TIER_COLORS[1], on_pick=choose)
        card.set(spread=20000, chosen=True)       # redraw (live, as the spread is typed)
    """
    def __init__(self, parent, shape, name, color, on_pick, font_=None, canvas_bg=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["bg"], cursor="hand2")
        self.shape, self.name, self.color = shape, name, color
        self._font = font_ or font("body")
        self.spread, self.chosen = 20000.0, False
        self.bind("<Button-1>", lambda e: on_pick(shape))
        self._draw()

    def set(self, spread=None, chosen=None):
        if spread is not None:
            self.spread = max(1.0, float(spread))
        if chosen is not None:
            self.chosen = bool(chosen)
        self._draw()

    def refresh(self):
        self._draw()

    def median_rank(self):
        return QUEUE_MEDIAN[self.shape] * self.spread

    def _draw(self):
        self.delete("all")
        f, chosen = self._font, self.chosen
        line = f.metrics("linespace")
        pad, w, h = int(line * 0.75), line * 12, line * 5
        W, H = w + 2 * pad, h + 2 * pad + 2 * line + line // 2
        self.configure(width=W, height=H)
        self.create_rectangle(1, 1, W - 2, H - 2, fill=PALETTE["surface"] if chosen else PALETTE["surface2"],
                              outline=PALETTE["accent"] if chosen else PALETTE["border"], width=2 if chosen else 1,
                              tags="face")
        x0, y0 = pad, pad
        pts = []
        for i in range(0, w + 1, 2):
            pts += [x0 + i, y0 + h - queue_weight(self.shape, (i / w) * QUEUE_AXIS / self.spread) * (h - 4)]
        ink = lerp_color(self.color, PALETTE["text"], 0.45) if chosen else PALETTE["disabled"]
        area = self.color if chosen else lerp_color(PALETTE["disabled"], "#FFFFFF", 0.75)
        # drawn as one smooth image (canvas lines and polygons have jagged edges, worst on Windows); the plain
        # items stay, hidden, as the record of what is drawn
        self.create_polygon([x0, y0 + h] + pts + [x0 + w, y0 + h], outline="", tags="area", fill=area, state="hidden")
        self.create_line(pts, fill=ink, width=2 if chosen else 1.5, tags="curve", state="hidden")
        ys = [h - queue_weight(self.shape, (i / w) * QUEUE_AXIS / self.spread) * (h - 4) for i in range(w + 1)]
        self._curve_img = curve_image(self, w, h, ys, area, ink, 2 if chosen else 1.5)
        self.create_image(x0, y0, image=self._curve_img, anchor="nw", tags="curve_image")
        self.create_line(x0, y0 + h, x0 + w, y0 + h, fill=PALETTE["border"], tags="axis")
        if chosen:
            med = self.median_rank()
            mx = x0 + w * min(1.0, med / QUEUE_AXIS)
            self.create_line(mx, y0 + 6, mx, y0 + h, fill=PALETTE["muted"], dash=(2, 3), tags="median")
            right = mx > x0 + w * 0.6                       # near the right edge: the label goes on its left
            self.create_text(mx - 4 if right else mx + 4, y0 + 4, text=f"half by #{short_rank(med)}", font=f,
                             fill=PALETTE["muted"], anchor="ne" if right else "nw", tags="median_text")
        yl = y0 + h + 4
        self.create_text(x0, yl, text="common", anchor="nw", font=f, fill=PALETTE["muted"])
        self.create_text(x0 + w, yl, text=f"#{short_rank(QUEUE_AXIS)}", anchor="ne", font=f, fill=PALETTE["muted"])
        self.create_text(W / 2, H - pad + 2, text=("\u25cf  " if chosen else "\u25cb  ") + self.name, anchor="s",
                         font=f, fill=PALETTE["text"] if chosen else PALETTE["muted"], tags="name")


def short_rank(n):
    """13,863 -> '13.9k', 250,000 -> '250k', 1,200,000 -> '1.2M', 840 -> '840'."""
    if n >= 999_500:
        return f"{n / 1e6:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 1000:
        k = n / 1000
        return (f"{k:.1f}".rstrip("0").rstrip(".") if k < 100 else f"{k:.0f}") + "k"
    return f"{n:.0f}"


class FileList(SmoothCanvas):
    """A white rounded list of files and folders (UI-42): a muted icon, the name, a quiet detail (size, words
    placed) and a date per row; the selected row in lilac. Only the rows on screen are drawn, so a folder with
    thousands of files stays quick.

        fl = FileList(parent, on_open=open_it, on_select=show_it)
        fl.set_rows([{"icon": "folder", "name": "Documents/", "info": "", "date": "", "value": path}, ...])
        fl.selected            # the selected row's dict, or None

    Keys (it takes focus on a click): Up / Down / Home / End / Page Up / Down move the selection, Enter opens
    (on_open(row)), the mouse wheel scrolls; a click selects, a double click opens. A row with "dim": True is
    shown greyed (a file you cannot pick here) and cannot be selected. "icon" names one of smooth.ICONS (drawn,
    all in one style, M-8); any other text is shown as it is.
    """
    def __init__(self, parent, on_open=None, on_select=None, rows_visible=9, width_chars=52, font_=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=PALETTE["bg"], takefocus=1)
        self._font = font_ or font("body")
        self.on_open, self.on_select = on_open, on_select
        self.rows, self.index, self.top = [], None, 0
        self.rows_visible, self.width_chars = rows_visible, width_chars
        for seq, d in (("<Up>", -1), ("<Down>", 1), ("<Prior>", -rows_visible), ("<Next>", rows_visible)):
            self.bind(seq, lambda e, d=d: (self.move_selection(d), "break")[1])
        self.bind("<Home>", lambda e: (self.select(self._first(1)), "break")[1])
        self.bind("<End>", lambda e: (self.select(self._first(-1)), "break")[1])
        self.bind("<Return>", lambda e: (self.open_selected(), "break")[1])
        self.bind("<KP_Enter>", lambda e: (self.open_selected(), "break")[1])
        self.bind("<Button-1>", self._click)
        self.bind("<Double-Button-1>", lambda e: self.open_selected())
        self.bind("<MouseWheel>", lambda e: self.scroll(-1 if e.delta > 0 else 1))
        self.bind("<Button-4>", lambda e: self.scroll(-1))
        self.bind("<Button-5>", lambda e: self.scroll(1))
        self._draw()

    @property
    def line(self):
        return self._font.metrics("linespace") + 10

    @property
    def selected(self):
        return self.rows[self.index] if self.index is not None and self.index < len(self.rows) else None

    def set_rows(self, rows, select=None):
        """Show these rows (dicts, see the class note), scrolled to the top; `select` = index to select."""
        self.rows, self.top = list(rows), 0
        self.index = None
        if select is not None and 0 <= select < len(self.rows) and not self.rows[select].get("dim"):
            self.index = select
        self._draw()

    def _first(self, step):
        order = range(len(self.rows)) if step > 0 else range(len(self.rows) - 1, -1, -1)
        return next((i for i in order if not self.rows[i].get("dim")), None)

    def select(self, i):
        if i is None or not (0 <= i < len(self.rows)) or self.rows[i].get("dim"):
            return
        self.index = i
        if i < self.top:
            self.top = i
        elif i >= self.top + self.rows_visible:
            self.top = i - self.rows_visible + 1
        self._draw()
        if self.on_select:
            self.on_select(self.rows[i])

    def move_selection(self, d):
        if not self.rows:
            return
        if self.index is None:
            self.select(self._first(1 if d > 0 else -1))
            return
        i = self.index
        step = 1 if d > 0 else -1
        target = max(0, min(len(self.rows) - 1, i + d))
        while 0 <= target < len(self.rows) and self.rows[target].get("dim"):
            target += step
        if 0 <= target < len(self.rows):
            self.select(target)

    def open_selected(self):
        if self.selected is not None and self.on_open:
            self.on_open(self.selected)

    def scroll(self, d):
        most = max(0, len(self.rows) - self.rows_visible)
        top = max(0, min(most, self.top + d * 3))
        if top != self.top:
            self.top = top
            self._draw()

    def _click(self, e):
        self.focus_set()
        i = self.top + int((e.y - 3) // self.line)
        if 0 <= i < len(self.rows):
            self.select(i)

    def refresh(self):
        self._draw()

    def _draw(self):
        self.delete("all")
        f, line = self._font, self.line
        w = f.measure("n") * self.width_chars
        h = line * self.rows_visible + 6
        super().configure(width=w, height=h)
        self.round_rect(1, 1, w - 1, h - 1, 10, fill=PALETTE["surface"], outline=PALETTE["border"], tags="frame")
        date_w = f.measure("today 00:00")
        info_x = w - 16 - date_w - f.measure("n") * 2
        ls = f.metrics("linespace")
        icon = max(10, round(ls * 0.9))                   # the icon and the room after it grow with the text
        name_x = 14 + icon + max(12, round(ls * 0.8))
        for k in range(self.rows_visible):
            i = self.top + k
            if i >= len(self.rows):
                break
            row, y = self.rows[i], 3 + k * line
            if i == self.index:
                self.round_rect(6, y + 1, w - 6, y + line - 1, 8, fill=PALETTE["select_bg"], tags="sel")
            ink = PALETTE["disabled"] if row.get("dim") else PALETTE["text"]
            mark = row.get("icon", "")
            if mark in ICONS:
                tint = PALETTE["disabled"] if row.get("dim") else PALETTE["muted"]
                self.create_image(14, int(y + (line - icon) / 2), image=self.icon_image(mark, icon, tint),
                                  anchor="nw", tags="icon")
            elif mark:
                self.create_text(14, y + line / 2, text=mark, font=f, fill=PALETTE["muted"], anchor="w", tags="icon")
            name = row["name"]
            if row.get("info"):                           # the room the name has, up to the next column
                room = info_x - f.measure(row["info"]) - 20 - name_x
            elif row.get("date"):
                room = w - 16 - date_w - 16 - name_x
            else:
                room = w - 16 - name_x
            while f.measure(name) > room and len(name) > 4:       # long names are cut in the middle
                name = name[: len(name) // 2 - 1] + "\u2026" + name[len(name) // 2 + 1:]
                if f.measure(name) <= room:
                    break
            self.create_text(name_x, y + line / 2, text=name, font=f, fill=ink, anchor="w", tags=("name", f"name{i}"))
            if row.get("info"):
                self.create_text(info_x, y + line / 2, text=row["info"], font=f, fill=PALETTE["muted"], anchor="e")
            if row.get("date"):
                self.create_text(w - 16, y + line / 2, text=row["date"], font=f, fill=PALETTE["muted"], anchor="e")
        if len(self.rows) > self.rows_visible:            # a quiet scroll mark down the right edge
            frac, size = self.top / max(1, len(self.rows) - self.rows_visible), self.rows_visible / len(self.rows)
            bar_h = max(16, (h - 12) * size)
            y0 = 6 + (h - 12 - bar_h) * frac
            self.round_rect(w - 7, y0, w - 4, y0 + bar_h, 1.5, fill=PALETTE["border"], tags="scrollmark")
        if not self.rows:
            self.create_text(w / 2, h / 2, text="Nothing here", font=f, fill=PALETTE["muted"], tags="empty")


class EmptyCard(SmoothCanvas):
    """A friendly "nothing to do here" card (UI-20): a soft rounded panel with a short title and a line of
    help, shown instead of greyed-out controls.

        card = EmptyCard(parent, font("title"), font("body"))
        card.set("No conflicts", "Nicely consistent. Nothing to look at here.")
    """

    def __init__(self, parent, title_font, body_font, width_chars=34, canvas_bg=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["bg"])
        self._tf, self._bf, self._chars = title_font, body_font, width_chars
        self.title = self.text = ""
        self._draw()

    def set(self, title, text):
        self.title, self.text = title, text
        self._draw()

    def _draw(self):
        self.delete("all")
        line = self._tf.metrics("linespace")
        pad, gap = int(line * 1.2), int(line * 0.35)
        wrap = self._bf.measure("n" * self._chars)
        t = self.create_text(0, 0, text=self.title, font=self._tf, fill=PALETTE["text"], anchor="n",
                             justify="center", width=wrap, tags="title")
        b = self.create_text(0, 0, text=self.text, font=self._bf, fill=PALETTE["muted"], anchor="n",
                             justify="center", width=wrap, tags="body")
        tb, bb = self.bbox(t), self.bbox(b)
        tw, th = (tb[2] - tb[0], tb[3] - tb[1]) if tb else (0, 0)
        bw, bh = (bb[2] - bb[0], bb[3] - bb[1]) if bb else (0, 0)
        w = max(tw, bw, wrap * 0.6) + 2 * pad
        h = th + gap + bh + 2 * int(pad * 0.8)
        super().configure(width=w + 2, height=h + 2)
        self.round_rect(1, 1, w, h, min(22, h // 3), fill=PALETTE["surface2"], outline=PALETTE["border"], tags="panel")
        top = 1 + int(pad * 0.8)
        self.coords(t, 1 + w / 2, top)
        self.coords(b, 1 + w / 2, top + th + gap)
        self.tag_raise("title")
        self.tag_raise("body")

    def refresh(self):
        self._draw()


class WordCard(SmoothCanvas):
    """The word being sorted: big text on a soft rounded white card with a faint shadow, and a muted
    sub-line under it (frequency rank, "skipped", "compound").

        card = WordCard(parent, font("word"), font("body"))
        card.set("serendipity", "frequency rank #4,321")

    * The card's size never depends on the word: only on the two fonts and the room it is given
      (configure(wraplength=) = the widest the text may be). So nothing around it moves from word to word
      (reported more than once: the tier buttons shifting or flashing while sorting fast, even with Reduce
      motion). It is CARD_CHARS letters of the word font wide (less if the room is smaller), always even,
      and tall enough for one line of the word and one of the sub-line.
    * A word too wide for it is drawn in a smaller copy of the font (the shared font is never touched); below
      MIN_SCALE of the size it wraps, still inside the one line's height. A sub-line too wide shrinks the same
      way, then is cut short with "...".
    * `word` / `sub` read the current text; refresh() re-measures after the shared fonts were resized.
    * UI-51: a little magnifier in the top-right corner (on_find() when clicked). begin_typing() turns the card
      into the place to type a word: type_key(event) takes the keys, Enter calls on_enter(text), Escape (or the
      magnifier again) puts the word back; note(text, animator) says something under it and shakes the card.
    * ST-6: set(word, sub, censor=True) shows the word smeared sideways (Censor obscene words); with the pointer
      over it, it un-smears (Unsmear; `animator` is the App's, for the easing).
    * UI-59: set(..., kind="sexual") writes what kind of rude word it is faintly above it, in a row of its own: the
      card is KIND_ROOM of a sub-line taller for every word (so its size still never changes) and a word with a
      kind is drawn at KIND_SCALE of its size (asked for: a little of both, so the kind has room).
    """
    KIND_FADE = 0.45        # how far toward the card the kind's colour is (a see-through look: Tk has no alpha)
    KIND_ROOM = 0.9         # extra card height for the kind's row, in sub-line heights (on every card)
    KIND_GAP = 0.3          # clear space between the kind's row and the word's line, in sub-line heights
    KIND_SCALE = 0.85       # a word with a kind above it is drawn this much smaller
    TYPE_HINT = "Enter: sort it  \u00b7  Esc: back"
    PLACEHOLDER = "type a word"
    SHADOW = 4
    CARD_CHARS = 12
    MIN_SCALE = 0.35
    MIN_SUB_SCALE = 0.75

    def __init__(self, parent, word_font, sub_font, wraplength=0, radius=26, canvas_bg=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["bg"])
        self._wfont, self._sfont = word_font, sub_font
        # the fonts the text is actually drawn in (sized to fit this word), and the outgoing word's
        self._fit, self._fit_sub, self._old_font = word_font.copy(), sub_font.copy(), word_font.copy()
        self._kind_font = sub_font.copy()
        self._kind = None
        self._fit_wrap = 0             # 0, or the width the current word wraps at
        self._word, self._sub, self._wrap = "", "", wraplength
        self._radius = radius
        self._frame, self._p = None, 0.0   # the running transition's frame (re-applied after a redraw) and its stage
        self._box = None                   # (width, height) last given to the canvas
        self.on_find = self.on_enter = None
        self.typing, self._typed, self._saved = False, "", None
        self._find_hover = False
        self._censor = self._old_censor = False
        self.smear = Unsmear(self, "smear")
        self.animator = None
        self.bind("<Motion>", self._on_motion, add="+")
        self.bind("<Leave>", lambda e: self.smear.hover(False, self.animator), add="+")
        self.tag_bind("find", "<Button-1>", lambda e: self.on_find and self.on_find())
        self.tag_bind("find", "<Enter>", lambda e: self._hover_find(True))
        self.tag_bind("find", "<Leave>", lambda e: self._hover_find(False))
        self.bind("<Configure>", lambda e: self._draw())
        self._draw()

    @property
    def padx(self):
        """Side padding in pixels; it follows the word font, so the card shrinks with the text."""
        return int(self._wfont.metrics("linespace") * 0.6)

    @property
    def _pady(self):
        return int(self._wfont.metrics("linespace") * 0.2)

    def box(self):
        """(width, height) of the card for the current fonts and room; the same for every word."""
        line, sline = self._wfont.metrics("linespace"), self._sfont.metrics("linespace")
        inner = self._wfont.measure("n" * self.CARD_CHARS)
        if self._wrap > 0:
            inner = min(inner, self._wrap)
        w = inner + 2 * self.padx + self.SHADOW
        w += w % 2                                 # even: centring it never lands on half a pixel
        h = line + int(sline * 0.4) + sline + int(sline * self.KIND_ROOM) + 2 * self._pady + self.SHADOW
        return w, h

    @property
    def word(self):
        return self._word

    @property
    def sub(self):
        return self._sub

    @property
    def censored(self):
        return self._censor

    @property
    def kind(self):
        return self._kind

    def set(self, word, sub="", censor=False, kind=None):
        """Show `word` with the muted line `sub` under it; `censor`: smeared until the pointer is over it; `kind`:
        the faint label above it. While a word is being typed on the card (begin_typing) it is kept for afterwards
        instead: end_typing shows it (a refresh meanwhile neither hides what is typed nor brings back an old word)."""
        if self.typing:
            self._saved = (word, sub, censor, kind)
            return
        self._put(word, sub, censor, kind)

    def _put(self, word, sub="", censor=False, kind=None):
        self._kind = kind
        self._old_font.configure(**self._fit.actual())      # (transition_from draws the outgoing word as it was)
        self._old_wrap, self._old_censor = self._fit_wrap, self._censor
        if word != self._word or censor != self._censor:
            self.smear.clear = self.smear._target = 0.0      # a new word starts smeared (the old one leaves so)...
        self._word, self._sub, self._censor = word, sub, censor
        self._draw()
        if censor:                                          # ...and un-smears at once if the pointer is already on
            self.after_idle(self._pointer_check)            # it (asked for: no need to nudge the mouse)

    def _on_motion(self, e):
        self._hover_at(e.x, e.y)

    def _hover_at(self, x, y):
        """The pointer at (x, y) over the word (its line, a little wider than the text) un-smears a censored one."""
        if not self._censor:
            return
        box = self.bbox(self.smear.tag) or self.bbox("word")
        pad = self._sfont.metrics("linespace") // 2
        self.smear.hover(bool(box) and box[0] - pad <= x <= box[2] + pad and box[1] <= y <= box[3], self.animator)

    def _pointer_check(self):
        """Where the pointer is now, without waiting for it to move (a new word appears under a still pointer)."""
        try:
            px, py = self.winfo_pointerxy()
            if self.winfo_containing(px, py) is self:
                self._hover_at(px - self.winfo_rootx(), py - self.winfo_rooty())
        except (tk.TclError, KeyError):
            pass                                            # (closed meanwhile, or the pointer over a menu)

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

    TRANSITION_MS = 180

    def transition_from(self, old_word, old_sub, dx, dy, animator):
        """UI-16: call right after set() showed the next word. The previous word is drawn on top where it was,
        nudges (dx, dy) pixels (toward the tier it went to) while fading into the card, and the new word
        eases in from a few pixels below. Never blocks: Animator.finish_all (any key) jumps to the end."""
        if animator is None or animator.reduce_motion or not old_word:
            return
        self.delete("old")
        if not self.coords("word"):
            return
        # the old text, as it was drawn: its own size, centred in the word's line (the card itself does not move)
        cx, top, sub_y = self._layout
        old = self.create_text(cx, 0, text=old_word, font=self._old_font, fill=PALETTE["text"],
                               width=getattr(self, "_old_wrap", 0), justify="center", anchor="n",
                               tags=("old", "oldword"))
        ob = self.bbox(old)
        ow = [cx, top + (self._line - (ob[3] - ob[1] if ob else 0)) / 2]
        self.coords(old, *ow)
        smeared = None
        if self._old_censor and self.smear.clear < 1:   # a censored word leaves as its smear, never readable
            smear_items(self, old, PALETTE["text"], PALETTE["surface"], 1.0 - self.smear.clear, ("old", "oldsmear"))
            self.itemconfigure(old, state="hidden")
            smeared = [0, 0]                            # (how far it has moved so far)
        osub = None
        if old_sub and sub_y is not None:
            osub = [cx, sub_y]
            self.create_text(*osub, text=old_sub, font=self._fit_sub, fill=PALETTE["muted"], justify="center",
                             anchor="n", tags=("old", "oldsub"))
        self.tag_raise("old", "word")              # on top while it is the darker one (frame swaps them halfway)
        rise = max(4, self._wfont.metrics("linespace") // 10)
        card = PALETTE["surface"]

        def frame(p):
            self._p = p
            self.coords("oldword", ow[0] + dx * p, ow[1] + dy * p)
            if smeared:
                self.move("oldsmear", round(dx * p) - smeared[0], round(dy * p) - smeared[1])
                smeared[:] = [round(dx * p), round(dy * p)]
                self.itemconfigure("oldsmear", state="normal" if p < 0.4 else "hidden")
            if osub:
                self.coords("oldsub", osub[0] + dx * p, osub[1] + dy * p)
            # a crossfade: the new word comes in exactly as the old one goes, so between them there is always one
            # word's worth of ink (it used to start late, and for a few frames the card flashed empty white)
            gone = min(1.0, p / 0.55)
            q = gone
            back = rise * (1 - q)                # it rises into place (from the latest layout)
            wx, wy, sy = self._word_xy[0], self._word_xy[1], self._layout[2]
            self.coords("word", wx, wy + back)
            if sy is not None:
                self.coords("sub", wx, sy + back)
            # tk cannot blend two texts: a pale one drawn over a dark one cuts white gaps through its letters
            # (reported: a "white text version" of the word), so the darker of the two is always on top
            for old_tag, new_tag in (("oldword", "word"), ("oldsub", "sub")):
                if self.find_withtag(old_tag) and self.find_withtag(new_tag):
                    if gone < 0.5:
                        self.tag_raise(old_tag, new_tag)
                    else:
                        self.tag_raise(new_tag, old_tag)
            self.itemconfigure("oldword", fill=lerp_color(PALETTE["text"], card, gone))
            self.itemconfigure("oldsub", fill=lerp_color(PALETTE["muted"], card, gone))
            self.itemconfigure("word", fill=lerp_color(card, PALETTE["text"], q))
            self.itemconfigure("sub", fill=lerp_color(card, PALETTE["muted"], q))
            self.itemconfigure("kind", fill=lerp_color(card, self._kind_color(), q))
            if self._censor:                      # (the smear rises with its word)
                self.smear.paint()

        def done():
            if self._frame is frame:              # (a newer transition, started over this one, cleans up itself)
                self._frame = None
                self.delete("old")
        self._frame, self._p = frame, 0.0
        try:
            animator.run(f"card{id(self)}", self.TRANSITION_MS, frame, done)
        except tk.TclError:
            pass

    def _size_kind(self):
        """Size the kind's font (a little smaller than the sub-line's) and return the height of its row, with KIND_GAP
        clear under it (tall letters reach the top of the word's line: their smear touched the kind)."""
        sign = -1 if self._sfont.cget("size") < 0 else 1
        a = self._sfont.actual()
        self._kind_font.configure(family=a["family"], weight=a["weight"], slant=a["slant"],
                                  size=sign * max(5, int(round(abs(self._sfont.cget("size")) * 0.85))))
        return self._kind_font.metrics("linespace") + int(self._sfont.metrics("linespace") * self.KIND_GAP)

    def _draw_kind(self, bw, top):
        """The kind, in its own row from `top`, kept KIND_GAP clear of the tops of the word's letters (the tallest,
        accents too, stand about 0.82 em above the baseline: the line's box starts barely above them)."""
        pt = self._fit.cget("size")
        em = -pt if pt < 0 else pt * float(self.tk.call("tk", "scaling"))     # (in pixels)
        ink_top = self._word_xy[1] + self._fit.metrics("ascent") - 0.82 * em
        half = self._kind_font.metrics("linespace") / 2
        y = min(top + half, ink_top - int(self._sfont.metrics("linespace") * self.KIND_GAP) - half)
        self.create_text(bw / 2, max(3 + half, y), text=self._kind, font=self._kind_font, fill=self._kind_color(),
                         anchor="center", tags="kind")

    def _kind_color(self):
        return lerp_color(PALETTE["muted"], PALETTE["surface"], self.KIND_FADE)

    def _fit_word(self, avail, line, scale=1.0):
        """Size the drawing font for the current word: the full size (times `scale`) if it fits on one line in
        `avail` pixels, else smaller (down to MIN_SCALE), else wrapped at `avail` and as big as still fits in `line`
        pixels of height. Sets self._fit and self._fit_wrap."""
        base = self._wfont
        full = base.cget("size")
        sign = -1 if full < 0 else 1               # (a negative size is in pixels)
        full = max(6, round(abs(full) * scale))
        a = base.actual()
        self._fit.configure(family=a["family"], weight=a["weight"], slant=a["slant"], size=sign * full)
        self._fit_wrap = 0
        need = self._fit.measure(self._word)
        if need <= avail or not self._word:
            return
        floor = max(6, int(full * self.MIN_SCALE))
        size = max(floor, int(full * avail / need))
        self._fit.configure(size=sign * size)
        while size > floor and self._fit.measure(self._word) > avail:
            size -= 1
            self._fit.configure(size=sign * size)
        if self._fit.measure(self._word) <= avail:
            return
        self._fit_wrap = avail                       # still too long: wrap, as big as fits the line's height
        probe = self.create_text(0, 0, text=self._word, font=self._fit, width=avail, anchor="nw")
        while size > 6:
            b = self.bbox(probe)
            if b and b[3] - b[1] <= line:
                break
            size -= 1
            self._fit.configure(size=sign * size)
        self.delete(probe)

    def _fit_subline(self, avail):
        """Size the sub-line's font (down to MIN_SUB_SCALE), then cut it short with "..." if it still does not fit."""
        base = self._sfont
        full = base.cget("size")
        sign, full = (-1 if full < 0 else 1), abs(full)
        a = base.actual()
        self._fit_sub.configure(family=a["family"], weight=a["weight"], slant=a["slant"], size=sign * full)
        text = self._sub
        need = base.measure(text)
        if need <= avail:
            return text
        size = max(6, int(full * self.MIN_SUB_SCALE), int(full * avail / need))
        self._fit_sub.configure(size=sign * size)
        while self._fit_sub.measure(text) > avail and len(text) > 1:
            text = text[:-2].rstrip() + "\u2026"
        return text

    def _draw(self):
        for item in self.find_all():          # everything but a transition's outgoing word (a resize must not
            if "old" not in self.gettags(item):   # wipe it: the card flashed blank white, reported)
                self.delete(item)
        w, h = self.box()
        if self._box != (w, h):               # only when the fonts or the room changed, never for a new word
            self._box = (w, h)
            super().configure(width=w, height=h)
        bw, bh = w - self.SHADOW, h - self.SHADOW
        line, sline = self._wfont.metrics("linespace"), self._sfont.metrics("linespace")
        avail = bw - 2 * self.padx
        labelled = bool(self._kind) and not self.typing
        kind_row = self._size_kind() if labelled else 0      # (the kind's own row, above the word's line)
        if labelled:
            line = int(line * self.KIND_SCALE)
        self._fit_word(avail, line, self.KIND_SCALE if labelled else 1.0)
        r = max(6, min(self._radius, bh // 2))
        # the shadow is drawn in the card's own image (one solid image: much cheaper to draw); this invisible
        # item only marks where it is
        self.create_polygon(1 + self.SHADOW, 1 + self.SHADOW, bw + self.SHADOW - 1, 1 + self.SHADOW,
                            bw + self.SHADOW - 1, bh + self.SHADOW - 1, 1 + self.SHADOW, bh + self.SHADOW - 1,
                            fill="", outline="", tags="shadow")
        self.round_rect(1, 1, bw - 1, bh - 1, r, fill=PALETTE["surface"], outline=PALETTE["border"], tags="card",
                        shadow=(PALETTE["shadow"], self.SHADOW, self.SHADOW))
        # fixed rows: the word's line, a gap, the sub-line's line, the whole block centred in the card
        gap = int(sline * 0.4)
        top = (bh - (kind_row + line + gap + sline)) / 2 + kind_row
        word = self.create_text(bw / 2, 0, text=self._word, font=self._fit, fill=PALETTE["text"],
                                width=self._fit_wrap, justify="center", anchor="n", tags="word")
        wb = self.bbox(word)
        th = wb[3] - wb[1] if wb else 0
        self._word_xy = (bw / 2, top + (line - th) / 2)
        self.coords(word, *self._word_xy)
        sub_y = None
        if self._sub:
            sub_y = top + line + gap + (sline - self._fit_sub.metrics("linespace")) / 2
            self.create_text(bw / 2, sub_y, text=self._fit_subline(avail), font=self._fit_sub,
                             fill=PALETTE["muted"], justify="center", anchor="n", tags="sub")
        self._layout = (bw / 2, top, sub_y)          # (transition_from: the word's line and the sub-line)
        self._line = line
        if labelled:
            self._draw_kind(bw, top - kind_row)
        self.smear.place(word, self._word if self._censor and not self.typing else None, PALETTE["text"],
                         PALETTE["surface"])
        if self.find_withtag("old"):
            self.tag_raise("old", "card")        # on the card (not under it), below the new word
        self.tag_raise("word")
        self.tag_raise(self.smear.tag)
        self.tag_raise("sub")
        self.tag_raise("kind")                # over the smear: its cut-off strips, the height of the word's line, hid
                                              # the ends of a kind wider than the word ("sexual" over "cum")
        if self._frame is not None:           # mid-transition: put the moving words back where they were
            self._frame(self._p)
        self._draw_find(bw, r)
        if self.typing:                       # a thin lilac caret after the typed word (before the pale prompt)
            wb = self.bbox("word")
            if wb:
                empty = not self._typed
                if empty:
                    self.itemconfigure("word", fill=PALETTE["disabled"])
                cx = (wb[0] - 3) if empty else (wb[2] + 3)
                self.create_line(cx, top + line * 0.18, cx, top + line * 0.86, fill=PALETTE["accent"],
                                 width=max(2, line // 20), tags="caret")

    # ---- looking up a word (UI-51) ------------------------------------------------------------------------
    def find_box(self):
        """Where the magnifier is: (x, y, size) in the card."""
        bw = (self._box or self.box())[0] - self.SHADOW
        size = max(12, round(self._sfont.metrics("linespace") * 0.95))
        inset = max(8, round(min(self._radius, (self._box or self.box())[1] // 2) * 0.5))
        return bw - inset - size, inset, size

    def _draw_find(self, bw, r):
        """The magnifier: drawn once, then only moved and recoloured. Never deleted and made again here: called from
        its own Enter / Leave, a new item under the pointer is entered again, and Tk looped on that for good
        (reported: the program froze, hovering it; F-21)."""
        x, y, size = self.find_box()
        ink = PALETTE["accent"] if self.typing else (PALETTE["text"] if self._find_hover else PALETTE["muted"])
        image = self.icon_image("search", size, ink)
        items = self.find_withtag("find")
        if items:
            self.coords(items[0], x, y)
            self.itemconfigure(items[0], image=image)
            self.tag_raise("find")
        else:
            self.create_image(x, y, image=image, anchor="nw", tags="find")

    def _hover_find(self, on):
        self._find_hover = on
        self.configure(cursor="hand2" if on else "")
        if self._box:
            self._draw_find(self._box[0] - self.SHADOW, self._radius)

    def begin_typing(self):
        """The card becomes the place to type a word (the word it showed comes back with end_typing)."""
        if self.typing:
            return
        self.typing, self._typed, self._saved = True, "", (self._word, self._sub, self._censor, self._kind)
        self._show_typed(self.TYPE_HINT)

    def end_typing(self, restore=True):
        if not self.typing:
            return
        self.typing = False
        if restore and self._saved is not None:
            self.set(*self._saved)
        self._saved = None

    @property
    def typed(self):
        """What has been typed so far (tests)."""
        return self._typed

    def _show_typed(self, sub):
        self._put(self._typed or self.PLACEHOLDER, sub)

    def type_key(self, e):
        """A key while typing: letters and the like add to the word, Backspace takes one off, Enter asks
        on_enter(text), Escape goes back to the word."""
        ks, ch = e.keysym, getattr(e, "char", "") or ""
        if ks in ("Return", "KP_Enter"):
            if self.on_enter:
                self.on_enter(self._typed.strip())
            return
        if ks == "Escape":
            self.end_typing()
            return
        if ks == "BackSpace":
            self._typed = self._typed[:-1]
        elif len(ch) == 1 and ch.isprintable() and len(self._typed) < 60 and (ch != " " or self._typed):
            self._typed += ch
        else:
            return
        self._show_typed(self.TYPE_HINT)

    SHAKE_MS = 320

    def note(self, text, animator=None):
        """Say `text` under the typed word and give the card a little side-to-side "no" shake (none with Reduce
        motion: the words say it)."""
        self._show_typed(text)
        if animator is None or animator.reduce_motion:
            return
        moved = [0]

        def frame(p):
            dx = round(7 * math.sin(p * 3 * 2 * math.pi) * (1 - p))
            if dx != moved[0]:
                self.move("all", dx - moved[0], 0)
                moved[0] = dx

        def done():
            if moved[0]:
                self.move("all", -moved[0], 0)
                moved[0] = 0
        animator.run(f"cardshake{id(self)}", self.SHAKE_MS, frame, done, ease=lambda t: t)


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


def close_popups():
    """Close every drop-down the program has open (UI-43): all DropMenus (header menus, ChoiceButtons). Called
    when the program loses focus, so nothing is left floating in front of another program."""
    for menu in list(DropMenu.open_menus):
        menu.close()


def watch_focus(root, on_lost=None):
    """When the whole program loses focus (another program came to the front), close its drop-downs
    (close_popups) and call on_lost(). Moving focus between the program's own windows does nothing.
    (ttk drop-down lists cannot be closed this way: they grab all input, so no focus event arrives at
    all; the program uses ChoiceButton instead.)"""
    state = {"job": None}

    def check():
        state["job"] = None
        try:
            # ask Tcl, not focus_get(): while a ttk drop-down list is open the focus is in its pop-down,
            # which tkinter does not know, and focus_get() raises instead of answering
            focused = root.tk.call("focus")
        except tk.TclError:
            return
        if not str(focused):
            close_popups()
            if on_lost:
                on_lost()

    def later(_e):
        if state["job"] is None:
            state["job"] = root.after(120, check)
    root.bind_all("<FocusOut>", later, add="+")
    return check


def dialog_open(root):
    """True while one of our dialogs (StyledDialog: a question, a message, a settings page) is on screen."""
    try:
        return any(getattr(w, "styled_dialog", False) and w.winfo_viewable() for w in root.winfo_children())
    except tk.TclError:
        return False


class StyledDialog:
    """The shared dialog frame (UI-24): a bold headline, a muted line of explanation, a body to fill and
    a row of rounded buttons, the default one (what Enter presses) in lilac and on the right.

        dlg = StyledDialog(parent, "Anchor words", "Pick one word per tier", "New words are compared...")
        ttk.Entry(dlg.body, ...).pack()
        dlg.button("Cancel", dlg.close)
        dlg.button("Save anchors", save, default=True)
        dlg.show()                    # centre over the parent and take the input; wait=True blocks

    Buttons line up left to right in the order added, at the right edge (side="left" puts one at the
    far left instead, like "Show details"). Escape and the close box call on_cancel (default: close).
    """

    def __init__(self, parent, title, headline=None, intro=None, animator=None, wrap_chars=52):
        self.parent, self._anim, self._default = parent, animator, None
        self.on_cancel = self.close
        bg = PALETTE["bg"]
        self.win = tk.Toplevel(parent)
        self.win.styled_dialog = True            # (a question or message is open: dialog_open)
        self.win.dialog = self                   # (refresh_widgets: an open dialog follows a new text size)
        self._wrap_chars = wrap_chars
        # hidden until show() has sized and centred it: built while showing, it appeared where the window
        # manager put it (the parent's top left) and then jumped to the middle
        self.win.withdraw()
        self.win.title(title)
        self.win.configure(bg=bg)
        self.win.resizable(False, False)
        try:
            if parent.winfo_viewable():
                self.win.transient(parent)
        except tk.TclError:
            pass
        self.wrap = max(380, font("body").measure("n") * wrap_chars)
        box = tk.Frame(self.win, bg=bg, padx=26, pady=22)
        box.pack(fill="both", expand=True)
        if headline:
            tk.Label(box, text=headline, font=font("head"), bg=bg, fg=PALETTE["text"], wraplength=self.wrap,
                     justify="left").pack(anchor="w")
        if intro:
            tk.Label(box, text=intro, font=font("body"), bg=bg, fg=PALETTE["muted"], wraplength=self.wrap,
                     justify="left").pack(anchor="w", pady=(8 if headline else 0, 0))
        self.body = tk.Frame(box, bg=bg)
        self.body.pack(fill="both", expand=True, pady=(14 if headline or intro else 0, 0))
        self.button_row = tk.Frame(box, bg=bg)
        self.button_row.pack(fill="x", pady=(18, 0))
        self._right = tk.Frame(self.button_row, bg=bg)
        self._right.pack(side="right")
        self.buttons = {}
        self.win.bind("<Return>", lambda e: self._default.invoke() if self._default else None)
        self.win.bind("<Escape>", lambda e: self.on_cancel())
        self.win.protocol("WM_DELETE_WINDOW", lambda: self.on_cancel())

    def text(self, text, muted=False, parent=None, room=0, **pack):
        """A wrapped line of text in the body (or `parent`), packed to the left (`pack`: more pack options); muted
        for notes. `room`: pixels to leave beside it. Returns the label (its text can change later)."""
        label = ttk.Label(parent or self.body, text=text, wraplength=self.wrap - room, justify="left",
                          **({"foreground": PALETTE["muted"]} if muted else {"font": font("body")}))
        label.pack(**dict({"anchor": "w"}, **pack))
        return label

    def button(self, text, command, default=False, side="right"):
        """Add a rounded button; `default` makes it the lilac one Enter presses."""
        row = self._right if side == "right" else self.button_row
        b = RoundButton(row, text, command, bg=PALETTE["select_bg"] if default else PALETTE["surface"],
                        font=font("body"), padx=16, pady=6, radius=12, animator=self._anim)
        b.pack(side="left", padx=(8, 0) if row is self._right and self.buttons else 0)
        self.buttons[text] = b
        if default:
            self._default = b
        return b

    def clear_buttons(self):
        """Take every button (and anything else in the button row) away, to put others there (a page of steps)."""
        for w in (*self.button_row.winfo_children(), *self._right.winfo_children()):
            if w is not self._right:
                w.destroy()
        self.buttons, self._default = {}, None

    def show(self, wait=False):
        """Size to the contents, centre over the parent, then appear there; take the input (and with wait, block
        until closed)."""
        place_dialog(self.win, self.parent)
        self.win.deiconify()
        try:                             # some Linux window managers refuse a grab before the window shows
            self.win.wait_visibility()
            self.win.grab_set()
        except tk.TclError:
            pass
        self.win.lift()                  # in front, even of a window that was raised a moment before
        self.win.focus_force()
        if wait:
            self.win.wait_window()

    def refit(self):
        """Re-size to the contents after something was shown or hidden, kept on its monitor (a dialog that grew
        could run off the bottom of a small screen)."""
        self.win.update_idletasks()
        self.win.geometry("")
        keep_on_screen(self.win)

    def rescale(self):
        """The shared fonts were resized while it is open (the main window's zoom: maximizing brings back its own,
        UI-57): every wrapped line is re-wrapped in proportion to the new text size, then the dialog is sized to
        its contents again and centred over its parent, kept on its monitor. Before, the text grew inside a
        window that kept its size and was cut off (reported)."""
        wrap = max(380, font("body").measure("n") * self._wrap_chars)
        ratio = wrap / self.wrap if self.wrap else 1.0
        self.wrap = wrap
        if ratio != 1.0:
            stack = [self.win]
            while stack:
                w = stack.pop()
                stack.extend(w.winfo_children())
                try:
                    if isinstance(w, (tk.Label, ttk.Label)) and int(str(w.cget("wraplength")) or 0) > 0:
                        w.configure(wraplength=max(1, round(int(str(w.cget("wraplength"))) * ratio)))
                except (tk.TclError, ValueError):
                    pass
        def place():                    # (after the parent's own new size is settled: maximizing moves it too)
            try:
                if self.win.winfo_viewable():
                    place_dialog(self.win, self.parent)
            except tk.TclError:
                pass
        place()
        self.win.after_idle(place)

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def alive(self):
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False


def refresh_widgets(widget):
    """Re-measure every canvas widget of ours (RoundButton, WordCard, AnchorLadder, TabBar, the chart...) under
    `widget` after shared fonts were resized; an open dialog (StyledDialog) then re-wraps and resizes itself."""
    for child in widget.winfo_children():
        if isinstance(child, tk.Canvas) and callable(getattr(child, "refresh", None)):
            child.refresh()                  # our canvas widgets (here and in ui_chart.py) all have refresh()
        else:
            refresh_widgets(child)
            dialog = getattr(child, "dialog", None)
            if isinstance(dialog, StyledDialog):
                dialog.rescale()
