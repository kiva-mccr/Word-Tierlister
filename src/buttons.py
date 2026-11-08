"""The program's buttons, drawn on canvases with smoothed rounded corners (Canvas, not tk.Button or ttk, so the colours
look the same on macOS, Windows and Linux): RoundButton (UI-5) and the tier pills (TierRow, TierChip), the small icon
link (LinkButton) and the developer tools' bubbles (DevBubble). EDGE is a button's or pill's edge: its fill this far toward the ink.
"""
import tkinter as tk
import tkinter.font as tkfont

from fonts import font
from smooth import SmoothCanvas
from theme import PALETTE, TIER_COLORS, TIER_TEXT, ink_on, is_light
from ui_motion import lerp_color
from popups import Tooltip
from smears import Unsmear


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


class DevBubble(SmoothCanvas):
    """A small lilac pill with a dot and a few words: a developer tool in a dialog's top right corner (asked for:
    dev tools reachable from the window, not only by command; only while Settings > Developer tools is ticked).
    A click (or Space / Return once it has focus) runs `command`. With `variable` it is a switch, lit while True.

        DevBubble(parent, "Log", app.devtools.open_log)
        DevBubble(parent, "Nightly", toggle, variable=shown)
    """

    def __init__(self, parent, text, command, variable=None, font_=None, bg=None):
        super().__init__(parent, bd=0, highlightthickness=1, takefocus=1, cursor="hand2",
                         bg=bg or PALETTE["bg"], highlightbackground=bg or PALETTE["bg"],
                         highlightcolor=PALETTE["accent"])
        self.text, self.command, self.variable = text, command, variable
        self._font, self._hover = font_ or font("small"), False
        self.bind("<ButtonRelease-1>", lambda e: self.invoke())
        for seq in ("<space>", "<Return>"):
            self.bind(seq, lambda e: self.invoke())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self._draw()

    def invoke(self):
        if self.variable is not None:
            self.variable.set(not self.variable.get())
            self._draw()
        if self.command:
            self.command()

    def lit(self):
        return self.variable is not None and bool(self.variable.get())

    def _set_hover(self, on):
        self._hover = on
        self._draw()

    def _draw(self):
        self.delete("all")
        f, on = self._font, self.lit()
        line = f.metrics("linespace")
        h = line + 6
        dot = max(4, line // 3)
        pad = h // 2
        w = pad + dot + dot + f.measure(self.text) + h // 2
        super().configure(width=w + 2, height=h + 2)
        fill = PALETTE["select_bg"] if on or self._hover else PALETTE["surface"]
        edge = PALETTE["accent"] if on or self._hover else PALETTE["border"]
        self.round_rect(1, 1, w, h, h, fill=fill, outline=edge)      # (r = h: a pill in smooth.py's corners)
        y = 1 + h / 2
        cx = 1 + pad + dot / 2
        self.round_rect(cx - dot / 2, y - dot / 2, cx + dot / 2, y + dot / 2, dot, fill=PALETTE["accent"])
        self.create_text(1 + pad + dot + dot, y, text=self.text, font=f, anchor="w",
                         fill=PALETTE["text"] if on or self._hover else PALETTE["muted"])

    def refresh(self):
        self._draw()
