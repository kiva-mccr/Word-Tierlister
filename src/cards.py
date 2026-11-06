"""The drawn panels of the main page and its dialogs: the word card (WordCard: a fixed size, each word fitted in its
own font copy), the duel's two cards (DuelCards), the anchor strip (AnchorLadder), the "nothing to do here" card
(EmptyCard), the queue dialog's shape cards (ShapeCard) and the file picker's list (FileList).
"""
import math
import tkinter as tk

from constants import QUEUE_AXIS, QUEUE_MEDIAN, queue_weight
from fonts import font
from smooth import ICONS, SmoothCanvas, curve_image
from theme import PALETTE, TIER_COLORS
from ui_motion import lerp_color
from buttons import RoundButton
from smears import Unsmear, smear_items


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
        self._anim = animator
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

    FADE_MS, FADE_OUT = 240, 0.4             # show(fade=True): the whole fade, and the share of it spent fading out

    def show(self, left, right, colors=None, censor=(False, False), fade=False, then=None):
        """Show a new pair (and enable everything). `colors` = (left fill, right fill), e.g. each word's tier
        colour; without it the cards keep their own pastel blue / peach. `censor`: each word smeared until
        hovered (ST-6). `fade`: the old pair fades into the page and the new one fades in (switching between the
        duel tabs; asked for: the cards changed words, colours and widths in one blink). It runs under anim_key,
        so a key press or the next result finishes it first. `then()` runs once the new words are on the cards."""
        left_bg, right_bg = colors or (PALETTE["left"], PALETTE["right"])

        def put():
            self.left.config(text=left, bg=left_bg, censor=censor[0])
            self.right.config(text=right, bg=right_bg, censor=censor[1])
            self.set_enabled(True)
            if then:
                then()
        if not fade or self._anim is None:
            put()
            return
        cards, swapped = (self.left, self.right), []

        def frame(p):
            if p < self.FADE_OUT:
                amount = p / self.FADE_OUT
            else:
                if not swapped:                  # (out of sight: the new words, colours and widths)
                    swapped.append(True)
                    put()
                amount = 1.0 - (p - self.FADE_OUT) / (1.0 - self.FADE_OUT)
            for c in cards:
                c.veil(amount, PALETTE["bg"])
        self._anim.run(self.anim_key, self.FADE_MS, frame)

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


class ShapeCard(SmoothCanvas):
    """One of the queue dialog's two shape choices (UI-41): a little card with the shape's soft pastel curve
    (how likely a word is to come up early, from rank #1 to QUEUE_AXIS), its name under it, and for the
    chosen card a dotted line at the rank above which half the early words come from. The chosen card is
    white with a lilac hairline and a filled curve; the other is faint. A click calls on_pick(shape).

        card = ShapeCard(parent, "exp", "Exponential", TIER_COLORS[1], on_pick=choose)
        card.set(spread=20000, chosen=True)       # redraw (live, as the spread is typed)
    """
    def __init__(self, parent, shape, name, color, on_pick, font_=None, canvas_bg=None, spread=None, chosen=False):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["bg"], cursor="hand2")
        self.shape, self.name, self.color = shape, name, color
        self._font = font_ or font("body")
        self.spread, self.chosen = max(1.0, float(spread or 20000.0)), bool(chosen)
        self.bind("<Button-1>", lambda e: on_pick(shape))
        self._draw()

    def set(self, spread=None, chosen=None):
        """Redraw for a new spread or choice; nothing to do when neither changed (the curve is costly to draw)."""
        was = (self.spread, self.chosen)
        if spread is not None:
            self.spread = max(1.0, float(spread))
        if chosen is not None:
            self.chosen = bool(chosen)
        if (self.spread, self.chosen) != was:
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

        card = WordCard(parent, font("word"), font("small"))
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
        self._blink_job = None
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
            wrap = kw.pop("wraplength")
            if wrap != self._wrap:            # (a re-fit sets it every time: only a new width redraws)
                self._wrap = wrap
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
            moved = round(wy + back) - round(self.coords("word")[1]) if self.coords("word") else 0
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
            if self._censor and moved:            # (the smear rises with its word: moved, not drawn again, F-36)
                self.move(self.smear.tag, 0, moved)

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
                self._blink(0)

    BLINK_MS, BLINK_FOR_MS = 530, 10000   # the caret blinks as in most programs (UI-70), shown on every key, and
                                          # stays shown after 10 s without one (GTK's way: nothing runs for good)

    def _blink(self, since):
        """Show the caret (`since` = 0: a key, or a redraw) or hide it, every BLINK_MS while typing."""
        if self._blink_job:
            self.after_cancel(self._blink_job)
            self._blink_job = None
        if not self.typing:
            return
        on = since % (2 * self.BLINK_MS) < self.BLINK_MS or since >= self.BLINK_FOR_MS
        try:
            self.itemconfigure("caret", state="normal" if on else "hidden")
        except tk.TclError:
            return
        if since < self.BLINK_FOR_MS:
            self._blink_job = self.after(self.BLINK_MS, lambda: self._blink(since + self.BLINK_MS))

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
        self._blink(0)                    # (stops it)
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
