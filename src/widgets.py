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
    * `hint_font`: a Font for the caption (default: 72% of the label font, which is too big on big cards).
    * `flat=True` is a quiet text button: no fill or outline until hovered (UI-8). `ring` is the
      width of the accent outline on hover (2; the duel cards use 3).
    """

    def __init__(self, parent, text, command, bg=PALETTE["neutral"], fg=PALETTE["text"], font=None,
                 padx=14, pady=8, hint=None, wraplength=0, radius=14, animator=None, canvas_bg=None, lift=0,
                 flat=False, ring=2, hint_font=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["bg"],
                         cursor="hand2", takefocus=0)
        self._command = command
        self._text, self._hint, self._wrap = text, hint, wraplength
        self._fill, self._fg = bg, fg
        self._padx, self._pady, self._radius = padx, pady, radius
        self._lift, self._lifted = lift, False
        self._flat, self._ring = flat, ring
        self._selected = False
        self._anim = animator
        self._font = font if isinstance(font, tkfont.Font) else tkfont.Font(root=self, font=font or "TkDefaultFont")
        self._own_hint_font = hint_font is None          # else a shared font: never resize it here
        self._hint_font = hint_font if hint_font is not None else tkfont.Font(root=self, font=self._font)
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
        fill, fg = self._fill, self._fg
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
            return (lerp_color(fill, "#FFFFFF", 0.45), PALETTE["accent"], self._ring, fg)
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


class DuelCards(tk.Frame):
    """The duel view's controls (UI-8): two big word cards side by side, each with a hover ring and its
    key hint, and quiet Tie / Skip text buttons under them.

        duel = DuelCards(parent, on_answer, font("pair"), font("body"), animator=app.anim)
        duel.show("apple", "pear")
        duel.press("left")   # what the Left key does: on_answer("left") runs, then the card dips

    on_answer(side) gets "left", "right", "tie" or "skip", from a click or from press(). `left`, `right`,
    `tie` and `skip` are the RoundButtons (App.left_btn and friends).
    """
    SIDES = ("left", "right", "tie", "skip")

    def __init__(self, parent, on_answer, card_font=None, small_font=None, animator=None):
        super().__init__(parent, bg=PALETTE["bg"])
        self._on_answer = on_answer
        self.columnconfigure((0, 1), uniform="duel")
        self.left = RoundButton(self, "", lambda: on_answer("left"), bg=PALETTE["left"], font=card_font,
                                padx=40, pady=40, radius=24, hint="\u2190  A", animator=animator, ring=3,
                                hint_font=small_font)
        self.left.grid(row=0, column=0, padx=12, sticky="nsew")
        self.right = RoundButton(self, "", lambda: on_answer("right"), bg=PALETTE["right"], font=card_font,
                                 padx=40, pady=40, radius=24, hint="L  \u2192", animator=animator, ring=3,
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

    def show(self, left, right):
        """Show a new pair (and enable everything)."""
        self.left.config(text=left)
        self.right.config(text=right)
        self.set_enabled(True)

    def set_enabled(self, enabled):
        for b in self.buttons.values():
            b.set_enabled(enabled)

    def press(self, side):
        """The keyboard version of a click: on_answer(side) runs first, then that button dips."""
        b = self.buttons.get(side)
        if b is None or not b.enabled:
            return
        self._on_answer(side)
        try:
            b.flash()
        except tk.TclError:
            pass


class AnchorLadder(tk.Canvas):
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
            self.create_polygon(_rounded_points(x, 3, x + w, 3 + h, h // 2), smooth=True,
                                tags=("pill", f"pill{i}"), width=1)
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


class TabBar(tk.Canvas):
    """Folder-style tabs over a page (UI-10): a hairline runs the full width under the tabs, and the
    chosen tab is drawn in the page colour with its sides and rounded top outlined, open at the bottom,
    so it looks joined to the page below.

        tabs = TabBar(parent, [("place", "Place new words"), ...], on_change, font("label"),
                      animator=app.anim, page_bg=PALETTE["bg"])
        tabs.pack(fill="x")
        tabs.set("refine")        # move to a tab without calling on_change (e.g. after a key)

    A click on another tab slides the open tab there (SLIDE_MS, ease-out; jumps with Reduce motion) and
    calls on_change(key). Tabs are all as wide as the widest label and sit centred.
    """
    SLIDE_MS = 180

    def __init__(self, parent, options, on_change, font=None, animator=None, canvas_bg=None, page_bg=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["surface"], takefocus=0)
        self.options = list(options)
        self._keys = [k for k, _ in self.options]
        self._on_change, self._font, self._anim = on_change, font, animator
        self._page = page_bg or PALETTE["bg"]
        self.value = self._keys[0]
        self._x = 0.0                        # position of the open tab, in tabs (animated)
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
        return tab_w, h, (width - n * tab_w) / 2, width       # tab width, height, left edge of the tabs, width

    def _draw(self):
        self.delete("all")
        tab_w, h, x0, width = self._metrics()
        super().configure(height=h + 1, cursor="hand2")
        n = len(self.options)
        super().configure(width=n * tab_w + 20)
        self.create_polygon(0, 0, 0, 0, fill=PALETTE["surface2"], outline="", tags="hoverfill")
        self.create_polygon(0, 0, 0, 0, fill=self._page, outline="", tags="tabfill")
        self.create_line(0, 0, 0, 0, fill=PALETTE["border"], smooth=True, tags="tabedge")
        self.create_line(0, 0, 0, 0, fill=PALETTE["border"], tags="baseline_left")
        self.create_line(0, 0, 0, 0, fill=PALETTE["border"], tags="baseline_right")
        for i, (key, label) in enumerate(self.options):
            self.create_text(x0 + tab_w * i + tab_w / 2, 2 + h / 2, text=label, font=self._font,
                             tags=("label", f"label_{key}"))
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
        x2 = x1 + tab_w - 4
        shape = self._tab_shape(x1, x2, top, base + 1, r)
        self.coords("tabfill", *shape)
        self.coords("tabedge", *shape[2:-2])       # sides and top only: open at the bottom
        self.coords("baseline_left", 0, base, x1, base)
        self.coords("baseline_right", x2, base, width, base)
        hov = self._hover if self._hover != self.value else None
        if hov is not None:
            i = self._keys.index(hov)
            hx1 = x0 + i * tab_w + 6
            self.coords("hoverfill", *self._tab_shape(hx1, hx1 + tab_w - 12, top + 4, base - 1, r))
            self.itemconfigure("hoverfill", state="normal")
        else:
            self.itemconfigure("hoverfill", state="hidden")
        for key in self._keys:
            on = key == self.value or key == self._hover
            self.itemconfigure(f"label_{key}", fill=PALETTE["text"] if on else PALETTE["muted"])
        self.tag_raise("label")

    def _index_at(self, x):
        tab_w, _h, x0, _w = self._metrics()
        i = int((x - x0) // tab_w) if x >= x0 else -1
        return self._keys[i] if 0 <= i < len(self._keys) else None

    def tab_x(self, key):
        """Centre x of a tab, in canvas pixels (for tests)."""
        tab_w, _h, x0, _w = self._metrics()
        return x0 + self._keys.index(key) * tab_w + tab_w / 2

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
        start, goal = self._x, float(self._keys.index(key))

        def frame(p):
            self._x = start + (goal - start) * p
            self._place_tab()
        if self._anim is None:
            frame(1.0)
        else:
            self._anim.run(f"tabs{id(self)}", self.SLIDE_MS, frame)

    def get(self):
        return self.value

    def refresh(self):
        self._draw()


class DropMenu:
    """A styled drop-down menu (UI-10): a borderless window with roomy rows, the pastel highlight, check
    marks and shortcut hints, used by the header's File / Edit / View / Settings buttons.

        items = [("command", "Export tier list...", app.export, None),
                 ("check", "Reduce motion", app.motion_var, app.toggle_motion),
                 ("separator",),
                 ("command", "Undo", app.undo, "Ctrl+Z")]
        DropMenu(root, items, font("body")).open(x, y, on_close)

    Mouse: hover highlights, click runs the item and closes. Keys: Up / Down move, Return runs, Escape
    closes. It also closes when the main window is clicked elsewhere, moved, or loses focus.
    """

    def __init__(self, root, items, font=None):
        self.root, self.items, self.font = root, list(items), font
        self.win = None
        self._rows, self._active, self._on_close = [], None, None

    @staticmethod
    def labels(items):
        """The labels of the clickable items (for tests and docs)."""
        return [it[1] for it in items if it[0] in ("command", "check")]

    def is_open(self):
        return self.win is not None

    def open(self, x, y, on_close=None):
        """Show the menu with its top-left corner at screen position (x, y)."""
        self.close()
        self._on_close = on_close
        win = self.win = tk.Toplevel(self.root, bg=PALETTE["border"])
        win.withdraw()
        win.overrideredirect(True)
        try:
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
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
        win.bind("<FocusOut>", self._on_focus_out)
        win.update_idletasks()
        # keep it on screen
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        x = max(0, min(x, win.winfo_screenwidth() - w))
        y = max(0, min(y, win.winfo_screenheight() - h))
        win.geometry(f"+{x}+{y}")
        win.deiconify()
        win.lift()
        try:
            win.focus_force()
        except tk.TclError:
            pass

    def _on_focus_out(self, _e):
        # only when focus left the menu for good (not moving between its own rows)
        self.root.after(50, lambda: self.win is not None and self.win.focus_get() is None and self.close())

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
        else:
            it[2]()

    def close(self):
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None
            self._rows, self._active = [], None
            cb, self._on_close = self._on_close, None
            if cb:
                cb()


class HeaderMenus(tk.Frame):
    """The row of header menu buttons (File, Edit, View, Settings) with their DropMenus (UI-10).

        HeaderMenus(parent, [("File", items), ("Edit", items), ...], font("body"), animator=app.anim)

    Clicking a button opens its menu under it (clicking again closes it); while one menu is open,
    hovering another button switches to that menu, like a desktop menu bar. open_menu(name) opens one
    from the keyboard (Alt+F and friends, F10).
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

    def _hover_switch(self, name):
        if self._open is not None and self._open != name:
            self.open_menu(name)

    def close(self):
        if self._open is not None:
            self.drops[self._open].close()


class Toast(tk.Canvas):
    """A small rounded message that fades in over the page, stays a moment, and fades out (UI-11).

        toast = Toast(root, font("label"), animator=app.anim)
        toast.show("serendipity  ->  S", tint=("#FFB3C1", "#3D3A4B"), ms=1500, in_=app.center)

    It floats (place), so showing it never moves anything else. A new message replaces the current one.
    fling() is the placement version: the message rises out of the word, rests while it pales a little,
    then swipes sideways (toward its tier) and fades out completely.
    "Fades" are colour blends from the page colour (FADE_IN_MS / FADE_OUT_MS; they jump with Reduce
    motion). cget("text") is the message on screen ("" once it is gone); cget("font") its Font.
    """
    FADE_IN_MS, FADE_OUT_MS = 160, 220
    RISE_MS, SETTLE_MS, SWIPE_MS = 200, 250, 240      # fling(): rise out of the word, settle, swipe away

    def __init__(self, parent, font=None, animator=None, page_bg=None):
        page = page_bg or PALETTE["bg"]
        super().__init__(parent, bd=0, highlightthickness=0, bg=page)
        self._font, self._anim, self._page = font, animator, page
        self._home = page              # the page colour (fling may borrow another backdrop for a moment)
        self._text, self._tint = "", (PALETTE["info"][0], PALETTE["info"][1])
        self._job = None
        self._wrap = 600
        self._gen = 0                  # bumped by every show / fling, so stale stages of an old one stop
        self._in = None

    def cget(self, key):
        if key == "text":
            return self._text
        if key == "font":
            return self._font
        return super().cget(key)

    def show(self, text, tint=None, ms=3500, in_=None, wraplength=None):
        """Show `text` on a pill coloured `tint` = (background, text colour) for `ms` milliseconds."""
        self._reset()
        self._text = text
        self._tint = tint or self._tint
        if wraplength:
            self._wrap = wraplength
        self._draw()
        self._in = in_ or self.master
        self._put(0, 6)
        self._fade(0.0, 1.0, self.FADE_IN_MS)
        self._job = self.after(ms, self.hide)

    def fling(self, text, tint, start_mid, rest_bottom, dx, hold_ms=550, in_=None, wraplength=None, under=None):
        """The placement message: rise from its centre at y=start_mid (the word) until its bottom edge is at
        y=rest_bottom, fading in; rest for hold_ms while paling slightly; then slide dx pixels sideways
        (negative = left) while fading out completely. y values are inside `in_`. Every stage is <= 250 ms and a new
        message (or Animator.finish_all from a key press) cuts it short; with Reduce motion it stays put.
        `under(y_mid)` returns the colour behind the toast at that height (tk has no transparency, so the
        toast takes that colour as its own background and blends toward it)."""
        self._reset()
        gen = self._gen
        self._text, self._tint = text, tint
        if wraplength:
            self._wrap = wraplength
        self._draw()
        self._in = in_ or self.master
        key = f"toast{id(self)}"
        alive = lambda: gen == self._gen

        h = int(self.cget("height"))
        from_y, to_y = start_mid - h / 2, rest_bottom - h

        def backdrop(y):
            if under is not None:
                c = under(y + h / 2)
                if c != self._page:
                    self._page = c
                    super(Toast, self).configure(bg=c)

        def rise(p):
            if alive():
                y = from_y + (to_y - from_y) * p
                backdrop(y)
                self._put(0, y)
                self._paint(p)

        def settle(p):
            if alive():
                self._paint(1.0 - 0.3 * p)

        def swipe(p):
            if alive():
                self._put(dx * p, to_y)
                self._paint(0.7 * (1.0 - p))

        def gone():
            if alive():
                self._text = ""
                self.place_forget()
                self._page = self._home
                super(Toast, self).configure(bg=self._home)

        def after_rise():
            if alive():
                self._job = self.after(hold_ms, lambda: alive() and self._anim_run(key, self.SWIPE_MS, swipe, gone))
                self._anim_run(key, self.SETTLE_MS, settle)
        self._anim_run(key, self.RISE_MS, rise, after_rise)

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
        if self._page != self._home:
            self._page = self._home
            super().configure(bg=self._home)
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        if self._anim is not None:
            self._anim.finish(f"toast{id(self)}")

    def _put(self, x, y):
        self.place(in_=self._in, relx=0.5, x=int(x), y=int(y), anchor="n")
        self.tk.call("raise", self._w)          # (Canvas.lift raises canvas items, not the widget)

    def hide(self):
        """Fade out now (also what happens when the time is up)."""
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        if not self._text:
            return

        def gone():
            self._text = ""
            self.place_forget()
        self._fade(1.0, 0.0, self.FADE_OUT_MS, gone)

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
        super().configure(width=w + 2, height=h + 2)
        self.create_polygon(_rounded_points(1, 1, w, h, min(h // 2, line)), smooth=True, tags="pill")
        self.coords(t, 1 + w / 2, 1 + pady)
        self.tag_raise("text")

    def _paint(self, a):
        bg, fg = self._tint
        try:
            self.itemconfigure("pill", fill=lerp_color(self._page, bg, a),
                               outline=lerp_color(self._page, lerp_color(bg, PALETTE["text"], 0.12), a))
            self.itemconfigure("text", fill=lerp_color(self._page, fg, a))
        except tk.TclError:
            pass

    def _fade(self, a, b, ms, done=None):
        if self._anim is None:
            self._paint(b)
            if done:
                done()
            return
        self._anim.run(f"toast{id(self)}", ms, lambda p: self._paint(a + (b - a) * p), done)


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
        self._italic = tkfont.Font(root=self, font=body)
        self._italic.configure(slant="italic")
        self._body = body
        inner = tk.Frame(self, bg=PALETTE["surface"], highlightthickness=1, highlightbackground=PALETTE["border"])
        inner.pack(fill="x", anchor="n")
        self.text = tk.Text(inner, height=9, wrap="word", state="disabled", font=body, bd=0, highlightthickness=0,
                            padx=14, pady=10, bg=PALETTE["surface"], cursor="arrow")
        self.text.pack(fill="x")
        t = self.text
        t.tag_configure("head", font=head, spacing1=2, spacing3=4)
        t.tag_configure("num", foreground=PALETTE["muted"])
        t.tag_configure("pos", font=self._italic, foreground=PALETTE["muted"])
        t.tag_configure("sense", lmargin1=6, lmargin2=26, spacing1=2)
        t.tag_configure("ex", font=self._italic, foreground=PALETTE["muted"], lmargin1=26, lmargin2=26)
        t.tag_configure("wait", foreground=PALETTE["muted"])
        self._shown = False

    def refresh_fonts(self):
        """Follow the body font after it was resized (the italic copy is this widget's own)."""
        self._italic.configure(size=self._body.cget("size"), family=self._body.cget("family"))

    def show_words(self, words, get_def):
        """Fill the pane: for each word, its name and its senses (get_def(word) -> text, or None while
        it is still being looked up)."""
        from definitions import parse_definition
        t = self.text
        t.config(state="normal")
        t.delete("1.0", "end")
        for i, w in enumerate(words):
            if i:
                t.insert("end", "\n")
            t.insert("end", w + "\n", "head")
            text = get_def(w)
            if text is None:
                t.insert("end", "Looking up definition...\n", "wait")
                continue
            for sense in parse_definition(text):
                if sense["num"]:
                    t.insert("end", sense["num"] + ".  ", ("num", "sense"))
                if sense["pos"]:
                    t.insert("end", sense["pos"] + "  ", ("pos", "sense"))
                t.insert("end", sense["text"] + "\n", "sense")
                if sense["example"]:
                    t.insert("end", "\u201c" + sense["example"] + "\u201d\n", "ex")
        t.config(state="disabled")

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
            super().configure(height=0)
            self.pack_propagate(True)
        except tk.TclError:
            pass

    def open(self):
        """Ease open from nothing to the height the contents want (the caller has packed it already)."""
        self._shown = True
        self.update_idletasks()
        goal = self.winfo_reqheight()
        self._slide(0, goal, self._natural)

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


class Tooltip:
    """A small hover note (UI-13 / UI-15): appears after DELAY_MS of hovering, follows the pointer, and goes
    when the pointer leaves or a key or button is pressed.

        Tooltip(widget, lambda e: "1,234 words")    # text_fn(event) -> text, or None for "nothing here"

    text_fn gets the Motion event, so one tooltip can say different things over different parts of a
    canvas (each bar of the chart). It is a borderless window in the surface colour with a hairline.
    """
    DELAY_MS = 350

    def __init__(self, widget, text_fn, font=None):
        self.widget, self.text_fn, self.font = widget, text_fn, font
        self.win = self._label = None
        self._job = None
        self._last = None
        widget.bind("<Motion>", self._on_motion, add="+")
        widget.bind("<Leave>", lambda e: self.hide(), add="+")
        widget.bind("<ButtonPress>", lambda e: self.hide(), add="+")

    @property
    def text(self):
        """What is showing now ("" when hidden)."""
        return self._label.cget("text") if self.win is not None else ""

    def _on_motion(self, e):
        self._last = e
        text = self.text_fn(e)
        if not text:
            self.hide()
            return
        if self.win is not None:
            self._label.configure(text=text)
            self._place(e)
            return
        if self._job is None:
            self._job = self.widget.after(self.DELAY_MS, self._show)

    def _show(self):
        self._job = None
        e = self._last
        text = self.text_fn(e) if e is not None else None
        if not text:
            return
        win = self.win = tk.Toplevel(self.widget, bg=PALETTE["border"])
        win.overrideredirect(True)
        try:
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
        self._label = tk.Label(win, text=text, bg=PALETTE["surface"], fg=PALETTE["text"], font=self.font,
                               padx=8, pady=4, justify="left")
        self._label.pack(padx=1, pady=1)
        self._place(e)

    def show_at(self, e):
        """Show now for this event (tests, and keyboard focus later)."""
        self._last = e
        self._show()

    def _place(self, e):
        x = self.widget.winfo_rootx() + e.x + 14
        y = self.widget.winfo_rooty() + e.y + 18
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
            self.win = self._label = None


def refresh_widgets(widget):
    """Re-measure every canvas widget of ours (RoundButton, WordCard, AnchorLadder, TabBar, the chart...) under
    `widget` after shared fonts were resized."""
    for child in widget.winfo_children():
        if isinstance(child, tk.Canvas) and callable(getattr(child, "refresh", None)):
            child.refresh()                  # our canvas widgets (here and in ui_chart.py) all have refresh()
        else:
            refresh_widgets(child)
