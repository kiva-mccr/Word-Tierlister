"""The definitions pane (UI-12): DefinitionDrawer eases open and closed; fill_definitions writes words and their senses
into a tk.Text (the word in bold, senses numbered, the part of speech and examples in italics, a censored word and its meanings smeared),
with a Wiktionary link per word and words in meanings that can be clicked to look them up (word_at, W-1).
Its contents are placed for good and its height always set (F-27): never repack them.
"""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from theme import PALETTE
from buttons import LinkButton
from smears import WORD_PATTERN, smeared_label


def definition_tags(t, body):
    """The text tags a definition pane uses (fill_definitions): the word in bold, muted numbers, the part of
    speech and examples in italics, senses indented. The italics are the body's size now: refresh_widgets sets them
    again after a zoom (reported: noun, verb... kept their old size until the pane was filled again)."""
    t._tag_body = body
    italic = (body.cget("family"), body.cget("size"), "italic")
    t.tag_configure("num", foreground=PALETTE["muted"])
    t.tag_configure("pos", foreground=PALETTE["muted"], font=italic)
    t.tag_configure("sense", lmargin1=6, lmargin2=26, spacing1=2)
    t.tag_configure("ex", foreground=PALETTE["muted"], lmargin1=26, lmargin2=26, font=italic)
    t.tag_configure("wait", foreground=PALETTE["muted"])
    t.tag_configure("base", foreground=PALETTE["muted"], lmargin1=26, lmargin2=26, spacing1=1, spacing3=2)
    t.tag_configure("link", underline=True, foreground=PALETTE["text"])     # (W-1: the word under the pointer)
    t.tag_configure("back", foreground=PALETTE["muted"], underline=True, spacing3=4)
    t.tag_raise("link")


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


def fill_definitions(t, entries, body, animator=None, base=None, on_word=None, back=None, link=None):
    """Fill the definition pane `t` (a tk.Text) with [(word, definition text or None while it is being looked up,
    True if the word is censored)]: the word in bold, then each sense numbered, its part of speech, its text and
    example. A censored word (OB-14: on the obscene words list, while censoring) is smeared sideways (not masked),
    and so is each of its meanings after its labels; they un-smear while the pointer is anywhere over the pane.
    `base` (F-3): base(word) -> the same three for another word; under a meaning that only names one ("Alternative form of bull dyke"), that
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
        """The word `name` (a censored one smeared, un-smearing while the pointer is over the pane; a form's word
        can still be clicked, W-2)."""
        if not hide:
            t.insert("end", name, tag)
            return
        c = smeared_label(t, name, font_, t.cget("bg"), animator, hover=False,
                          on_word=(lambda w: t._on_word and t._on_word(w)) if tag == "base" else None)
        t.window_create("end", window=c, align="center")
        by_pane(c)

    def by_pane(c):
        t._smears.append(c)
        t._words.append(c)
        if inside:
            c.unsmear.hover(True)
    t._by_pane = by_pane
    for i, (heading, text, hide) in enumerate(entries):
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
            _insert_gloss(t, sense, "sense", hide, body, animator, prefix)
            if sense["example"]:
                t.insert("end", "\u201c" + sense["example"] + "\u201d\n", "ex")
            target = form_target(sense["gloss"]) if base else None
            if target and target not in shown:          # (each word once: "plural of X" and "past of X" share it)
                shown.add(target)
                name, other, hidden = base(target)
                main = main_sense(other) if other else None
                word(name, hidden, body, "base")
                after = (f" ({main['pos']})" if main and main["pos"] else "") + ": "
                t.insert("end", after, "base")
                if other is None:
                    t.insert("end", "Looking up definition...\n", "base")
                elif main is None:
                    t.insert("end", "No definition found.\n", "base")
                else:
                    _insert_gloss(t, main, "base", hide or hidden, body, animator, " " * 6 + name + after)
    t.config(state="disabled")


LINK_TAGS = ("sense", "ex", "base")     # where a word can be clicked to look it up (W-1): meanings, examples, forms


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
    for m in WORD_PATTERN.finditer(text):
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
    """Once per pane: while the pointer is anywhere over it, its censored words and their meanings un-smear (asked
    for); moving onto a smeared meaning inside it is still over the pane."""
    if getattr(t, "_watched", False):
        return
    t._watched = True

    def over(on):
        for c in getattr(t, "_words", ()):
            c.unsmear.hover(on, t._animator)
    t.bind("<Enter>", lambda e: over(True), add="+")
    t.bind("<Leave>", lambda e: None if _pointer_inside(t) else over(False), add="+")


def _insert_gloss(t, sense, tag, smear, body, animator, prefix):
    """A sense's text and a line end into the pane `t` under `tag`; `smear` (its word is censored): its labels, then
    its gloss smeared (smeared_label, wrapped to the room left on its line; `prefix`: the text already on it). It
    un-smears with the pointer anywhere over the pane (W-2, asked for), and its words can be clicked as the others
    can (on_word)."""
    if not smear:
        t.insert("end", sense["text"] + "\n", tag)
        return
    label = "(" + ", ".join(sense["labels"]) + ") " if sense["labels"] else ""
    t.insert("end", label, ("pos", tag))
    pad = int(t.cget("padx") or 0)
    room = (t.winfo_width() if t.winfo_ismapped() else int(t.cget("width")) * body.measure("0")) - 2 * pad - 30
    width = max(body.measure("n" * 12), room - body.measure(prefix + label))
    c = smeared_label(t, sense["gloss"].strip(), body, t.cget("bg"), animator, width=width, hover=False,
                      on_word=lambda w: t._on_word and t._on_word(w))
    t.window_create("end", window=c, align="top")
    t.insert("end", "\n", tag)
    t._by_pane(c)


class DefinitionDrawer(tk.Frame):
    """The definition pane (UI-12): eases open and closed instead of snapping, and shows each word in bold
    with its senses numbered, the part of speech in italics and examples muted.

        drawer = DefinitionDrawer(root, fonts={"body": font("body"), "head": font("heading")}, animator=app.anim)
        drawer.show_words(["apple"], lambda w: "1. (noun) a fruit\n      e.g. \"an apple a day\"")
        drawer.open() / drawer.close()      # the caller packs it first / unpacks it after on_closed

    `text` is the tk.Text inside (its height in lines is what the window-fitting code shortens).
    """
    SLIDE_MS = 200

    def __init__(self, parent, fonts, animator=None, gap=0):
        super().__init__(parent, bg=PALETTE["bg"])
        self._anim = animator
        self._gap = gap                   # room under the pane, inside it: it slides shut with the pane (packed
                                          # outside it, it jumped the page by that much as the pane left)
        body, head = fonts["body"], fonts["head"]
        self._body = body
        inner = self._inner = tk.Frame(self, bg=PALETTE["surface"], highlightthickness=1,
                                       highlightbackground=PALETTE["border"])
        # The contents are placed for good, at their own height, and the pane's height is always set, never left
        # to the contents: by the slide while it eases, else from them as they change (_follow). Packed between
        # slides (F-2 placed them only while folded), the switch back at each slide's end let the pane size itself
        # for a moment, and now and then a frame showed it empty (F-20), at full height (F-22) or dipping (F-27).
        inner.place(x=0, y=0, relwidth=1)
        inner.bind("<Configure>", lambda e: self._follow())
        self._folded, self._sliding, self._held, self._reopen, self._pinned = False, False, False, False, False
        # one column, or two side by side for a duel's two words (asked for: each under its own card)
        self.texts = [tk.Text(inner, height=9, wrap="word", state="disabled", font=body, bd=0, highlightthickness=0,
                              padx=14, pady=10, bg=PALETTE["surface"], cursor="arrow") for _ in range(2)]
        self.text, self.text2 = self.texts
        self._rule = tk.Frame(inner, width=1, bg=PALETTE["border"])
        for t in self.texts:
            t.tag_configure("head", font=head, spacing1=2, spacing3=4)
            definition_tags(t, body)
        # a slim scroll bar beside each column, only while its meanings do not all fit (F-34, asked for: there was
        # none); its column keeps the bar's width either way, so showing it never re-wraps the text or resizes the pane
        self.bars = [ttk.Scrollbar(inner, orient="vertical", command=t.yview) for t in self.texts]
        for t, bar, col in zip(self.texts, self.bars, (1, 4)):
            t.configure(yscrollcommand=lambda first, last, b=bar: self._scrolled(b, first, last))
            bar.grid(row=0, column=col, sticky="ns", pady=6)
            bar.grid_remove()
        self._bar_w = self.bars[0].winfo_reqwidth()
        inner.columnconfigure(1, minsize=self._bar_w)
        self.text.grid(row=0, column=0, sticky="nsew")
        inner.columnconfigure(0, weight=1)
        self._columns = 1
        self._shown = False
        self._opening = None              # (from, to) pixels while it eases open (give)

    COLUMN_CHARS = 80                     # the one column's width in characters; two share it (the window's size
                                          # never changes for them)

    def _set_columns(self, n):
        """One column (the left text) or two equal ones side by side with a hairline between."""
        if n == self._columns:
            return
        self._columns = n
        inner = self._inner
        if n == 2:                                   # (each half, less its own side padding, its scroll bar's room
            c = max(1, self._body.measure("0"))      # and the hairline, so the two together ask no more room than
            pad = 2 * int(self.text.cget("padx")) + 1 + self._bar_w      # the one column)
            for t in self.texts:
                t.config(width=max(10, (self.COLUMN_CHARS * c - 2 * pad) // (2 * c) - 1))
            self._rule.grid(row=0, column=2, sticky="ns", pady=10)
            self.text2.grid(row=0, column=3, sticky="nsew")
            inner.columnconfigure(0, weight=1, uniform="defs")
            inner.columnconfigure(3, weight=1, uniform="defs")
            inner.columnconfigure(4, minsize=self._bar_w)
        else:
            self._rule.grid_remove()
            self.text2.grid_remove()
            self.bars[1].grid_remove()
            self.text.config(width=self.COLUMN_CHARS)
            inner.columnconfigure(0, weight=1, uniform="")
            inner.columnconfigure(3, weight=0, uniform="")
            inner.columnconfigure(4, minsize=0)

    @property
    def columns(self):
        return self._columns

    def _scrolled(self, bar, first, last):
        """A column's view moved or its meanings changed: its bar follows, shown only while they do not all fit."""
        if self._pinned:
            return                       # (unpin() brings them up to date)
        try:
            bar.set(first, last)
            need = (float(first) > 0.0 or float(last) < 1.0) and (bar is self.bars[0] or self._columns == 2)
            if need != bool(bar.winfo_manager()):
                bar.grid() if need else bar.grid_remove()
        except (tk.TclError, ValueError):
            pass

    def set_lines(self, n):
        """The pane's height in lines (both columns)."""
        for t in self.texts:
            t.config(height=n)

    def lines(self):
        return int(self.text.cget("height"))

    def line_height(self):
        """Pixels a line adds to its height (App._pane_lines works out the lines that fit with it)."""
        return max(1, self._body.metrics("linespace"))

    def show_words(self, words, get_def, censored=None, on_word=None, back=None, link=None):
        """Fill the pane: for each word, its senses (get_def(word) -> text, or None while it is still being looked
        up). `censored(word)`: True for a word shown smeared with its meanings (until the pointer is over the pane).
        A meaning that only names another word shows that word's first meaning under it, looked up the same way (F-3). `on_word`,
        `back`, `link`: see fill_definitions (W-1; the Wiktionary link on each column's word)."""
        def entry(w):
            return w, get_def(w), bool(censored and censored(w))
        two = len(words) == 2 and back is None       # (a duel: each word's meanings on its card's side)
        self._set_columns(2 if two else 1)
        for t, ws, bk in ((self.text, words[:1] if two else words, back), (self.text2, words[1:] if two else [], None)):
            if t is self.text2 and not two:
                continue
            fill_definitions(t, [entry(w) for w in ws], self._body, animator=self._anim, base=entry, on_word=on_word, back=bk, link=link)

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
        if on:
            self._folded = False
            self._follow()

    def _follow(self):
        """Between slides, open: the pane as tall (and asking as wide) as its contents want, gap included."""
        if self._sliding or self._folded or self._held:
            return
        try:
            inner = self._inner
            super().configure(height=max(1, inner.winfo_reqheight() + self._gap), width=inner.winfo_reqwidth())
        except tk.TclError:
            pass

    def collapse(self):
        """Fold to nothing before it is packed for opening, so it never shows at full height first. The contents
        stay at their full height, clipped, so the text keeps its real width and can say how tall it needs to be
        before the pane opens (F-2: it opened at its usual 9 lines, measured 0)."""
        self._folded = True
        super().configure(height=1, width=self._inner.winfo_reqwidth())

    def natural_height(self):
        """The height the contents want (whether or not it is folded right now)."""
        self.update_idletasks()
        self._follow()
        return self._inner.winfo_reqheight() + self._gap

    def height_for(self, lines):
        """Its height with `lines` lines of text (App works out the room it has from one measurement, Z-1)."""
        self.update_idletasks()
        return self._inner.winfo_reqheight() + self._gap + (lines - self.lines()) * self.line_height()

    @property
    def steady(self):
        """Open and still: not sliding, pinned or folded (App._fill_pane eases it from here to a new height)."""
        return self._shown and not (self._sliding or self._folded or self._held)

    def ease_from(self, height):
        """Its contents just changed its height (shortened or lengthened by the window's fit): show it back at
        `height` and ease to the new one."""
        self.update_idletasks()
        end = self._inner.winfo_reqheight() + self._gap
        if not self.steady or abs(end - height) < 2:
            self._follow()                # (pinned at `height` until now: the last pixel or two)
            return
        try:
            super().configure(height=height)
        except tk.TclError:
            return

        def done():
            self._sliding = self.easing = False
            self._follow()
        self.easing = True
        self._slide(height, end, done)

    easing = False                        # (ease_from running: a fit measuring now would count it half-way)

    def pin(self):
        """About to change its lines (App._fill_pane, App._fit_window): keep showing the height it has, so the page
        never shows the change before it eases (it stuttered switching tabs). Sliding open, it stops where it is and
        carries on to its new height at unpin() (it slid on to the old one, then jumped)."""
        if self._opening is not None and self._anim is not None:
            self._anim.stop(f"drawer{id(self)}")
            self._opening, self._sliding, self._reopen = None, False, True
        self._held = True
        self._pin_box(True)

    def unpin(self, follow=True):
        """After pin(): follow the contents again; `follow=False` stays at the pinned height for ease_from to start
        from (following first showed the new height for a frame before the ease began). Stopped sliding open, it
        eases on from there."""
        self._pin_box(False)
        if self._reopen:
            self._reopen = False
            self.open()                     # (held: from the height it has)
            return
        self._held = False
        if follow:
            self._follow()

    def _pin_box(self, on):
        """Keep the box inside at the height it shows, and its scroll bars as they are, while other line counts are
        set (pin): left to follow, the box shrank and grew a line at a time and the bars blinked."""
        if on == self._pinned:
            return
        self._pinned = on
        if on:
            self._inner.place_configure(height=max(1, self._inner.winfo_height()))
            return
        self._inner.place_configure(height="")
        for t, bar in zip(self.texts, self.bars):
            self._scrolled(bar, *t.yview())

    @property
    def opening(self):
        """Sliding open (App._fill_pane pins it to change its lines, then it eases on to its new height)."""
        return self._opening is not None

    def open(self):
        """Ease open from nothing (or, pinned, the height it has) to the height the contents want (the caller has
        packed it already)."""
        self._shown = True
        end = self.natural_height()
        held = self.winfo_reqheight() if self._folded or self._held else 0
        start = min(max(1, held), end)
        self._opening = (start, end)
        self._folded = self._held = False
        self._pin_box(False)

        def done():
            self._opening = None
            self._sliding = False
            self._follow()                      # (the same height it ended at, unless its contents changed since)
        self._slide(start, end, done)

    def close(self, on_closed=None):
        """Ease shut, then call on_closed (the caller unpacks it there)."""
        self._shown = False
        self._opening = None

        def done():
            self._sliding = False
            self._folded = True                 # (left at 1 pixel: unpacked by on_closed, or opened from there)
            if on_closed:
                on_closed()
        self._slide(max(1, self.winfo_height()), 0, done)

    def _slide(self, a, b, done=None):
        self._sliding = True

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
