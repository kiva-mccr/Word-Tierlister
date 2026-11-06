"""The review of rude meanings by hand (OB-9, a developer option: python tierlist.py --review-rude [FILE]).

A window over the main one goes through a review file (constants.REVIEW_FILE next to the save, from
tools/measure_rudeness.py sample: JSON lines, commonest first), word by word. For each word it shows the meanings
worth asking about (the main one, then those with a sign of rudeness), each with the rules' guess filled in, and
whether the rules smear the whole word. The keys (the keymap's "review" group, changeable) answer:

    1 ... 4      the kind of the selected meaning (Not rude, Expletive, Sexual, Slur: OB-12); it
                 stays selected (moving on by itself made the lit button show the next meaning's kind, which read
                 as the key changing the meaning below: reported)
    Up / Down    another meaning (a click on one, or on its kind, selects it too)
    S            smear the whole word, or not
    Enter        keep the answers (as shown) and go on to the next word in the file
The word's Wiktionary page opens from a small icon at the top right of the word (only while Wiktionary can be
reached; asked for: like the card's icon, no button or key).
    Backspace    back one word in the file, as it was answered (a straight walk: Back then Enter returns to where
                 it was; a history of words answered made Enter after Back skip ahead: reported)
    /            find a word in the file (or the magnifier at the word's top left: asked for, like the card's look-up,
                 UI-51): typing goes over the word, the words that start with it (then those that hold it) drop
                 down under it with their answers, Up / Down and Enter (or a click) go to one, Escape goes back.
                 Enter on a word found this way returns to the word the search started from ("Back to ..." on
                 the Next button); Back walks the file from the found word as usual, and forgets the return.

The answers go to the answers file beside the review file (constants.review_answers_path), rewritten on every
answer (a kind, the whole word) and on Enter, so stopping any time loses nothing and starting again carries on at the first word not answered. Nothing is
smeared here, and nothing in the save changes: the answers only test and tune the rules (measure_rudeness answers).

    RudeReview(app, path)          # app: the main App (root, keys, animator)
"""

import json
import os
import tkinter as tk

from constants import review_answers_path
from fonts import font
from keymap import spec_of
from obscene import set_aside_old_answers
from sizing import keep_on_screen, place_dialog
from theme import PALETTE, TIER_COLORS
from ui_style import set_icon, show_drawn
from buttons import LinkButton, RoundButton, SmearWordButton
from drawer import WIKTIONARY_NOTE
from popups import Tooltip

KINDS = (("clean", "Not rude"), ("expletive", "Expletive"), ("sexual", "Sexual"), ("slur", "Slur"))   # (OB-12)
KIND_NAMES = dict(KINDS)
WRAP_CHARS = 64           # a meaning wraps at this many average characters
FIND_SHOWN = 8            # the most words the search lists under the word
FIND_HINT = "Up / Down: pick  \u00b7  Enter: go to it  \u00b7  Esc: back"
HISTORY_FILE = "rude_tune_history.jsonl"   # (tools/tune_rudeness.py writes a line per finished tune, beside the answers)


TIER_OF_KIND = {"expletive": 2, "sexual": 0, "slur": 3}   # (as in the mock-ups)


def kind_colour(kind):
    """A kind's pastel: a tier colour each (read now: they can be changed), Not rude the plain neutral."""
    if kind == "clean":
        return PALETTE["neutral"]
    return TIER_COLORS[TIER_OF_KIND[kind]]


# ---- the files (no tkinter needed) ----------------------------------------------------------------------------
def read_review(path):
    """The review file's words, in order: [{"w", "why", "whole", "senses": [{"key", "pos", "labels", "gloss",
    "guess"}]}]. Lines that are not JSON are skipped."""
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict) and item.get("w") and item.get("senses"):
                items.append(item)
    return items


def read_answers(path):
    """{word: {"keys", "kinds", "whole"}} from an answers file, or {} when there is none yet (or it was in the old six
    kinds: set aside, obscene.set_aside_old_answers)."""
    out = {}
    if set_aside_old_answers(path):
        return out
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    a = json.loads(line)
                    out[a["w"]] = a
                except (ValueError, KeyError, TypeError):
                    continue
    except OSError:
        pass
    return out


def read_history(answers_path):
    """The earlier tunes beside the answers file, oldest first: [{"words", "start", "best", "kept", ...}] (the
    tuner's history file: "start" / "best" are tested errors in %, lower is better), or [] when there are none."""
    out = []
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(answers_path)), HISTORY_FILE), encoding="utf-8") as f:
            for line in f:
                try:
                    h = json.loads(line)
                except ValueError:
                    continue
                if isinstance(h, dict) and {"words", "start", "best"} <= set(h):
                    out.append(h)
    except OSError:
        pass
    return out


def find_words(order, typed, limit=FIND_SHOWN):
    """The words of `order` (the file's, commonest first) that start with `typed`, then those that only hold it,
    at most `limit`; case is ignored. Nothing for nothing typed."""
    t = typed.strip().lower()
    if not t:
        return []
    starts = [w for w in order if w.lower().startswith(t)][:limit]
    if len(starts) < limit:
        starts += [w for w in order if t in w.lower() and not w.lower().startswith(t)][:limit - len(starts)]
    return starts


def answer_kinds(answer):
    """The kinds an answer gave its meanings, rude ones in KINDS order, or ["clean"] when none is rude."""
    given = set(answer.get("kinds", []))
    return [k for k, _n in KINDS if k != "clean" and k in given] or ["clean"]


def write_answers(path, answers, order):
    """Write every answer to `path` (the review's words in its order, then any others: answers from an earlier,
    smaller review are kept), through a temporary file, so a crash mid-write never leaves half a file."""
    tmp = path + ".part"
    listed = set(order)
    with open(tmp, "w", encoding="utf-8") as f:
        for w in [w for w in order if w in answers] + [w for w in answers if w not in listed]:
            f.write(json.dumps(answers[w], ensure_ascii=False) + "\n")
    os.replace(tmp, path)


# ---- the window ---------------------------------------------------------------------------------------------
class RudeReview:
    """The review window (see the module's note)."""

    def __init__(self, app, path):
        self.app, self.path = app, path
        self.answers_path = review_answers_path(path)
        self.items = read_review(path)
        self.order = [it["w"] for it in self.items]
        self.answers = read_answers(self.answers_path)
        self.i = next((n for n, it in enumerate(self.items) if it["w"] not in self.answers), len(self.items))
        self.sel, self.kinds, self.whole = 0, [], False
        self.typing, self.typed, self.found, self.found_sel = False, "", [], 0
        self.return_to = None                    # (the word a search started from: Enter on the found one goes back)
        bg = PALETTE["bg"]
        self.win = tk.Toplevel(app.root)
        self.win.withdraw()                      # (shown once built and placed)
        self.win.title("Review rude meanings")
        self.win.configure(bg=bg)
        set_icon(self.win)
        self._ws = app.root.tk.call("tk", "windowingsystem")
        body = font("body")
        self.wrap = body.measure("n") * WRAP_CHARS
        box = self.box = tk.Frame(self.win, bg=bg, padx=26, pady=20)
        box.pack(fill="both", expand=True)
        top = tk.Frame(box, bg=bg)
        top.pack(fill="x")
        tk.Label(top, text="Review rude meanings", font=font("head"), bg=bg, fg=PALETTE["text"]).pack(side="left")
        self.count = tk.Label(top, font=body, bg=bg, fg=PALETTE["muted"])
        self.count.pack(side="right")
        tk.Label(box, text="A developer option: nothing is smeared here, and the answers only test the rules.",
                 font=font("small"), bg=bg, fg=PALETTE["muted"]).pack(anchor="w")
        tunes = tk.Frame(box, bg=bg)                 # (DT-6: earlier tunes, the next automatic one, one by hand)
        tunes.pack(fill="x", pady=(10, 0))
        self.tune_btn = RoundButton(tunes, "Tune & reroll now", lambda: self.app.devtools.tune_reroll(None), bg=PALETTE["surface"],
                                    font=font("small"), padx=10, pady=3, radius=10, animator=app.anim)
        self.tune_btn.pack(side="right", padx=(8, 0))
        self.next_tune = tk.Label(tunes, font=font("small"), bg=bg, fg=PALETTE["muted"])
        self.next_tune.pack(side="right", padx=(12, 0))
        self.strip = tk.Canvas(tunes, bg=bg, highlightthickness=0, bd=0, height=self._strip_height())
        self.strip.pack(side="left", fill="x", expand=True)
        self.strip.bind("<Configure>", lambda e: self._draw_strip())
        head = tk.Frame(box, bg=bg)
        head.pack(fill="x", pady=(16, 2))
        self.word = tk.Label(head, font=font("heading"), bg=bg, fg=PALETTE["text"])
        self.word.pack()
        size = max(12, int(font("heading").metrics("linespace") * 0.6))   # (the word's Wiktionary page, like the
        self.wikt_link = LinkButton(head, "external", self.open_wiktionary, note=WIKTIONARY_NOTE, size=size, bg=bg)
        self._wikt_shown = False                                         # card's icon: only while online)
        self.find_link = LinkButton(head, "search", self.start_find, size=size, bg=bg)   # (its mirror on the left)
        self.find_link.place(relx=0.0, rely=0.0, anchor="nw")
        Tooltip(self.find_link, lambda e: self._find_note())
        self.drop = tk.Frame(box, bg=PALETTE["surface"], highlightthickness=1, highlightbackground=PALETTE["border"])
        self.why = tk.Label(box, font=body, bg=bg, fg=PALETTE["muted"])
        self.why.pack()
        self.rows = tk.Frame(box, bg=bg)
        self.rows.pack(fill="x", pady=(14, 0))
        self.ask = tk.Label(box, font=body, bg=bg, fg=PALETTE["muted"])
        self.ask.pack(pady=(14, 6))
        kinds = tk.Frame(box, bg=bg)
        kinds.pack()
        self.kind_btns = {}
        for k, name in KINDS:
            b = RoundButton(kinds, name, lambda k=k: self.set_kind(k), bg=kind_colour(k), font=body, padx=12,
                            pady=6, radius=12, animator=app.anim)
            b.pack(side="left", padx=3)
            self.kind_btns[k] = b
        nav = tk.Frame(box, bg=bg)
        nav.pack(fill="x", pady=(16, 0))
        self.whole_btn = SmearWordButton(nav, "Smear the whole word", self.toggle_whole, font_=body,
                                         animator=app.anim)       # (the word itself, smeared when yes: DT-6)
        self.whole_btn.pack(side="left")
        self.next_btn = RoundButton(nav, "Next word", self.next_word, bg=PALETTE["select_bg"], font=body,
                                    padx=16, pady=6, radius=12, animator=app.anim)
        self.next_btn.pack(side="right")
        self.back_btn = RoundButton(nav, "Back", self.back, bg=PALETTE["surface"], font=body, padx=16, pady=6,
                                    radius=12, animator=app.anim)
        self.back_btn.pack(side="right", padx=(0, 8))
        self.saved = tk.Label(box, font=font("small"), bg=bg, fg=PALETTE["muted"],
                              text=f"Answers are kept in {self.answers_path}")
        self.saved.pack(anchor="w", pady=(14, 0))
        self.win.bind("<Key>", self.on_key)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.apply_keys()
        self._load()
        place_dialog(self.win, app.root)
        show_drawn(self.win)                     # (appears complete)
        self.win.lift()
        self.win.focus_force()

    # ---- state ----------------------------------------------------------------------------------------------
    @property
    def item(self):
        return self.items[self.i] if self.i < len(self.items) else None

    def _load(self):
        """Show the current word: its earlier answers if it has them, else the rules' guesses."""
        self.end_find()
        it = self.item
        if it is not None:
            a = self.answers.get(it["w"])
            keys = [s["key"] for s in it["senses"]]
            if a and list(a.get("keys", [])) == keys:
                self.kinds, self.whole = list(a["kinds"]), bool(a["whole"])
            else:
                self.kinds, self.whole = [s["guess"] if s["guess"] in KIND_NAMES else "clean"
                                          for s in it["senses"]], bool(it.get("whole"))
            self.sel = 0
        self._render(new=True)

    def _render(self, new=False):
        """Draw the word, its meanings (the selected one tinted, each with its kind), the question and the count.
        `new`: a different word (its rows are made again; otherwise only their colours and kinds change)."""
        it = self.item
        done = sum(1 for w in self.order if w in self.answers)
        total = len(self.items)
        self.count.config(text=f"{done:,} of {total:,} answered ({100 * done // max(1, total)}%)")
        self._draw_strip()
        if self.back_btn.enabled != (self.i > 0):
            self.back_btn.set_enabled(self.i > 0)
        nxt = "Next word" if self.return_to is None else f"Back to {self.items[self.return_to]['w']}"
        if self.next_btn.cget("text") != nxt:
            self.next_btn.config(text=nxt)
        self.show_online()
        if it is None:
            self.word.config(text="Every word is answered" if total else "Nothing to review")
            self.why.config(text=f"The answers are in {self.answers_path}" if total else
                            f"{self.path} has no words: make one with tools/measure_rudeness.py sample")
            for w in self.rows.winfo_children():
                w.destroy()
            self.ask.config(text="")
            for b in (*self.kind_btns.values(), self.whole_btn, self.next_btn):
                if b.enabled:
                    b.set_enabled(False)
            self._refit()
            return
        for b in (*self.kind_btns.values(), self.whole_btn, self.next_btn):
            if not b.enabled:                # (only on a change: it starts a fade)
                b.set_enabled(True)
        if new:
            self.word.config(text=it["w"])               # (never smeared: judging it needs the real word)
            guess = "smeared whole" if it.get("whole") else "not smeared whole"
            self.why.config(text=f"Here because {it.get('why', '')}  ·  the rules: {guess}")
            for w in self.rows.winfo_children():
                w.destroy()
            self.row_parts = []
            for n, s in enumerate(it["senses"]):
                self.row_parts.append(self._make_row(n, s))
        for n, (row, labels, chip) in enumerate(self.row_parts):
            fill = PALETTE["surface2"] if n == self.sel else PALETTE["surface"]
            row.config(bg=fill)
            for lab in labels:
                lab.config(bg=fill)
            if tk.Canvas.cget(chip, "background") != fill:
                tk.Canvas.configure(chip, background=fill)       # (its shape's edge is blended with the row's)
            chip.config(text=KIND_NAMES[self.kinds[n]], bg=kind_colour(self.kinds[n]))
        self.ask.config(text=f"Kind of meaning {self.sel + 1}:" if len(it["senses"]) > 1 else "Kind of this meaning:")
        for k, b in self.kind_btns.items():           # the selected meaning's kind in its colour, the rest plain
            b.config(bg=kind_colour(k) if k == self.kinds[self.sel] else PALETTE["surface"])
        self.whole_btn.show(it["w"], self.whole)
        if new:
            self._refit()

    def _make_row(self, n, s):
        """One meaning's row: "1.  noun  (vulgar, slang)" over its definition, its kind on the right."""
        fill = PALETTE["surface"]
        row = tk.Frame(self.rows, bg=fill, highlightthickness=1, highlightbackground=PALETTE["border"], padx=12,
                       pady=6)
        row.pack(fill="x", pady=3)
        labels = [lab for lab in s.get("labels", []) if lab]
        head = f"{n + 1}.  {s.get('pos', '')}" + (f"  ({', '.join(labels)})" if labels else "")
        h = tk.Label(row, text=head, font=font("small"), bg=fill, fg=PALETTE["muted"], anchor="w")
        h.grid(row=0, column=0, sticky="w")
        g = tk.Label(row, text=s.get("gloss", ""), font=font("body"), bg=fill, fg=PALETTE["text"], anchor="w",
                     justify="left", wraplength=self.wrap)
        g.grid(row=1, column=0, sticky="w")
        row.columnconfigure(0, weight=1)
        chip = RoundButton(row, KIND_NAMES[self.kinds[n]], lambda n=n: self.select(n), bg=kind_colour(self.kinds[n]),
                           font=font("small"), padx=10, pady=2, radius=10, canvas_bg=fill, animator=self.app.anim)
        chip.grid(row=0, column=1, rowspan=2, sticky="ne", padx=(12, 0))
        for w in (row, h, g):
            w.bind("<Button-1>", lambda e, n=n: self.select(n))
        return row, (h, g), chip

    # ---- earlier tunes (DT-6) -------------------------------------------------------------------------------
    def _strip_height(self):
        return font("small").metrics("linespace") * 2 + 12

    def strip_marks(self):
        """What the strip shows: (answered words, [(words, error %, kept)] of the earlier tunes, the words at which the
        next automatic Tune & reroll starts, or None)."""
        n = len(self.answers)
        past = [(int(h["words"]), float(h["best"] if h.get("kept") else h["start"]), bool(h.get("kept")))
                for h in read_history(self.answers_path)]
        tools = getattr(self.app, "devtools", None)
        nxt = tools.next_auto_tune(n) if tools is not None else None
        return n, past, nxt

    def _draw_strip(self):
        """A line from no answers to the next automatic tune: filled as far as the answers go, a tick at each earlier
        tune with its tested error over it (lower is better; hollow: its numbers were not kept), the words under it,
        and, beside it, how many answers until the next tune."""
        c = self.strip
        c.delete("all")
        w = c.winfo_width()
        if w < 40:
            return
        n, past, nxt = self.strip_marks()
        small = font("small")
        line = small.metrics("linespace")
        top = max([n, nxt or 0] + [p[0] for p in past]) or 1
        x0, x1, y = 2, w - 2, line + 4
        at = lambda words: x0 + (x1 - x0) * words / top
        c.create_line(x0, y, x1, y, fill=PALETTE["border"], width=4, capstyle="round")
        if n:
            c.create_line(x0, y, at(n), y, fill=PALETTE["ring"], width=4, capstyle="round")
        last = -999
        for words, err, kept in past:
            x = at(words)
            c.create_line(x, y - 6, x, y + 6, fill=PALETTE["ring"] if kept else PALETTE["muted"], width=2)
            if x - last > small.measure("00% error") + 8:     # (crowded ticks: only some are labelled)
                c.create_text(x, y - 7, text=f"{err:.0f}% error", font=small, anchor="s", fill=PALETTE["muted"])
                c.create_text(x, y + 7, text=f"{words:,}", font=small, anchor="n", fill=PALETTE["muted"])
                last = x
        if nxt:
            x = at(nxt)
            c.create_line(x, y - 6, x, y + 6, fill=PALETTE["border"], width=2)
        self.next_tune.config(text=f"next tune in {max(0, nxt - n):,}" if nxt else "")

    def _refit(self):
        """Size the window to its contents (a word with more meanings is taller), kept on its monitor."""
        self.win.update_idletasks()
        self.win.geometry("")
        keep_on_screen(self.win)

    # ---- answering ------------------------------------------------------------------------------------------
    def select(self, n):
        """Select meaning `n` (a click on it, or Up / Down)."""
        if self.item is not None and 0 <= n < len(self.kinds) and n != self.sel:
            self.sel = n
            self._render()

    def set_kind(self, kind):
        """The kind of the selected meaning (a button or its key); it stays selected (Down moves on)."""
        if self.item is None:
            return
        self.kinds[self.sel] = kind
        self._save()
        self._render()

    def toggle_whole(self):
        """Smear the whole word, or not."""
        if self.item is not None:
            self.whole = not self.whole
            self._save()
            self._render()

    def next_word(self):
        """Keep this word's answers (as shown, the guesses too) and go on to the next word in the file."""
        if self.item is None:
            return
        self._save()
        if self.return_to is not None:           # a word found by the search: back to where the search started
            self.i, self.return_to = self.return_to, None
            self._load()
            return
        self.i += 1                              # the next word in the file (shown as answered if it was)
        if self.i >= len(self.items):            # past the last: any word skipped earlier, else the end
            self.i = next((n for n in range(len(self.items)) if self.items[n]["w"] not in self.answers),
                          len(self.items))
        self._load()

    def _save(self):
        """Save this word's answers as shown, at once (every kind key or click, not only on moving on: going Back
        after changing a kind kept the old answer, reported), and rewrite the answers file."""
        it = self.item
        self.answers[it["w"]] = {"w": it["w"], "keys": [s["key"] for s in it["senses"]], "kinds": list(self.kinds),
                                 "whole": self.whole}
        write_answers(self.answers_path, self.answers, self.order)
        tools = getattr(self.app, "devtools", None)
        if tools is not None:
            tools.review_answered(len(self.answers))          # (DT-6: every 50 new answers, Tune & reroll starts by itself)

    def back(self):
        """Back one word in the file, shown as it was answered."""
        if self.i > 0:
            self.i -= 1
            self.return_to = None                # (walking the file again from the found word)
            self._load()

    def open_wiktionary(self):
        """The word's Wiktionary page in the browser (the same link as a definition's)."""
        if self.item is not None and self.app.online.online:
            self.app.open_wiktionary(self.item["w"])

    def show_online(self):
        """The Wiktionary icon at the word area's top right, only while there is a word and Wiktionary can be
        reached (asked for: an icon like the card's, no button or key)."""
        on = self.item is not None and bool(self.app.online.online)
        if on != self._wikt_shown:
            self._wikt_shown = on
            if on:
                self.wikt_link.place(relx=1.0, rely=0.0, anchor="ne")
            else:
                self.wikt_link.place_forget()

    # ---- finding a word ---------------------------------------------------------------------------------------
    def _find_note(self):
        """The magnifier's hover note, with its key."""
        if self.typing:
            return "Back to the word"
        keys = self.app.keys.display("review_find")
        return "Find a word" + (f" ({keys[0]})" if keys else "")

    def start_find(self):
        """The magnifier (or its key): type over the word to find one in the file; again, it goes back."""
        if self.typing:
            self.end_find()
            self._render(new=True)
            return
        if not self.items:
            return
        self.typing, self.typed, self.found, self.found_sel = True, "", [], 0
        self._show_find()

    def end_find(self):
        """Stop typing (the word comes back with the next render)."""
        if self.typing:
            self.typing = False
            self.drop.place_forget()
            self.word.config(fg=PALETTE["text"])

    def find_key(self, e):
        """A key while typing: letters add, Backspace takes one off, Up / Down pick, Enter goes, Escape goes back."""
        ks, ch = e.keysym, getattr(e, "char", "") or ""
        if ks in ("Return", "KP_Enter"):
            if self.found:
                self.go_to(self.found[self.found_sel])
            return
        if ks == "Escape":
            self.end_find()
            self._render(new=True)
            return
        if ks in ("Up", "Down"):
            if self.found:
                self.found_sel = (self.found_sel + (1 if ks == "Down" else -1)) % len(self.found)
                self._draw_drop()
            return
        if ks == "BackSpace":
            self.typed = self.typed[:-1]
        elif len(ch) == 1 and ch.isprintable() and len(self.typed) < 60 and (ch != " " or self.typed):
            self.typed += ch
        else:
            return
        self.found, self.found_sel = find_words(self.order, self.typed), 0
        self._show_find()

    def go_to(self, word):
        """Show `word` from the file; Enter on it returns to the word the search started from."""
        n = self.order.index(word)
        if n != self.i:
            if self.return_to is None and self.item is not None:
                self.return_to = self.i
            elif self.return_to == n:            # (found the word the search started from: just back there)
                self.return_to = None
            self.i = n
        self._load()

    def _show_find(self):
        """The typed letters over the word (a lilac caret after them), the keys under it, the matches below."""
        if self.typed:
            self.word.config(text=self.typed + "\u2009|", fg=PALETTE["accent"])
        else:
            self.word.config(text="type a word\u2009|", fg=PALETTE["muted"])
        self.why.config(text=FIND_HINT)
        self._draw_drop()

    def _draw_drop(self):
        """The words found, under the word, each with its answer (the kinds given) or "not answered yet"."""
        for w in self.drop.winfo_children():
            w.destroy()
        if not self.typed:
            self.drop.place_forget()
            return
        body, small = font("body"), font("small")
        row_h = body.metrics("linespace") + 10
        self.win.update_idletasks()
        y = self.word.master.winfo_y() + self.word.winfo_height() + 2
        room = max(1, (self.box.winfo_height() - y - 8) // row_h)
        shown = self.found[:room]
        if not shown:
            tk.Label(self.drop, text="No word in the review matches", font=small, bg=PALETTE["surface"],
                     fg=PALETTE["muted"], padx=12, pady=6).pack(fill="x")
        for n, w in enumerate(shown):
            fill = PALETTE["surface2"] if n == self.found_sel else PALETTE["surface"]
            row = tk.Frame(self.drop, bg=fill, padx=12, pady=4, cursor="hand2")
            row.pack(fill="x")
            parts = [row, tk.Label(row, text=w, font=body, bg=fill, fg=PALETTE["text"])]
            parts[-1].pack(side="left")
            a = self.answers.get(w)
            if a:
                for k in reversed(answer_kinds(a)):
                    chip = RoundButton(row, KIND_NAMES[k], lambda w=w: self.go_to(w), bg=kind_colour(k), font=small,
                                       padx=8, pady=1, radius=9, canvas_bg=fill, animator=self.app.anim)
                    chip.pack(side="right", padx=(4, 0))
            parts.append(tk.Label(row, text="answered" if a else "not answered yet", font=small, bg=fill,
                                  fg=PALETTE["muted"]))
            parts[-1].pack(side="right", padx=(0, 4))
            for p in parts:
                p.bind("<Button-1>", lambda e, w=w: self.go_to(w))
        self.drop.place(x=self.box.winfo_width() // 2, y=y, anchor="n", width=int(self.box.winfo_width() * 0.6))
        self.drop.lift()

    # ---- keys -----------------------------------------------------------------------------------------------
    def apply_keys(self):
        """Show the keymap's keys on the buttons (App.apply_keys calls this after a change)."""
        km = self.app.keys
        hint = lambda a: " / ".join(km.display(a, short=True))
        for k, b in self.kind_btns.items():
            b.config(hint=hint("review_" + k))
        self.whole_btn.set_hint(hint("review_whole"))
        self.next_btn.config(hint=hint("review_next"))
        self.back_btn.config(hint=hint("review_back"))

    def on_key(self, e):
        """A key press: what the keymap's "review" group says it does (while finding a word, the typing)."""
        if self.typing:
            self.find_key(e)
            return "break"
        spec = spec_of(e, self._ws)
        action = self.app.keys.lookup("review", spec) if spec else None
        if action is None or not action.startswith("review_"):
            return None
        kind = action[len("review_"):]
        if kind in KIND_NAMES:
            self.set_kind(kind)
        else:
            {"review_up": lambda: self.select(self.sel - 1), "review_down": lambda: self.select(self.sel + 1),
             "review_whole": self.toggle_whole, "review_next": self.next_word, "review_back": self.back,
             "review_find": self.start_find}[action]()
        return "break"

    def alive(self):
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def close(self):
        """Close the window (the answers are already saved after every word)."""
        if getattr(self.app, "review", None) is self:
            self.app.review = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass
