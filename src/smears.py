"""Censored (obscene) words drawn smeared: copies of the word side by side, pale, so it cannot be read (ST-6, F-33).

smear_items smears a text item on one of our canvases; Unsmear eases it back to the word under the pointer (and smears
it again as it leaves). smeared_label is a small canvas for places that are not our canvases (the definition panes),
TreeSmears does Browse's list. The look is the user's (F-33, F-38, F-39, F-43): SMEAR_SPREAD letter widths, each
line's end letters smeared only inward, round letters twice as far. Buttons holding a smeared word are in buttons.py.
"""
import re
import tkinter as tk

from fonts import letter_holes, text_overhang
from theme import PALETTE
from ui_motion import lerp_color


UNSMEAR_MS = 260        # a censored word un-smears this fast under the pointer (ST-6), and smears again as fast
SMEAR_SPREAD = 0.625    # how far a censored word is smeared sideways, in letter widths (the user's pick)
SMEAR_TONE = 0.55       # how pale the smear is (0 = the text colour, 1 = the card)
SMEAR_BODY = 0.48       # the band filling the gaps between the letters, in em up from the baseline (about the
                        # x-height of the roundest fonts used; a more generous one would show a flat top)
SHORT_LETTERS = frozenset("acemnorsuvwxz")   # no ascender, descender or dot: smeared twice as far as the others
SHORT_SPREAD = 2.0                            # (F-38, the user's idea), filling the gaps between round letters
END_SPREAD = 2.0        # a line's first and last letters smear inward this many times as far (F-43, asked for: their
                        # counters, a d's or an o's, still showed at the word's ends)
FILL_FADE = 0.1         # the band and the holes' fill are gone this far into un-smearing (F-40: at its very start)
_TEXT_OPTS = ("text", "font", "anchor", "justify", "width")


def smear_items(canvas, item, ink, paper, amount=1.0, tags=()):
    """Smear the text `item` sideways (ST-6): copies of it side by side over SMEAR_SPREAD letter widths, in one
    pale tone (so none of them stays crisp on top). The smear never reaches past the word (F-33, the user's rules):
    the first and last letter of each line smear only inward and the letters between them both ways; so nothing is
    cut off, by a strip or by the edge of a canvas only as wide as the word. A band in the same tone fills the gaps
    behind them (else the space inside an "e" and between the curves of "ss" or "uc" shows as white slivers), from
    the end of the first letter to the start of the last, hidden in the word (asked for: reaching the ends, its flat
    edges showed as a bar under the smear, F-37). On one line the short letters (SHORT_LETTERS: no ascender,
    descender or dot) smear SHORT_SPREAD times as far, behind the rest, which fills most such gaps on their own
    (F-38, the user's idea). `amount` (0..1) narrows it and darkens it toward `ink`
    (un-smearing; the band fades out). Tk cannot blur, so the copies are plain canvas text, redrawn
    every frame from a layout worked out once (_smear_layout). Returns nothing; the items carry `tags`."""
    c = canvas
    box = c.bbox(item)
    if not box:
        return
    lay = _smear_layout(c, item, box)
    half = lay["n"] * SMEAR_SPREAD / 2 * amount
    col = lerp_color(ink, paper, SMEAR_TONE * amount)
    # the band between the end letters (F-37) and a fill inside every letter's holes (F-40, asked for: no counter shows
    # white), both gone at the very start of un-smearing (else a pale box shows behind the letters closing in); not
    # on a word wrapped over two lines
    fill = max(0.0, (amount - (1 - FILL_FADE)) / FILL_FADE)
    if fill > 0:
        tone = lerp_color(paper, col, fill)
        if lay["band"]:
            c.create_rectangle(*lay["band"], outline="", fill=tone, tags=tags)
        for shape in lay["holes"]:
            c.create_polygon(*shape, outline="", fill=tone, tags=tags)
    # a copy every `gap` whole pixels (Tk draws text at whole pixels: copies landing on the same one stack up and look
    # bold on small text, reported in the definitions pane; on small text wider gaps show as combs, while big text's
    # thick strokes hide them, and half the copies is half the drawing each frame: F-36); near the end the side copies
    # fade into the paper and the middle one, drawn last, becomes the word itself, so the last frames end where the
    # plain word starts
    gap = lay["gap"]
    steps = max(4, int(2 * half / gap))
    offsets = sorted({round(-half + 2 * half * k / steps) for k in range(steps + 1)} - {0}, key=abs, reverse=True)
    side = lerp_color(paper, col, min(1.0, max(0.0, (half - 0.5) / 1.5)))   # (faded out by half a pixel apart)
    make = tk.Canvas.create_text                # (plain items: the guard below repaints their reach, once: F-36)
    fnt = lay["font"]
    # (F-38) the short letters' runs (third letter on, from either end) reach further, behind the rest: never onto the
    # end letters
    far = half * SHORT_SPREAD
    if far - half >= gap:
        more = sorted({round(half + (far - half) * k / max(1, int((far - half) / gap))) for k in
                       range(1, max(1, int((far - half) / gap)) + 1)}, reverse=True)
        for dist in more:
            for run, rx, y, left_room, right_room in lay["short"]:
                if dist <= right_room:            # (never over the end letters: F-33)
                    make(c, rx + dist, y, text=run, font=fnt, anchor="nw", fill=side, tags=tags)
                if dist <= left_room:
                    make(c, rx - dist, y, text=run, font=fnt, anchor="nw", fill=side, tags=tags)
    # (F-43) the end letters reach further inward, behind the rest, never past the word's other end
    far = half * END_SPREAD
    if far - half >= gap:
        steps = max(1, int((far - half) / gap))
        for dist in sorted({round(half + (far - half) * k / steps) for k in range(1, steps + 1)}, reverse=True):
            for first, fx, last, lx, y, room in lay["ends"]:
                if dist <= room:
                    make(c, fx + dist, y, text=first, font=fnt, anchor="nw", fill=side, tags=tags)
                    make(c, lx - dist, y, text=last, font=fnt, anchor="nw", fill=side, tags=tags)
    # (F-33, the user's rules) the end letters move only inward; the letters next to them outward only as far as the
    # space between letters (`near`), never over the end letter; the rest both ways. A copy moved right is the line
    # less its last letter (or, past `near`, less its last two), one moved left less its first (or first two): still
    # one item a copy
    near = lay["near"]
    for dx in offsets:
        for line, x, y, right1, right2, left1_x, left1, left2_x, left2 in lay["lines"]:
            if dx > 0:
                piece, px = (right1, x) if dx <= near else (right2, x)
            else:
                piece, px = (left1, left1_x) if -dx <= near else (left2, left2_x)
            if piece:
                make(c, px + dx, y, text=piece, font=fnt, anchor="nw", fill=side, tags=tags)
    for line, x, y, *_pieces in lay["lines"]:
        make(c, x, y, text=line, font=fnt, anchor="nw", fill=col, tags=tags)
    # an invisible shape over everything the smear can reach: drawn with it, so deleting it with the smear's next frame
    # makes Tk repaint all of it (letters reaching past their boxes, F-32), without a guard for every copy
    g = lay["reach"]
    tk.Canvas.create_rectangle(c, g[0] - half - 2, g[1], g[2] + half + 2, g[3], outline="", fill="", tags=tags)


def _smear_layout(c, item, box):
    """What a smear of text `item` needs that stays the same from frame to frame (kept per canvas for the text, its
    font and its box, so an un-smearing redraws without measuring again: F-36): its lines, each without its last
    letter and without its first (F-33), the band between its end letters (F-37), its runs of short letters with
    which way each may move (F-38), the font's "n" width, the copies' gap and the smear's whole reach."""
    opts = {k: c.itemcget(item, k) for k in _TEXT_OPTS}
    fnt = opts["font"]
    key = (item, tuple(opts.values()), tuple(box), tuple(c.coords(item)[:2]))
    cache = c.__dict__.setdefault("_smear_cache", {})
    if key in cache:
        return cache[key]
    size = float(c.tk.call("font", "actual", fnt, "-size"))
    em = -size if size < 0 else size * float(c.tk.call("tk", "scaling"))
    linespace = float(c.tk.call("font", "metrics", fnt, "-linespace"))
    lines = _smear_lines(c, item, opts, box, linespace)
    rows = []        # (line, x, y, it less its last letter, less its last two, where and less its first, its first two)
    for text, x, y in lines:
        if not text.strip():
            continue
        if len(text) < 2:                       # (one letter: it smears both ways)
            rows.append((text, x, y, text, text, x, text, x, text))
            continue
        w1 = x + _measure(c, fnt, text[0])
        if len(text) == 2:                      # (two letters: each is an end, and moves only inward)
            rows.append((text, x, y, text[0], text[0], w1, text[1], w1, text[1]))
            continue
        rows.append((text, x, y, text[:-1], text[:-2], w1, text[1:], x + _measure(c, fnt, text[:2]), text[2:]))
    ends = []                        # (first letter, its x, last letter, its x, y, how far each may move inward)
    for text, x, y in lines:
        if len(text.strip()) >= 2:
            whole, last_x = _measure(c, fnt, text), _measure(c, fnt, text[:-1])
            ends.append((text[0], x, text[-1], x + last_x, y,
                         min(whole - _measure(c, fnt, text[0]), last_x)))
    band = None
    if len(lines) == 1 and len(lines[0][0]) > 2:   # (inside the end letters, never to the word's edges: F-37)
        line, x = lines[0][0], lines[0][1]
        base = box[1] + float(c.tk.call("font", "metrics", fnt, "-ascent"))
        band = (x + _measure(c, fnt, line[0]), base - SMEAR_BODY * em, x + _measure(c, fnt, line[:-1]),
                base - 0.02 * em)
    short = []                       # (run of short letters, its x, y, its room to the first letter and to the last)
    for text, x, y in lines if len(lines) == 1 else ():   # (not a wrapped meaning: small text, many runs, F-38)
        i, end = 2, len(text) - 2                       # (from the third letter to the third from the end)
        first_w, last_x = _measure(c, fnt, text[:1]), _measure(c, fnt, text[:-1])
        while i < end:
            if text[i] not in SHORT_LETTERS:
                i += 1
                continue
            j = i
            while j < end and text[j] in SHORT_LETTERS:
                j += 1
            left = _measure(c, fnt, text[:i])
            short.append((text[i:j], x + left, y, left - first_w, last_x - _measure(c, fnt, text[:j])))
            i = j
    holes = []
    if len(lines) == 1:                          # (inside each letter's holes: never past its ink, F-40)
        line, x = lines[0][0], lines[0][1]
        base = box[1] + float(c.tk.call("font", "metrics", fnt, "-ascent"))
        holes = [[x + v if k % 2 == 0 else base - v for k, v in enumerate(shape)] for shape in letter_holes(c, fnt, line)]
    out, right = text_overhang(c, fnt, opts["text"])
    lay = {"font": fnt, "lines": rows, "band": band, "short": short, "ends": ends, "holes": holes,
           "n": _measure(c, fnt, "n"), "gap": max(1, round(em / 40)), "near": max(1, round(em / 20)),
           "reach": (box[0] - out - 2, box[1] - 1, box[2] + right + 2, box[3] + 1)}
    if len(cache) > 64:
        cache.clear()
    cache[key] = lay
    return lay

def _measure(c, fnt, text):
    return float(c.tk.call("font", "measure", fnt, text))


def _smear_lines(c, item, opts, box, linespace):
    """[(line's text, its left x, its top y)] as Tk laid out text `item` (wrapped at its width, if any): where each
    line starts is the letter Tk finds at its left end; where it sits, from the item's anchor point, the widest
    line and its justify (its bbox is a pixel wider than the letters)."""
    text, justify, fnt = opts["text"], opts["justify"], opts["font"]
    n = max(1, round((box[3] - box[1]) / linespace))
    if n == 1:
        starts = [0]
    else:
        starts = []
        for k in range(n):
            try:
                i = int(c.index(item, f"@{box[0] - 10},{box[1] + (k + 0.5) * linespace}"))
            except (tk.TclError, ValueError):
                i = starts[-1] if starts else 0
            if not starts or i > starts[-1]:
                starts.append(i)
    rows = [text[i:starts[k + 1] if k + 1 < len(starts) else len(text)].rstrip("\n").rstrip()
            for k, i in enumerate(starts)]
    widths = [_measure(c, fnt, r) for r in rows]
    wide, high = max(widths), len(rows) * linespace
    ax, ay = c.coords(item)[:2]
    anchor = opts["anchor"] or "center"
    left = ax - wide * (0.0 if "w" in anchor else 1.0 if "e" in anchor else 0.5)
    top = ay - high * (0.0 if "n" in anchor else 1.0 if "s" in anchor else 0.5)
    j = {"center": 0.5, "right": 1.0}.get(justify, 0.0)
    return [(r, round(left + (wide - w) * j), round(top + k * linespace)) for k, (r, w) in enumerate(zip(rows, widths))]


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
WORD_PATTERN = re.compile(r"[^\W\d_]+(?:['\u2019-][^\W\d_]+)*")


def smeared_label(parent, text, font_, bg, animator=None, width=0, fg=None, hover=True, on_word=None):
    """A small canvas showing `text` smeared (smear_items; wrapped at `width` pixels, 0: one line), for the places
    that are not our own canvases (the definition panes, Browse's list). It un-smears while the pointer is over it
    (`hover`), or when the caller says so: canvas.unsmear.hover(on, animator). `on_word` (W-2): once it shows, the
    word under the pointer is underlined, as in the pane around it, and a click calls on_word(word)."""
    fg = PALETTE["text"] if fg is None else fg
    c = tk.Canvas(parent, bg=bg, highlightthickness=0, bd=0, cursor="arrow")
    item = c.create_text(0, 0, text=text, font=font_, width=width, anchor="nw", fill=fg, tags="gloss")
    x0, y0, x1, y1 = c.bbox(item) or (0, 0, 0, 0)          # (no box for an empty text)
    c.configure(width=x1 + 1, height=y1 + 1)
    smear = c.unsmear = Unsmear(c, "smear")
    smear.place(item, text, fg, bg)
    if hover:
        c.bind("<Enter>", lambda e: smear.hover(True, animator))
        c.bind("<Leave>", lambda e: (smear.hover(False, animator), _underline(c, None)))
    if on_word:
        c.word_at = lambda x, y: _canvas_word(c, item, text, font_, width, x, y) if smear.clear >= 1.0 else None

        def motion(e):
            hit = c.word_at(e.x, e.y)
            _underline(c, hit, fg)
            c.configure(cursor="hand2" if hit else "arrow")

        def click(e):
            hit = c.word_at(e.x, e.y)
            if hit:
                on_word(hit[0])
        c.bind("<Motion>", motion, add="+")
        c.bind("<Button-1>", click, add="+")
        if not hover:
            c.bind("<Leave>", lambda e: _underline(c, None), add="+")
    return c


def _canvas_word(c, item, text, font_, width, x, y):
    """(word, (x0, x1, y) of its underline) for the word under x, y of a smeared_label's text, or None. A canvas text
    tells only which letter is under a point; where a word starts and ends is measured by laying out the text up to
    each end the same way (wrapped at `width`)."""
    try:
        i = int(c.index(item, f"@{x},{y}"))
    except (tk.TclError, ValueError):
        return None
    box = c.bbox(item)
    if not box or not (box[0] <= x <= box[2] and box[1] <= y <= box[3]):
        return None
    for m in WORD_PATTERN.finditer(text):
        if m.start() <= i < m.end():
            break
    else:
        return None

    def end_of(n):                       # (the right edge and bottom of the text up to n letters)
        probe = c.create_text(0, 0, text=text[:n], font=font_, width=width, anchor="nw", state="hidden")
        c.itemconfigure(probe, state="normal")
        b = c.bbox(probe)
        c.delete(probe)
        return (b[2], b[3]) if b else (0, 0)
    k = len(text[:m.start()].rstrip())   # (measured up to the last letter before it, then the spaces added: Aqua's
    sx, sy = end_of(k) if k else (0, None)   # bbox leaves a text's trailing spaces out, so the underline began there)
    if k:
        sx += int(c.tk.call("font", "measure", font_, text[k:m.start()]))
    ex, ey = end_of(m.end())
    if sy is not None and sy != ey:      # (the word starts the next line)
        sx = 0
    if not (sx <= x <= ex + 1):
        return None
    return m.group(0).lower(), (sx, ex, ey - 2)


def _underline(c, hit, ink=None):
    try:
        c.delete("link")
        if hit:
            x0, x1, y = hit[1]
            c.create_line(x0, y, x1, y, fill=ink or PALETTE["text"], tags="link")
    except tk.TclError:
        pass


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
