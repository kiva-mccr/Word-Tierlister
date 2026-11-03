"""The review of rude meanings by hand (OB-9, a developer option: python tierlist.py --review-rude [FILE]).

A window over the main one goes through a review file (constants.REVIEW_FILE next to the save, from
tools/measure_rudeness.py sample: JSON lines, commonest first), word by word. For each word it shows the meanings
worth asking about (the main one, then those with a sign of rudeness), each with the rules' guess filled in, and
whether the rules smear the whole word. The keys (the keymap's "review" group, changeable) answer:

    1 ... 7      the kind of the selected meaning (Clean, Clinical, Crude, Swear word, Insult, Sexual, Slur); the
                 next meaning is selected after it
    Up / Down    another meaning (a click on one, or on its kind, selects it too)
    S            smear the whole word, or not
    Enter        keep the answers (as shown) and go on to the next word
    Backspace    back one word, as it was answered

The answers go to the answers file beside the review file (constants.review_answers_path), rewritten after every
word, so stopping any time loses nothing and starting again carries on at the first word not answered. Nothing is
smeared here, and nothing in the save changes: the answers only test and tune the rules (measure_rudeness answers).

    RudeReview(app, path)          # app: the main App (root, keys, animator)
"""

import json
import os
import tkinter as tk

from constants import review_answers_path
from fonts import font
from keymap import spec_of
from sizing import keep_on_screen, place_dialog
from theme import PALETTE, TIER_COLORS
from ui_style import set_icon
from widgets import RoundButton

KINDS = (("clean", "Clean"), ("clinical", "Clinical"), ("crude", "Crude"), ("swear", "Swear word"),
         ("insult", "Insult"), ("sexual", "Sexual"), ("slur", "Slur"))
KIND_NAMES = dict(KINDS)
WRAP_CHARS = 64           # a meaning wraps at this many average characters


TIER_OF_KIND = {"clinical": 4, "crude": 1, "swear": 2, "insult": 5, "sexual": 0, "slur": 3}   # (as in the mock-up)


def kind_colour(kind):
    """A kind's pastel: a tier colour each (read now: they can be changed), Clean the plain neutral."""
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
    """{word: {"keys", "kinds", "whole"}} from an answers file, or {} when there is none yet."""
    out = {}
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


def write_answers(path, answers, order):
    """Write every answer (in the review's order) to `path`, through a temporary file, so a crash mid-write never
    leaves half a file."""
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        for w in order:
            if w in answers:
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
        self.history = []                        # the words answered this time, for Back
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
        self.word = tk.Label(box, font=font("heading"), bg=bg, fg=PALETTE["text"])
        self.word.pack(pady=(16, 2))
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
        self.whole_btn = RoundButton(nav, "", self.toggle_whole, bg=PALETTE["surface"], font=body, padx=14, pady=6,
                                     radius=12, animator=app.anim)
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
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()

    # ---- state ----------------------------------------------------------------------------------------------
    @property
    def item(self):
        return self.items[self.i] if self.i < len(self.items) else None

    def _load(self):
        """Show the current word: its earlier answers if it has them, else the rules' guesses."""
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
        self.back_btn.set_enabled(bool(self.history) or self.i > 0)
        if it is None:
            self.word.config(text="Every word is answered" if total else "Nothing to review")
            self.why.config(text=f"The answers are in {self.answers_path}" if total else
                            f"{self.path} has no words: make one with tools/measure_rudeness.py sample")
            for w in self.rows.winfo_children():
                w.destroy()
            self.ask.config(text="")
            for b in (*self.kind_btns.values(), self.whole_btn, self.next_btn):
                b.set_enabled(False)
            self._refit()
            return
        for b in (*self.kind_btns.values(), self.whole_btn, self.next_btn):
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
        self.whole_btn.config(text="Smear the whole word: " + ("yes" if self.whole else "no"))
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
        """The kind of the selected meaning (a button or its key); the next meaning is selected after it."""
        if self.item is None:
            return
        self.kinds[self.sel] = kind
        self.sel = min(self.sel + 1, len(self.kinds) - 1)
        self._render()

    def toggle_whole(self):
        """Smear the whole word, or not."""
        if self.item is not None:
            self.whole = not self.whole
            self._render()

    def next_word(self):
        """Keep this word's answers (as shown), save them all, and go on to the next word not answered yet."""
        it = self.item
        if it is None:
            return
        self.answers[it["w"]] = {"w": it["w"], "keys": [s["key"] for s in it["senses"]], "kinds": list(self.kinds),
                                 "whole": self.whole}
        write_answers(self.answers_path, self.answers, self.order)
        self.history.append(self.i)
        nxt = next((n for n in range(self.i + 1, len(self.items)) if self.items[n]["w"] not in self.answers), None)
        if nxt is None:
            nxt = next((n for n in range(len(self.items)) if self.items[n]["w"] not in self.answers),
                       len(self.items))
        self.i = nxt
        self._load()

    def back(self):
        """Back one word (the last one answered this time, else the one before), shown as it was answered."""
        if self.history:
            self.i = self.history.pop()
        elif self.i > 0:
            self.i -= 1
        else:
            return
        self._load()

    # ---- keys -----------------------------------------------------------------------------------------------
    def apply_keys(self):
        """Show the keymap's keys on the buttons (App.apply_keys calls this after a change)."""
        km = self.app.keys
        hint = lambda a: " / ".join(km.display(a, short=True))
        for k, b in self.kind_btns.items():
            b.config(hint=hint("review_" + k))
        self.whole_btn.config(hint=hint("review_whole"))
        self.next_btn.config(hint=hint("review_next"))
        self.back_btn.config(hint=hint("review_back"))

    def on_key(self, e):
        """A key press: what the keymap's "review" group says it does."""
        spec = spec_of(e, self._ws)
        action = self.app.keys.lookup("review", spec) if spec else None
        if action is None or not action.startswith("review_"):
            return None
        kind = action[len("review_"):]
        if kind in KIND_NAMES:
            self.set_kind(kind)
        else:
            {"review_up": lambda: self.select(self.sel - 1), "review_down": lambda: self.select(self.sel + 1),
             "review_whole": self.toggle_whole, "review_next": self.next_word, "review_back": self.back}[action]()
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
