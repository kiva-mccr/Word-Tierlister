"""Settings > How words are dealt... (ST-6): the order new words come in, which kinds of words, and censoring the
obscene ones. The same pieces make the three-step page shown on the first start.

    DealDialog(app)               # the settings page: Order, Which words and Obscene words on one page
    DealDialog(app, first=True)   # the first start: one step at a time (Back / Next / Done)

Order is "Most common first" (strictly by frequency) or "Mostly common, a little shuffled" with its shape cards
(UI-41), spread, seed and compound strength. Which words: a tick box per kind (constants.KINDS) and one for
obscene words (all of their meanings rude), with how many words each holds; ticking it opens a tick box per kind
of rude meaning (OB-5: obscene.RUDE_KINDS, Clinical, Crude, Swear words and Insults ticked to start with). Unticked
ones are left out of the queue, never deleted (Store.set_deal).
Applying reshuffles / re-deals the unplaced words on a worker thread (App.busy, a moving bar); the censor tick
applies at once.
"""
import gc
import random
import sqlite3
import threading
import tkinter as tk
from tkinter import ttk

from constants import CENSOR_CAVEAT_LINE, KIND_NOTE_EXTRA, KIND_NOTE_RUDE, KIND_NOTES, KINDS, RUDE_LABELS
from obscene import RUDE_KINDS
from rudeness import KIND_BITS
from fonts import font
from theme import PALETTE, TIER_COLORS
from widgets import RoundButton, ShapeCard, StyledDialog, Tooltip

CENSOR_NOTE = "blurred, except on hover"


class DealDialog:
    """The page (or, on the first start, the three steps) of How words are dealt; see the module's note."""
    STEPS = ("order", "kinds", "censor")
    HEADS = {"order": ("How words are dealt", "Choose the order new words come in, and which words. You can change "
                                              "this any time (Settings > How words are dealt)."),
             "kinds": ("Which words", "Leave out kinds you'd rather not sort (they can come back any time)."),
             "censor": ("Obscene words", "Some words are vulgar or offensive.")}

    def __init__(self, app, first=False, on_done=None):
        self.app, self.store, self.first, self.on_done = app, app.store, first, on_done
        cfg, deal = self.store.queue_settings(), self.store.deal_settings()
        self.start_cfg, self.start_deal = cfg, deal
        head, intro = self.HEADS["order"]
        # the first start draws its own headline per step; the settings page has the shared one
        self.dlg = dlg = StyledDialog(app.root, "How words are dealt", None if first else head,
                                      None if first else intro, animator=app.anim, wrap_chars=72)
        self.body = dlg.body
        self.order_v = tk.StringVar(value="rank" if cfg["shape"] == "rank" else "shuffled")
        self.shape_v = tk.StringVar(value=cfg["shape"] if cfg["shape"] != "rank" else "exp")
        self.seed_v = tk.StringVar(value=str(cfg["seed"]))
        self.spread_v = tk.StringVar(value=f"{cfg['spread']:.0f}")
        self.comp_v = tk.StringVar(value=f"{cfg['compound']:g}")
        self.kind_vs = {key: tk.BooleanVar(value=bool(deal["kinds"] & bit)) for key, _, bit in KINDS}
        self.obscene_v = tk.BooleanVar(value=deal["obscene"])
        self.rude_vs = {k: tk.BooleanVar(value=bool(deal["rude"] & KIND_BITS[k])) for k in RUDE_KINDS}
        self.censor_v = tk.BooleanVar(value=deal["censor"])
        if first:
            self.head_lbl = tk.Label(self.body, font=font("head"), bg=PALETTE["bg"], fg=PALETTE["text"],
                                     wraplength=dlg.wrap, justify="left")
            self.intro_lbl = tk.Label(self.body, font=font("body"), bg=PALETTE["bg"], fg=PALETTE["muted"],
                                      wraplength=dlg.wrap, justify="left")
        self.sections = {"order": self._order(), "kinds": self._kinds(), "censor": self._censor()}
        self.status = ttk.Label(self.body, text="", foreground=PALETTE["bad"][1], wraplength=dlg.wrap)
        self.bar = ttk.Progressbar(self.body, mode="indeterminate")
        for v in (self.seed_v, self.spread_v, self.comp_v, self.shape_v, self.order_v, self.obscene_v,
                  *self.kind_vs.values(), *self.rude_vs.values()):
            v.trace_add("write", lambda *_: self.status.grid_remove())        # an edit clears the last note
        self.step = 0
        if first:
            dlg.on_cancel = self._skip
            self._show_step(0)
        else:
            # side by side (Order on the left), so the page fits a small screen (1366 x 768 at 133%)
            self.sections["order"].grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 30))
            self.sections["kinds"].grid(row=0, column=1, sticky="nw")
            self.sections["censor"].grid(row=1, column=1, sticky="nw", pady=(16, 0))
            self.body.rowconfigure(1, weight=1)          # (the Order column's extra height goes under Obscene words)
            dlg.button("Cancel", dlg.close)
            dlg.button("Apply", self.apply, default=True)
        dlg.show()

    # ---- the three parts ------------------------------------------------------------------------------------------
    def _section(self, key):
        f = tk.Frame(self.body, bg=PALETTE["bg"])
        if not self.first:
            tk.Label(f, text=self.HEADS[key][0] if key != "order" else "Order", font=font("label"),
                     bg=PALETTE["bg"], fg=PALETTE["text"]).grid(row=0, column=0, columnspan=4, sticky="w",
                                                                 pady=(0, 6))
        return f

    def _order(self):
        f = self._section("order")
        if self.first:
            tk.Label(f, text="Order", font=font("label"), bg=PALETTE["bg"], fg=PALETTE["text"]).grid(
                row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        row = tk.Frame(f, bg=PALETTE["bg"])
        row.grid(row=1, column=0, columnspan=4, sticky="w")
        self.order_btns = {}
        for key, text, hint in (("rank", "Most common first", "strictly by frequency"),
                                ("shuffled", "Mostly common, a little shuffled", "the default")):
            b = RoundButton(row, text, lambda k=key: self.order_v.set(k), bg=PALETTE["surface"], font=font("body"),
                            hint=hint, padx=12, pady=4, radius=10, animator=self.app.anim)
            b.pack(side="left", padx=(0, 8))
            self.order_btns[key] = b
        self.shuffle_f = sh = tk.Frame(f, bg=PALETTE["bg"])
        cards = tk.Frame(sh, bg=PALETTE["bg"])
        cards.grid(row=0, column=0, columnspan=4, sticky="w", pady=(10, 6))
        self.cards = {}
        for shape, name, colour in (("exp", "Exponential", TIER_COLORS[1]), ("gauss", "Gaussian", TIER_COLORS[4])):
            self.cards[shape] = ShapeCard(cards, shape, name, colour, on_pick=self.shape_v.set)
            self.cards[shape].pack(side="left", padx=(0, 10))
        ttk.Label(sh, text="Spread:").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=3)
        self.spread_e = ttk.Entry(sh, textvariable=self.spread_v, width=12)
        self.spread_e.grid(row=1, column=1, sticky="w")
        ttk.Label(sh, text="ranks  (bigger = more surprises)", foreground=PALETTE["muted"]).grid(
            row=1, column=2, columnspan=2, sticky="w", padx=10)
        ttk.Label(sh, text="Seed:").grid(row=2, column=0, sticky="e", padx=(0, 8), pady=3)
        self.seed_e = ttk.Entry(sh, textvariable=self.seed_v, width=12)
        self.seed_e.grid(row=2, column=1, sticky="w")
        self.new_seed = RoundButton(sh, "New random seed",
                                    lambda: self.seed_v.set(str(random.SystemRandom().randrange(1, 2 ** 31))),
                                    bg=PALETTE["surface"], font=font("body"), padx=12, pady=3, radius=10,
                                    animator=self.app.anim)
        self.new_seed.grid(row=2, column=2, sticky="w", padx=10)
        ttk.Label(sh, text="Compound words:").grid(row=3, column=0, sticky="e", padx=(0, 8), pady=3)
        self.comp_e = ttk.Entry(sh, textvariable=self.comp_v, width=12)
        self.comp_e.grid(row=3, column=1, sticky="w")
        ttk.Label(sh, text="0 = like any word, 1 = default, higher = later",
                  foreground=PALETTE["muted"]).grid(row=3, column=2, columnspan=2, sticky="w", padx=10)
        self.spread_v.trace_add("write", self._redraw)
        self.shape_v.trace_add("write", self._redraw)
        self.order_v.trace_add("write", self._redraw)
        self._redraw()
        return f

    def _redraw(self, *_):
        """The order buttons and shape cards follow the choices; the curves follow the spread as it is typed (an
        unreadable one keeps the last); the shuffle's settings show only for the shuffled order."""
        shuffled = self.order_v.get() == "shuffled"
        for key, b in self.order_btns.items():
            b.config(bg=PALETTE["select_bg"] if (key == "shuffled") == shuffled else PALETTE["surface"])
        try:
            spread = float(self.spread_v.get().replace(",", ""))
        except ValueError:
            spread = None
        if spread is not None and spread <= 0:
            spread = None
        for shape, card in self.cards.items():
            card.set(spread=spread, chosen=shape == self.shape_v.get())
        if shuffled and not self.shuffle_f.winfo_manager():
            self.shuffle_f.grid(row=2, column=0, columnspan=4, sticky="w")
        elif not shuffled and self.shuffle_f.winfo_manager():
            self.shuffle_f.grid_remove()
        if self.dlg.win.winfo_viewable():
            self.dlg.refit()

    def _kinds(self):
        f = self._section("kinds")
        counts = self.store.kind_counts()
        rows = [(key, label, self.kind_vs[key], f"{counts[key]:,}") for key, label, _ in KINDS]
        rows.insert(-1, ("obscene", "Obscene words", self.obscene_v, f"{counts['obscene']:,}"))   # (before Other)
        self.kind_ticks, self.kind_tips = {}, {}
        wrap = font("body").measure("n") * 40
        box_row = None
        for i, (key, label, var, n) in enumerate(rows):    # one column on the first start, two on the page
            r, c = (i, 0) if self.first else (i // 2, (i % 2) * 2)
            if box_row is not None and self.first:
                r += 1                                      # (the kinds of rude meaning open under Obscene words)
            if key == "obscene":
                box_row = 1 + r + 1
            tick = ttk.Checkbutton(f, text=label, variable=var, takefocus=1)
            tick.grid(row=1 + r, column=c, sticky="w", padx=(0, 18))
            count = ttk.Label(f, text=n, foreground=PALETTE["muted"])
            count.grid(row=1 + r, column=c + 1, sticky="e", padx=(0, 40 if self.first else 24))
            # what the kind holds, on hover (over its tick box or its count)
            note = KIND_NOTES[key] + ("" if key == "obscene" else "\n" + KIND_NOTE_EXTRA)
            self.kind_tips[label] = [Tooltip(w, lambda e, t=note: t, font=font("body"), wrap=wrap) for w in (tick, count)]
            self.kind_ticks[label] = tick
        # the kinds of rude meaning, under Obscene words: shown while it is ticked (OB-5)
        box = self.rude_box = tk.Frame(f, bg=PALETTE["bg"])
        for i, k in enumerate(RUDE_KINDS):
            r, c = (i, 0) if self.first else (i // 2, (i % 2) * 2)
            tick = ttk.Checkbutton(box, text=RUDE_LABELS[k], variable=self.rude_vs[k], takefocus=1)
            tick.grid(row=r, column=c, sticky="w", padx=(0, 18))
            count = ttk.Label(box, text=f"{counts[k]:,}", foreground=PALETTE["muted"])
            count.grid(row=r, column=c + 1, sticky="e", padx=(0, 40 if self.first else 24))
            note = KIND_NOTES[k] + "\n" + KIND_NOTE_RUDE
            self.kind_tips[RUDE_LABELS[k]] = [Tooltip(w, lambda e, t=note: t, font=font("body"), wrap=wrap)
                                              for w in (tick, count)]
            self.kind_ticks[RUDE_LABELS[k]] = tick
        self.box_row = box_row
        self.obscene_v.trace_add("write", lambda *_: self._show_rude())
        for v in self.rude_vs.values():
            v.trace_add("write", lambda *_: self._mark_obscene())
        self._show_rude(refit=False)
        note = "Point at a kind to see what it holds. Untick the rest to sort only obscene words."
        reading = self.app.rude_read_note()
        if reading:
            note += (f" The rude meanings are being read from Wiktionary in the background ({reading}); until then"
                     " a short list stands in.")
        wrap = self.dlg.wrap if self.first else font("body").measure("n") * 44
        ttk.Label(f, text=note, foreground=PALETTE["muted"], wraplength=wrap, justify="left").grid(
            row=10, column=0, columnspan=4, sticky="w", pady=(8, 0))
        return f

    def _show_rude(self, refit=True):
        """The kinds of rude meaning open under Obscene words while it is ticked."""
        if self.obscene_v.get():
            self.rude_box.grid(row=self.box_row, column=0, columnspan=4, sticky="w", padx=(24, 0), pady=(2, 0))
        else:
            self.rude_box.grid_remove()
        self._mark_obscene()
        if refit:
            self.dlg.refit()

    def _mark_obscene(self):
        """Obscene words shows a minus, as tick boxes do, while it is ticked but not every kind under it is."""
        def mark():         # (a moment later: the tick box's own trace, run after ours, clears "alternate" when its
                            # value changes, and refit() runs idle callbacks before that)
            partial = self.obscene_v.get() and not all(v.get() for v in self.rude_vs.values())
            tick = self.kind_ticks["Obscene words"]
            if tick.winfo_exists():
                tick.state(["alternate" if partial else "!alternate"])
        self.body.after(1, mark)

    def _censor(self):
        f = self._section("censor")
        ttk.Checkbutton(f, text="Censor obscene words", variable=self.censor_v, takefocus=1).grid(
            row=1, column=0, sticky="w")
        ttk.Label(f, text=CENSOR_NOTE, foreground=PALETTE["muted"]).grid(row=1, column=1, sticky="w", padx=(12, 0))
        ttk.Label(f, text=CENSOR_CAVEAT_LINE, foreground=PALETTE["muted"]).grid(row=2, column=0, columnspan=2,
                                                                               sticky="w", pady=(4, 0))
        # (ticked: the first time in a save a small dialog says why it may not be fully accurate, asked for)
        self.censor_v.trace_add("write", lambda *_: self.censor_v.get() and self.app.censor_note(self.dlg.win,
                                                                                                 toast=False))
        return f

    # ---- the first start, one step at a time ------------------------------------------------------------------
    def _show_step(self, i):
        self.step = i
        key = self.STEPS[i]
        for k, sec in self.sections.items():
            if k != key:
                sec.grid_remove()
        head, intro = self.HEADS[key]
        self.head_lbl.config(text=head)
        self.intro_lbl.config(text=intro)
        self.head_lbl.grid(row=0, column=0, sticky="w")
        self.intro_lbl.grid(row=1, column=0, sticky="w", pady=(8, 14))
        self.sections[key].grid(row=2, column=0, sticky="we")
        d = self.dlg
        d.clear_buttons()
        ttk.Label(d.button_row, text=f"Step {i + 1} of {len(self.STEPS)}", foreground=PALETTE["muted"]).pack(side="left")
        if i:
            d.button("Back", lambda: self._show_step(i - 1))
        last = i == len(self.STEPS) - 1
        d.button("Done" if last else "Next", self.apply if last else (lambda: self._next(i)), default=True)
        d.refit()

    def _next(self, i):
        if self.STEPS[i] == "order" and self._settings()[1]:
            self.say(self._settings()[1])
            return
        if self.STEPS[i] == "kinds" and not self._kinds_ticked():
            self.say("Tick at least one kind of word.")
            return
        self._show_step(i + 1)

    def _skip(self):
        """Closed on the first start: everything stays as it was (the defaults); not asked again."""
        if self.app.busy:
            return
        self.store.set_meta("dealt_asked", "1")
        self.dlg.close()
        if self.on_done:
            self.on_done()

    # ---- applying ---------------------------------------------------------------------------------------------
    def _kinds_ticked(self):
        return any(v.get() for v in self.kind_vs.values()) or self.obscene_v.get()

    def _settings(self):
        """(queue settings for Store.reshuffle, None) or (None, the problem)."""
        shuffled = self.order_v.get() == "shuffled"
        new, err = self.app.parse_queue_settings(self.seed_v.get(), self.spread_v.get(),
                                                 self.shape_v.get() if shuffled else "rank", self.comp_v.get())
        if err and not shuffled:            # (the shuffle's fields are hidden: what they held stays as it was)
            new, err = dict(self.start_cfg, shape="rank"), None
        return new, err

    def say(self, text, colour=None):
        self.status.config(text=text, foreground=colour or PALETTE["bad"][1])
        self.status.grid(row=8, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.dlg.refit()

    def apply(self):
        """Apply / Done: check the fields, save the censor tick at once, then reshuffle and / or re-deal if needed."""
        new, err = self._settings()
        if err:
            if self.first:
                self._show_step(0)
            self.say(err)
            return
        if not self._kinds_ticked():
            if self.first:
                self._show_step(1)
            self.say("Tick at least one kind of word.")
            return
        kinds = sum(bit for key, _, bit in KINDS if self.kind_vs[key].get())
        rude = sum(KIND_BITS[k] for k in RUDE_KINDS if self.rude_vs[k].get())
        deal = {"kinds": kinds, "obscene": self.obscene_v.get(), "rude": rude}
        reshuffle = not self.app.queue_unchanged(new)
        redeal = any(deal[k] != self.start_deal[k] for k in ("kinds", "obscene", "rude"))
        censor = self.censor_v.get()
        if censor != self.start_deal["censor"]:
            self.store.set_censor(censor)
        if self.first:
            self.store.set_meta("dealt_asked", "1")
        if not (reshuffle or redeal):
            if censor != self.start_deal["censor"] or self.first:
                self._finish(None)
            else:
                self.say("No settings changed.", PALETTE["muted"])
            return
        self._run(new if reshuffle else None, deal if redeal else None)

    def _run(self, cfg, deal):
        """Reshuffle and / or re-deal on a worker thread, with the moving bar; nothing else writes the save meanwhile."""
        app, d = self.app, self.dlg
        for b in (*d.buttons.values(), self.new_seed):
            b.set_enabled(False)
        d.on_cancel = lambda: None                   # it cannot be stopped halfway: wait for it
        self.say("Shuffling the words you haven't placed yet..." if cfg else "Dealing the words you chose...",
                 PALETTE["muted"])
        self.bar.grid(row=9, column=0, columnspan=2, sticky="we", pady=(6, 0))
        if not app.reduce_motion:
            self.bar.start(12)                       # the back-and-forth bar: no percentage to show
        d.refit()
        app.busy = True                              # nothing else writes to the save meanwhile (_poll_defs)
        gc.collect()                                 # tk objects may only be freed on this thread: tidy up now and
        gc.disable()                                 # pause the collector, so it never runs inside the worker
        result = {}

        def work():                                  # (no tkinter here)
            try:
                if deal is not None:
                    self.store.set_deal(**deal)
                if cfg is not None:
                    self.store.reshuffle(**cfg)
            except (sqlite3.Error, OSError, ValueError) as exc:
                result["error"] = str(exc)
        worker = threading.Thread(target=work, daemon=True)
        worker.start()

        def wait():
            if worker.is_alive():
                d.win.after(50, wait)
                return
            app.busy = False
            gc.enable()
            self.bar.stop()
            if result.get("error"):
                for b in (*d.buttons.values(), self.new_seed):
                    b.set_enabled(True)
                d.on_cancel = self._skip if self.first else d.close
                self.bar.grid_remove()
                self.say(f"Could not apply: {result['error']}")
                return
            self._finish("Queue reshuffled" if cfg else "Words dealt")
        wait()

    def _finish(self, message):
        app = self.app
        self.dlg.close()
        app.cmp = None
        app.after_external_change()
        if message and not self.first:
            app.flash(message, ms=2000)
        if self.on_done:
            self.on_done()

    # ---- for tests and the App ----------------------------------------------------------------------------------
    @property
    def buttons(self):
        return self.dlg.buttons

    def alive(self):
        return self.dlg.alive()

    def close(self):
        self.dlg.close()
