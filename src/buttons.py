"""The program's buttons, drawn on canvases with smoothed rounded corners (Canvas, not tk.Button or ttk, so the colours
look the same on macOS, Windows and Linux): RoundButton (UI-5) and the tier pills (TierRow, TierChip), the small icon
link (LinkButton), the censor pill (SmearToggle), the yes button naming a smeared word (SmearWordButton) and the
developer tools' bubbles (DevBubble). EDGE is a button's or pill's edge: its fill this far toward the ink.
"""
import tkinter as tk
import tkinter.font as tkfont

from fonts import font
from smooth import SmoothCanvas
from theme import PALETTE, TIER_COLORS, TIER_TEXT, ink_on, is_light, mix
from ui_motion import lerp_color
from popups import Tooltip
from smears import Unsmear, smear_items


HOVER_MS = 120          # colour fade when the pointer enters or leaves
DIP = 2                 # pixels the button sinks while pressed
_CUSTOM = ("text", "hint", "font", "wraplength", "bg", "fg", "censor")


EDGE = 0.07     # a button's or pill's edge: its fill this far toward the ink (UI-78: softer, asked for; it was 0.14)


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
    * `hint_font`: a Font for the caption (default: 77% of the label font, which is too big on big cards).
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
        # (drawn again only for a size it was not drawn for: a button shown at the size it asked for was drawn
        # twice, once when made and again when laid out, the most costly part of opening a dialog)
        self.bind("<Configure>", lambda e: (e.width, e.height) != self._drawn and self._draw())

    # ---- options ------------------------------------------------------------------------------
    def configure(self, cnf=None, **kw):
        """Label-style options (text, hint, font, wraplength, bg, fg) plus the normal Canvas ones."""
        kw = dict(cnf or {}, **kw)
        mine = {k: kw.pop(k) for k in _CUSTOM if k in kw}
        if mine.get("wraplength", None) == self._wrap:    # (the same wrap: no redraw; a re-fit sets it every time)
            del mine["wraplength"]
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
            if self._anim is not None and ("bg" in mine or "fg" in mine):
                self._anim.stop(f"rb{id(self)}")     # (a fade still running would end at the old colour: the
                                                     # review's lit kind showed the meaning before, reported)
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
        edge = lerp_color(fill, PALETTE["text"], EDGE)
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

    def veil(self, amount, color=None):
        """Paint it faded `amount` (0 = as it is, 1 = gone) into `color` (default: the colour behind it), its state
        untouched: for a fade an owner runs frame by frame (DuelCards.show). Any fade of its own stops."""
        if self._anim is not None:
            self._anim.stop(f"rb{id(self)}")
        color = color or super().cget("bg")
        fill, edge, width, fg = self._target()
        self._look = (lerp_color(fill, color, amount), lerp_color(edge, color, amount), width,
                      lerp_color(fg, color, amount))
        self._paint()

    def _paint(self):
        """Apply self._look to the items (colours only; geometry is _draw)."""
        fill, edge, width, fg = self._look
        try:
            self.itemconfigure("shape", fill=fill, outline=edge, width=width)
            self.itemconfigure("hint", fill=fg)     # (the key in the ink too, UI-76: paler, it was 3.4:1 on a pastel)
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
        hs = int(round(s * 0.77))           # (9-10 pt under 12-13 pt text: about fonts' small size)
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
        self._drawn = (w, h)
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
        self.round_rect(1, 1, w, h, h // 2 - 1, fill=self._color, outline=lerp_color(self._color, TIER_TEXT, EDGE))
        self.create_text(1 + w / 2, 1 + h / 2, text=self._text, font=self._font, fill=TIER_TEXT)   # (dark ink on a
                                                                                                 # pastel, dark mode too)

    def refresh(self):
        self._draw()

    def set_color(self, color):
        """Another tier colour (Tier colours, UI-61: the pill as it will look)."""
        self._color = color
        self._draw()


class LinkButton(SmoothCanvas):
    """A small icon (smooth.ICONS) that does something when clicked, muted until hovered, with a hover note: the
    Wiktionary link at the top right of a definition (asked for). With `text` (in `font`), the words come first and
    the icon after them, and hovering darkens both to the text colour: the GitHub link in the menu bar (UI-75).

        LinkButton(parent, "external", command, note="Open on Wiktionary", size=16, bg=PALETTE["surface"])
        LinkButton(bar, "external", command, text="GitHub", font=font("body"), bg=PALETTE["surface"])
    """

    def __init__(self, parent, icon, command, note=None, size=16, bg=None, text=None, font=None):
        bg = bg or PALETTE["surface"]
        super().__init__(parent, width=size + 6, height=size + 6, bd=0, highlightthickness=0, bg=bg, cursor="hand2")
        self.icon, self.command, self.size = icon, command, size
        self.text, self._font = text, font
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
        if not self.text:
            ink = PALETTE["accent"] if self._hover else PALETTE["muted"]
            self.create_image(3, 3, image=self.icon_image(self.icon, self.size, ink), anchor="nw")
            return
        ink = PALETTE["text"] if self._hover else PALETTE["muted"]
        f = self._font or tkfont.nametofont("TkDefaultFont")
        size = max(10, int(f.metrics("linespace") * 0.7))
        tw, h = f.measure(self.text), max(f.metrics("linespace"), size) + 6
        gap = max(4, size // 3)
        self.configure(width=3 + tw + gap + size + 3, height=h)
        self.create_text(3, h / 2, text=self.text, font=f, fill=ink, anchor="w")
        self.create_image(3 + tw + gap, (h - size) / 2, image=self.icon_image(self.icon, size, ink), anchor="nw")
        self.size = size

    def refresh(self):
        self._draw()


class SmearToggle(SmoothCanvas):
    """A small pill holding "abc", smeared while `variable` is True and plain while it is False; a click (or Space /
    Return once it has focus) flips it: the censor button beside each kind of rude meaning in How words are dealt
    (asked for: censoring each kind on its own; no hover note, asked for).

        SmearToggle(parent, tk.BooleanVar(value=True))
    """

    TEXT = "abc"

    def __init__(self, parent, variable, font_=None, bg=None):
        super().__init__(parent, bd=0, highlightthickness=1, takefocus=1, cursor="hand2",
                         bg=bg or PALETTE["bg"], highlightbackground=bg or PALETTE["bg"],
                         highlightcolor=PALETTE["accent"])
        self.variable, self._font, self._bg = variable, font_ or font("small"), bg
        self._hover = False
        for seq in ("<ButtonRelease-1>", "<space>", "<Return>"):
            self.bind(seq, lambda e: self.toggle())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self._trace = variable.trace_add("write", lambda *_: self._draw())
        self.bind("<Destroy>", lambda e: e.widget is self and self._untrace())
        self._draw()

    def _untrace(self):
        try:
            self.variable.trace_remove("write", self._trace)
        except tk.TclError:
            pass

    def toggle(self):
        self.variable.set(not self.variable.get())

    def _set_hover(self, on):
        self._hover = on
        self._draw()

    def _draw(self):
        self.delete("all")
        f, on = self._font, bool(self.variable.get())
        line = f.metrics("linespace")
        h = line + 4
        w = f.measure(self.TEXT) + line + 2
        super().configure(width=w + 2, height=h + 2)
        bg = self._bg or PALETTE["bg"]
        fill = PALETTE["select_bg"] if on else bg
        edge = PALETTE["accent"] if on or self._hover else PALETTE["border"]
        self.round_rect(1, 1, w, h, h, fill=fill, outline=edge)      # (r = h: a pill in smooth.py's corners)
        ink = PALETTE["text"] if on or self._hover else PALETTE["muted"]
        item = self.create_text(1 + (w - f.measure(self.TEXT)) / 2, 1 + (h - line) / 2, text=self.TEXT, font=f,
                                fill=ink, anchor="nw")              # (nw: smear_items reads a line's top left)
        if on:
            smear_items(self, item, ink, fill, 1.0, ("smear",))
            self.itemconfigure(item, state="hidden")

    def refresh(self):
        self._draw()


class SmearWordButton(SmoothCanvas):
    """A rounded button that says what a yes means (asked for: easy to tell yes from no; picked from a mock-up): its
    `text` on the left and the word on the right, smeared on the S tier's colour while on, plain on the surface
    colour while off, the key under the word. A click (or Space / Return once it has focus) runs `command`; a change
    gives a short bounce (none with Reduce motion). The review's "Smear the whole word".

        b = SmearWordButton(parent, "Smear the whole word", toggle, animator=app.anim); b.show("bugger", True)
    """
    BOUNCE = (-3, -2, -1, 0)      # pixels up, a frame each (BOUNCE_MS apart), when it changes
    BOUNCE_MS = 30

    def __init__(self, parent, text, command, font_=None, word_font=None, bg=None, animator=None):
        super().__init__(parent, bd=0, highlightthickness=1, takefocus=1, cursor="hand2",
                         bg=bg or PALETTE["bg"], highlightbackground=bg or PALETTE["bg"],
                         highlightcolor=PALETTE["accent"])
        self.text, self.command, self._anim = text, command, animator
        self._font, self._word_font = font_ or font("body"), word_font or font("heading")
        self.word, self.on, self.hint, self.enabled = "", False, "", True
        self._hover, self._lift, self._job = False, 0, None
        for seq in ("<ButtonRelease-1>", "<space>", "<Return>"):
            self.bind(seq, lambda e: self.invoke())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self._draw()

    def invoke(self):
        if self.enabled:
            self.command()

    def show(self, word, on):
        """Show `word`, smeared if `on`; a change of `on` for the same word bounces."""
        bounce = word == self.word and bool(on) != self.on
        self.word, self.on = word, bool(on)
        self._draw()
        if bounce and not getattr(self._anim, "reduce_motion", False):
            self._bounce(0)

    def set_hint(self, hint):
        self.hint = hint
        self._draw()

    def set_enabled(self, on):
        self.enabled = bool(on)
        super().configure(cursor="hand2" if on else "")
        self._draw()

    def _set_hover(self, on):
        self._hover = on
        self._draw()

    def _bounce(self, i):
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        self._lift = self.BOUNCE[i]
        self._draw()
        if i + 1 < len(self.BOUNCE):
            self._job = self.after(self.BOUNCE_MS, lambda: self._bounce(i + 1))

    def _draw(self):
        self.delete("all")
        f, wf, small = self._font, self._word_font, font("small")
        word = self.word or " "
        pad = f.metrics("linespace")
        wline, sline = wf.metrics("linespace"), small.metrics("linespace")
        h = wline + sline + 10
        ww = max(wf.measure(word), small.measure(self.hint))
        w = pad + f.measure(self.text) + pad + ww + pad
        super().configure(width=w + 2, height=h + 6)
        on = self.on and self.enabled
        fill = TIER_COLORS[0] if on else PALETTE["surface"]
        edge = PALETTE["accent"] if self._hover and self.enabled else (mix(fill, ink_on(fill), 0.3) if on else PALETTE["border"])
        y0 = 3 + self._lift
        self.round_rect(1, y0, w, y0 + h, 12, fill=fill, outline=edge)
        ink = ink_on(fill) if self.enabled else PALETTE["muted"]
        self.create_text(1 + pad, y0 + h / 2, text=self.text, font=f, anchor="w", fill=ink)
        cx = w - pad - ww / 2
        item = self.create_text(cx - wf.measure(word) / 2, y0 + 4, text=word, font=wf, anchor="nw", fill=ink)
        if on:                                    # (nw: smear_items reads a line's top left)
            smear_items(self, item, ink, fill, 1.0, ("smear",))
            self.itemconfigure(item, state="hidden")
        if self.hint:
            self.create_text(cx, y0 + 4 + wline + 1, text=self.hint, font=small, anchor="n",
                             fill=ink if self.enabled else PALETTE["muted"])

    def refresh(self):
        self._draw()


class DevBubble(SmoothCanvas):
    """A small lilac pill with a dot and a few words: a developer tool in a dialog's top right corner (asked for:
    dev tools reachable from the window, not only by command; only while Settings > Developer tools is ticked).
    A click (or Space / Return once it has focus) runs `command`. With `variable` it is a switch, lit while True.

    With `progress() -> None or (fraction or None, note)` it shows a tool that keeps running after the click (asked
    for, picked from a mock-up): while it runs the bubble is lit and a thin ring fills clockwise around the dot
    (a fraction), or a short arc goes round it (None: no way to tell how far); the hover note says how far it is;
    a click runs `on_running` (the tuner: its window back, asked for), or does nothing without one. When it ends the whole ring blinks once and the bubble is plain again. It asks every
    POLL_MS, so a dialog opened while the tool runs shows it too. Reduce motion: no spinning, no easing.

    With `second=(text, command)` it is split in two by a thin line (asked for, picked from a mock-up: one bubble
    for the review words): each half runs its own command, running or not (the commands know what to do then), and
    the half under the pointer has the darker text. progress() may give a third value, the second half's words
    while it runs ("Tuning · step 1 of 2").

    With `stop=(note, command)` a running tool can be stopped (asked for, picked from a mock-up): while the pointer
    is on the ring it turns into a small red cross on pink, the hover note says `note` (a string, or a function
    giving one), and a click runs `command`. The bubble never changes size for it.

        DevBubble(parent, "Log", app.devtools.open_log)
        DevBubble(parent, "Nightly", toggle, variable=shown)
        tools = app.devtools
        DevBubble(parent, "Review words", tools.review_words, progress=lambda: tools.progress("review"),
                  second=("Tune & reroll", tools.tune_reroll), stop=(tools.stop_note, tools.stop))
    """
    POLL_MS = 100
    SPIN_MS = 40              # a frame of the spinning arc (and of the ring easing to a new fraction)
    SPIN_STEP = 12            # degrees a frame: a turn in 1.2 s
    SPIN_ARC = 100            # the arc's length while it cannot tell how far
    BLINK_MS = 450            # the whole ring, once, when the tool ends

    def __init__(self, parent, text, command, variable=None, font_=None, bg=None, progress=None, animator=None,
                 on_running=None, second=None, stop=None):
        super().__init__(parent, bd=0, highlightthickness=1, takefocus=1, cursor="hand2",
                         bg=bg or PALETTE["bg"], highlightbackground=bg or PALETTE["bg"],
                         highlightcolor=PALETTE["accent"])
        self.text, self.command, self.variable = text, command, variable
        self._font, self._bg, self._hover = font_ or font("small"), bg, False
        self.progress, self._anim, self.on_running = progress, animator, on_running
        self.second = second          # (text, command): the right half, or None
        self._split = None            # where the right half starts (x), once drawn
        self.stop = stop              # (note, command): the ring stops a running tool, or None
        self._ring_end = None         # where the ring ends (x), once drawn: left of it is the stop button
        self.state = None             # what progress() said last: None (idle) or (fraction or None, note)
        self._shown = 0.0             # the fraction drawn (it eases to the real one)
        self._spin = 0                # the arc's start while it cannot tell how far
        self._blink = False           # the whole ring, a moment after the tool ended
        self._jobs = {}
        self.bind("<ButtonRelease-1>", lambda e: self.invoke(self._half(e.x)))
        for seq in ("<space>", "<Return>"):
            self.bind(seq, lambda e: self.invoke())
        self.bind("<Enter>", lambda e: self._set_hover(self._half(e.x)))
        self.bind("<Motion>", lambda e: self._hover != self._half(e.x) and self._set_hover(self._half(e.x)))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Destroy>", lambda e: e.widget is self and self._stop_all(), add="+")
        if progress is not None:
            Tooltip(self, self._note)
            self._poll()
        self._draw()

    # ---- running tools ---------------------------------------------------------------------------------
    def running(self):
        return self.state is not None

    def _note(self, e=None):
        """The hover note: how the tool is doing, or what stopping it does while the pointer is on the ring."""
        if not self.state:
            return None
        if self._hover == "stop":
            note = self.stop[0]
            return note() if callable(note) else note
        return self.state[1]

    def _still(self):
        return self._anim is not None and getattr(self._anim, "reduce_motion", False)

    def _later(self, name, ms, fn):
        try:
            self._jobs[name] = self.after(ms, fn)
        except tk.TclError:
            pass

    def _stop_all(self):
        for job in self._jobs.values():
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._jobs = {}

    def _poll(self):
        """Ask how the tool is doing; start the frames when it starts, blink once when it ends."""
        try:
            now = self.progress()
        except Exception:                 # (a tool's own state must never break the dialog)
            now = None
        was = self.state
        self.state = now
        if now is not None and was is None:
            self._shown = (now[0] or 0.0) if self._still() else 0.0
            self._blink = False
            self._frame()
        elif now is None and was is not None:
            self._blink = True
            self._draw()
            self._later("blink", self.BLINK_MS, self._end_blink)
        elif now is not None and self._still():
            self._shown = now[0] or 0.0
            self._draw()
        elif now is not None and "frame" not in self._jobs:       # (Reduce motion turned off while it runs)
            self._frame()
        self._later("poll", self.POLL_MS, self._poll)

    def _end_blink(self):
        self._blink = False
        self._draw()

    def _frame(self):
        """One frame while the tool runs: the arc turns, the ring eases towards the fraction."""
        self._jobs.pop("frame", None)
        if self.state is None:
            return
        frac = self.state[0]
        if not self._still():
            if frac is None:
                self._spin = (self._spin + self.SPIN_STEP) % 360
            else:
                self._shown += (frac - self._shown) * 0.25
                if abs(frac - self._shown) < 0.004:
                    self._shown = frac
        self._draw()
        if not self._still():
            self._later("frame", self.SPIN_MS, self._frame)

    # ---- clicks and drawing --------------------------------------------------------------------------------
    def _half(self, x):
        """Which part `x` is over: "stop" (the ring of a running tool that can be stopped), "second" (the right half
        of a split bubble) or "first"."""
        if self.stop and self.running() and self._ring_end is not None and x <= self._ring_end:
            return "stop"
        return "second" if self.second and self._split is not None and x >= self._split else "first"

    def invoke(self, half="first"):
        if half == "stop":
            if self.stop and self.running():
                self.stop[1]()
            return
        if self.second:                   # (split: each half its own command; they know a running tool)
            (self.second[1] if half == "second" else self.command)()
            return
        if self.running():                # (a running tool: its window back if it has one, else nothing)
            if self.on_running:
                self.on_running()
            return
        if self.variable is not None:
            self.variable.set(not self.variable.get())
            self._draw()
        if self.command:
            self.command()

    def lit(self):
        return self.running() or (self.variable is not None and bool(self.variable.get()))

    def _set_hover(self, on):
        self._hover = on
        self._draw()

    def _draw(self):
        self.delete("all")
        f, on = self._font, self.lit() or self._blink
        line = f.metrics("linespace")
        h = line + 6
        dot = max(4, line // 3)
        ring = (h - 6) | 1 if self.progress is not None else dot      # (odd: the dot sits in its middle)
        pad = h // 2 - (ring - dot) // 2
        w = pad + ring + dot + f.measure(self.text) + h // 2
        other = self._second_text()
        if other:
            w += h // 2 + 1 + f.measure(other) + h // 2
        super().configure(width=w + 2, height=h + 2)
        fill = PALETTE["select_bg"] if on or self._hover else PALETTE["surface"]
        edge = PALETTE["accent"] if on or self._hover else PALETTE["border"]
        self.round_rect(1, 1, w, h, h, fill=fill, outline=edge)      # (r = h: a pill in smooth.py's corners)
        y = 1 + h / 2
        cx = 1 + pad + ring / 2
        self._ring_end = 1 + pad + ring + dot / 2
        stopping = self._hover == "stop" and self.state is not None
        if stopping:                      # (the ring under the pointer: a red cross on pink, click to stop)
            self.round_rect(cx - ring / 2, y - ring / 2, cx + ring / 2, y + ring / 2, ring, fill=PALETTE["bad"][0])
            size = max(6, (ring * 9 // 16) | 1)
            self.create_image(round(cx - size / 2), round(y - size / 2), anchor="nw",
                              image=self.icon_image("stop", size, PALETTE["bad"][1]))
        else:
            self.round_rect(cx - dot / 2, y - dot / 2, cx + dot / 2, y + dot / 2, dot, fill=PALETTE["accent"])
        if self.state is not None or self._blink:
            thick = max(2, round(ring / 8))
            x0, y0 = round(cx - ring / 2), round(y - ring / 2)
            if not stopping:
                self.create_image(x0, y0, anchor="nw", image=self.ring_image(ring, thick, 0, 360, PALETTE["surface"]))
            frac = None if self.state is None else self.state[0]
            if self._blink:
                start, extent = 0, 360
            elif frac is None:
                start, extent = self._spin, self.SPIN_ARC
            else:
                start, extent = 0, int(round(self._shown * 120)) * 3          # (3 degree steps: a few images)
            if extent > 0:
                self.create_image(x0, y0, anchor="nw", image=self.ring_image(
                    ring, thick, start, min(360, extent), PALETTE["bad"][1] if stopping else PALETTE["ring"]))
        def ink(half):
            hover = self._hover == half if other else self._hover not in (False, "stop")
            return PALETTE["text"] if (on and not other) or hover else PALETTE["muted"]
        x = 1 + pad + ring + dot
        self.create_text(x, y, text=self.text, font=f, anchor="w", fill=ink("first"))
        if other:
            x += f.measure(self.text) + h // 2
            self.create_line(x, 1 + h * 0.25, x, 1 + h * 0.75, fill=edge)
            self._split = x
            self.create_text(x + 1 + h // 2, y, text=other, font=f, anchor="w", fill=ink("second"))

    def _second_text(self):
        """The right half's words: its own, or what progress() says while running ("Tuning · step 1 of 2")."""
        if not self.second:
            return None
        return self.state[2] if self.state is not None and len(self.state) > 2 and self.state[2] else self.second[0]

    def refresh(self):
        self._draw()
