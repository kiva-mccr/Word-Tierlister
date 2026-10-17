"""The main window: place / refine / boundary / conflict modes, header menus, key handling, definitions pane.

App is a thin controller. It never touches the database directly: every read/write goes through
self.store (store.py), and after each change it calls refresh() to redraw. The file reads top to
bottom in the order things happen:
    construction (header, widgets) -> layout toggles -> refresh -> place mode -> pair modes ->
    undo -> keys -> definitions -> dialogs (anchors, queue, merge, export)
"""
import json
import math
import os
import random
import sqlite3
import time

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from browser import Browser
from errors import show_exception
from constants import DEFAULT_ANCHORS, FOCUS_ROUNDS, MODES, TIERS
from fonts import ROLES, init_fonts, font, scale_fonts
from saves import write_export
from sizing import center_geometry, fit_size, place_dialog, ui_factor, usable_area
from theme import PALETTE, TIER_COLORS, TIER_TEXT
from ui_motion import HURRY_MS, Animator
from ui_style import apply_ttk_style
from ui_chart import DistributionChart
from widgets import (AnchorLadder, ChoiceButton, DefinitionDrawer, DuelCards, HeaderMenus, RoundButton, TabBar, TierRow, Toast,
                     Tooltip, WordCard, refresh_widgets, watch_focus)


def format_stats(stats):
    """The status line (UI-15): one quiet line. Placed / total stays while the progress bar is on hold
    (UI-14); conflicts only appear when there are some."""
    pct = 100.0 * stats["placed"] / stats["total"] if stats["total"] else 0.0
    parts = [f"Placed {stats['placed']:,} of {stats['total']:,} ({pct:.1f}%)",
             f"{stats['total'] - stats['placed']:,} left",
             f"{stats['skipped']:,} skipped"]
    if stats["conflicts"]:
        parts.append(f"{stats['conflicts']:,} conflict{'s' if stats['conflicts'] != 1 else ''} to look at")
    return "   \u00b7   ".join(parts)


def local_midnight(now=None):
    """The start of today, local time, as a timestamp."""
    t = time.localtime(now if now is not None else time.time())
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))


class App:
    """The main window and the state of what is currently on screen.

    State (all in memory; anything that must survive a restart is saved through the Store):
        mode          "place" | "refine" | "boundary" | "conflict" (saved as meta "mode")
        cur_word      the word shown in place mode, or None when every word is placed
        cmp           anchor-comparison in progress, else None. A dict:
                      lo/hi = range of tiers still possible (binary search over the six anchors),
                      mid   = index of the anchor being asked about,
                      stack = (lo, hi, log length) snapshots so Back can undo one answer,
                      log   = [(anchor word, 'a'|'b'|'tie')] answers to save when the word is placed
        pair          the two words shown in a duel: {"left", "right", "ctx"}, or None
        focus         word being refined in a "Refine this word" session; focus_left = duels left
        session_count words handled since the window opened (shown muted in the header)
        mem_defs      definitions already fetched this run (def_words = words on screen now)
        browsers      open Browse windows, so they can be refreshed after a change
    Widgets: place view (word, tier buttons, compare row, action row) and pair view (two big
    buttons) are two frames in self.center; refresh() shows the one matching the mode.
    """

    def __init__(self, root, store, defs, note=None, other_saves=()):
        """Build the window. `note` is a one-time message (which save was resumed); `other_saves` are
        extra saves with progress that _startup() offers to merge. `defs` is a Definitions.
        """
        self.root, self.store, self.defs = root, store, defs
        self.note, self.other_saves = note, list(other_saves)
        self.mode = store.get_meta("mode", "place")
        if self.mode not in dict(MODES):
            self.mode = "place"
        self.show_defs = store.get_meta("show_defs", "0") == "1"
        self.auto_compare = store.get_meta("auto_compare", "0") == "1"
        self.reduce_motion = store.get_meta("reduce_motion", "0") == "1"
        self.anchors = store.get_anchors()
        self.cur_word = None
        self.cmp = None
        self.pair = None
        self.focus = None
        self.focus_left = 0
        self.session_count = 0
        self.session_start = time.time()
        self.mem_defs = {}
        self.def_words = []
        self.browsers = []
        self.font_scale = 1.0     # < 1 when the fonts had to shrink to fit a small screen (_fit_window)
        self.zoom = min(self.ZOOM_MAX, max(self.ZOOM_MIN, float(store.get_meta("zoom", "1") or 1)))
        self._chart_ready = False

        init_fonts(root)
        apply_ttk_style(root)
        root.title(f"Word Tier List  -  {store.path}")
        self.defs_var = tk.BooleanVar(value=self.show_defs)
        self.auto_var = tk.BooleanVar(value=self.auto_compare)
        self.motion_var = tk.BooleanVar(value=self.reduce_motion)
        self.anim = Animator(root, reduce_motion=self.reduce_motion)
        self.mode_var = tk.StringVar(value=self.mode)
        self.filter_var = tk.StringVar()
        self._build_header()
        self._build_ui()
        root.bind("<Key>", self.on_key)
        for seq in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            root.bind(seq, lambda e: self.set_zoom(self.zoom + self.ZOOM_STEP))
        for seq in ("<Control-minus>", "<Control-KP_Subtract>"):
            root.bind(seq, lambda e: self.set_zoom(self.zoom - self.ZOOM_STEP))
        for seq in ("<Control-0>", "<Control-KP_0>"):
            root.bind(seq, lambda e: self.set_zoom(1.0))
        watch_focus(root)                          # switching to another program closes open drop-downs (UI-43)
        root.bind("<Control-z>", lambda e: self.undo())
        root.bind("<Command-z>", lambda e: self.undo())
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._update_options()
        self._layout_defs()
        self.refresh()
        self._fit_window(initial=True)
        root.after(120, self._poll_defs)
        root.after(300, self._startup)

    def _startup(self):
        """One-time prompts after the window opens: which save was resumed, merge offers, anchors."""
        if self.note:
            self.flash(self.note, ms=12000)
        if self.other_saves:
            self.offer_merge(self.other_saves)
        if not all(self.anchors):
            self.edit_anchors()

    # ---- construction ------------------------------------------------------------------
    def _menu_items(self):
        """The header menus (UI-10): File (import/export), Edit (undo), View (browse, definitions, motion),
        Settings (anchors, queue). Each item is a DropMenu row: ("command", label, command, shortcut)
        or ("check", label, variable, command)."""
        return [
            ("File", [("command", "Import earlier progress...", self.import_progress, None),
                      ("command", "Export tier list...", self.export, None),
                      ("command", "Where is my save file?", self.show_save_location, None),
                      ("separator",),
                      ("command", "Quit", self.on_close, None)]),
            ("Edit", [("command", "Undo", self.undo, "Ctrl+Z")]),
            ("View", [("command", "Browse / edit tier list...", self.open_browser, None),
                      ("separator",),
                      ("command", "Zoom in", lambda: self.set_zoom(self.zoom + self.ZOOM_STEP), "Ctrl +"),
                      ("command", "Zoom out", lambda: self.set_zoom(self.zoom - self.ZOOM_STEP), "Ctrl \u2212"),
                      ("command", "Actual size", lambda: self.set_zoom(1.0), "Ctrl 0"),
                      ("separator",),
                      ("check", "Show definitions", self.defs_var, lambda: self.toggle_defs(self.defs_var.get())),
                      ("check", "Reduce motion", self.motion_var, self.toggle_motion)]),
            ("Settings", [("command", "Anchor words...", self.edit_anchors, None),
                          ("command", "Queue randomness & seed...", self.edit_queue, None),
                          ("check", "Always compare new words to anchors", self.auto_var, self.toggle_auto)]),
        ]

    def _build_header(self):
        """The top of the window (UI-10): a white bar with the File / Edit / View / Settings menu buttons,
        then the mode tabs on a hairline, the open tab joined to the page below. Replaces the system menu
        bar and the radio buttons.
        Alt+F / Alt+E / Alt+V / Alt+S (and F10 for File) open the menus from the keyboard."""
        r = self.root
        head = tk.Frame(r, bg=PALETTE["surface"])
        head.pack(side="top", fill="x")
        bar = tk.Frame(head, bg=PALETTE["surface"], padx=8, pady=5)
        bar.pack(side="top", fill="x")
        self.header = HeaderMenus(bar, self._menu_items(), font("body"), animator=self.anim)
        self.header.pack(side="left")
        for name in self.header.buttons:
            r.bind(f"<Alt-{name[0].lower()}>", lambda e, n=name: self._open_menu_key(n))
        r.bind("<F10>", lambda e: self._open_menu_key("File"))
        # the mode tabs sit on the line that is the top edge of the page
        self.mode_switch = TabBar(head, MODES, self._on_mode_switch, font("label"), animator=self.anim,
                                  page_bg=PALETTE["bg"])
        self.mode_switch.set(self.mode)
        self.mode_switch.pack(side="top", fill="x")
        tk.Frame(r, height=6, bg=PALETTE["bg"]).pack(side="top", fill="x")

    def _open_menu_key(self, name):
        self.header.open_menu(name)
        return "break"

    def _on_mode_switch(self, key):
        """A segment of the mode switch was clicked."""
        self.mode_var.set(key)
        self.on_mode_change()

    def _build_ui(self):
        """Create every widget below the header once: stats, toast, bottom bar, definition pane, place view
        and pair view."""
        r = self.root
        # the status band: the numbers on the left, the tier chart (UI-13) on the right
        band = self.status_band = ttk.Frame(r, padding=(10, 2, 10, 0))
        band.pack(side="top", fill="x")
        self.stats_lbl = ttk.Label(band, anchor="w")
        self.stats_lbl.pack(side="left", anchor="n", pady=(4, 0))
        # "+N today", small and muted; the pace only in a hover note (UI-15: no pressure on screen)
        self.today_lbl = ttk.Label(band, anchor="w", foreground=PALETTE["muted"])
        self.today_lbl.pack(side="left", anchor="n", pady=(4, 0), padx=(14, 0))
        self.today_tip = Tooltip(self.today_lbl, lambda e: self._pace_text(), font=font("body"))
        self.chart = DistributionChart(band, TIERS, font("body"), font("head"), animator=self.anim)
        self.chart.pack(side="right")


        # bottom bar first so it keeps the bottom edge
        bottom = ttk.Frame(r, padding=(10, 6))
        bottom.pack(side="bottom", fill="x")
        ttk.Button(bottom, text="Undo", command=self.undo, takefocus=0).pack(side="left")
        ttk.Button(bottom, text="Browse / edit...", command=self.open_browser, takefocus=0).pack(side="left", padx=6)
        ttk.Button(bottom, text="Definition (D)", command=lambda: self.toggle_defs(), takefocus=0).pack(side="left")
        self.hint_lbl = ttk.Label(bottom, foreground=PALETTE["muted"], justify="right", wraplength=560)
        self.hint_lbl.pack(side="right")

        self.def_frame = DefinitionDrawer(r, {"body": font("body"), "head": font("head")}, animator=self.anim)
        self.def_text = self.def_frame.text

        self.center = ttk.Frame(r)
        self.center.pack(side="top", fill="both", expand=True)
        # messages float over the page as toasts (UI-11); each message is its own Toast (see _new_toast)
        self.toasts = [Toast(r, font("label"), animator=self.anim, on_gone=self._toast_gone)]

        # ---- place view
        self.place_frame = ttk.Frame(self.center)
        inner = ttk.Frame(self.place_frame)
        self.place_inner = inner
        inner.place(relx=0.5, rely=0.5, anchor="center")
        self.word_card = WordCard(inner, font("word"), font("body"))
        self.word_card.grid(row=0, column=0, pady=(0, 22))      # breathing room above the tier pills
        self.ladder = AnchorLadder(inner, TIERS, font("head"), animator=self.anim)
        self.ladder.grid(row=1, column=0)
        self.ladder.grid_remove()               # only while comparing to anchors (UI-9)
        self.vs_lbl = ttk.Label(inner, text="", font=font("vs"), justify="center")
        self.vs_lbl.grid(row=2, column=0, pady=14)

        self.tier_row = TierRow(inner, TIERS, self.place_word, font=font("tier"), animator=self.anim)
        self.tier_row.grid(row=3, column=0, pady=6)
        self.tier_btns = self.tier_row.buttons

        self.cmp_row = ttk.Frame(inner)
        self.cmp_row.grid(row=4, column=0, pady=6)
        self.cmp_btns = {}
        for col, (text, hint, ans, key) in enumerate((("Better", "Up / B", "better", "better"),
                                                      ("Same tier", "E", "same", "same"),
                                                      ("Worse", "Down / W", "worse", "worse"))):
            b = RoundButton(self.cmp_row, text, lambda ans=ans: self.cmp_answer(ans), bg=PALETTE[key],
                            font=font("choice"), padx=22, pady=12, hint=hint, animator=self.anim)
            b.grid(row=0, column=col, padx=8)
            self.cmp_btns[ans] = b
        self.cmp_btns["back"] = RoundButton(self.cmp_row, "Back", self.cmp_back, font=font("body"), padx=14, pady=8,
                                            hint="Bksp", animator=self.anim)
        self.cmp_btns["back"].grid(row=0, column=3, padx=(24, 0))

        self.act_row = ttk.Frame(inner)
        self.act_row.grid(row=5, column=0, pady=(16, 0))
        self.compare_btn = RoundButton(self.act_row, "Compare to anchors", self.start_compare,
                                       bg=PALETTE["left"], font=font("label"), hint="Space", animator=self.anim)
        self.compare_btn.grid(row=0, column=0, padx=8)
        self.later_btn = RoundButton(self.act_row, "Don't know / later", self.skip_word, bg=PALETTE["neutral"],
                                     font=font("label"), hint="U", animator=self.anim)
        self.later_btn.grid(row=0, column=1, padx=8)

        # ---- pair view
        self.pair_frame = ttk.Frame(self.center)
        pi = ttk.Frame(self.pair_frame)
        self.pair_inner = pi
        pi.place(relx=0.5, rely=0.5, anchor="center")
        # Refine / Boundary: which tier or boundary to work on, right above the duel it affects (so the page
        # area is the same in every tab and the content does not jump when switching)
        self.opt_frame = ttk.Frame(pi)
        self.opt_frame.grid(row=0, column=0, pady=(0, 16))
        self.opt_label = ttk.Label(self.opt_frame, text="Tier:", foreground=PALETTE["muted"])
        self.opt_label.pack(side="left")
        self.filter_cb = ChoiceButton(self.opt_frame, self.filter_var, ["All tiers"], on_change=self._on_filter,
                                      font=font("body"), animator=self.anim)
        self.filter_cb.pack(side="left", padx=6)
        self.focus_lbl = ttk.Label(self.opt_frame, text="")
        self.focus_lbl.pack(side="left", padx=12)
        self.focus_clear = ttk.Button(self.opt_frame, text="Clear focus", command=self.clear_focus, takefocus=0)
        self.opt_frame.grid_remove()
        self.pair_title = ttk.Label(pi, text="Which word is better?", font=font("title"))
        self.pair_title.grid(row=1, column=0, pady=(0, 12))
        self.duel = DuelCards(pi, self._on_duel, font("pair"), font("body"), animator=self.anim)
        self.duel.grid(row=2, column=0, sticky="nsew")
        self.left_btn, self.right_btn = self.duel.left, self.duel.right
        self.tie_btn, self.skip_pair_btn = self.duel.tie, self.duel.skip
        self.ctx_lbl = ttk.Label(pi, text="", foreground=PALETTE["muted"], wraplength=720, justify="center")
        self.ctx_lbl.grid(row=3, column=0, pady=(10, 0))
        self.center.bind("<Configure>", self._on_center_configure)

    # ---- zoom (View menu, Ctrl + / Ctrl - / Ctrl 0) ---------------------------------------------------------
    ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.6, 2.0, 0.1

    def set_zoom(self, z):
        """Make everything in the main window bigger or smaller (every shared font scales, so buttons, cards,
        the chart and the menus follow). Saved. The window grows if it has to; it never goes past the screen
        (the fitting step shrinks the fonts back if a zoom would not fit)."""
        z = round(min(self.ZOOM_MAX, max(self.ZOOM_MIN, z)), 2)
        if z == self.zoom:
            return "break"
        self.zoom = z
        self.store.set_meta("zoom", z)
        self.font_scale = 1.0                  # re-fit from the full size at the new zoom
        self._fit_window()
        self.flash(f"Zoom {round(z * 100)}%", bg=PALETTE["info"][0], fg=PALETTE["info"][1], ms=900)
        return "break"

    # ---- window size: fits the screen and the contents ------------------------------------------
    FONT_STEPS = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5)   # tried in order until the contents fit the screen
    BASE_SIZE = (1040, 760)                  # preferred window size at the classic 96 dpi
    MIN_SIZE = (780, 580)                    # never smaller than this (also at 96 dpi)

    def _apply_wraps(self, center_w):
        """Let long words wrap instead of running off the window (word, duel buttons, context line)."""
        f = ui_factor(self.root)       # paddings are fixed pixels: they do not shrink with the fonts
        self.word_card.config(wraplength=max(200, center_w - int(80 * f) - 2 * self.word_card.padx))
        side = max(150, (center_w - int(220 * f)) // 2)
        self.left_btn.config(wraplength=side)
        self.right_btn.config(wraplength=side)
        self.ctx_lbl.config(wraplength=max(300, center_w - int(80 * f)))

    def _on_center_configure(self, e):
        """The centre area was resized: re-wrap and re-fit the big words."""
        self._apply_wraps(e.width)
        self._fit_big_text()
        self._recenter()

    def _recenter(self):
        """Centre the content in the visible page (from the tab line down to the bottom bar), not just in the
        area under the status line: it moves up by half the status line's height, but only as far as the
        free space allows, so it never runs into the stats on a small window."""
        band = self.status_band.winfo_height()
        ch = self.center.winfo_height()
        for inner in (self.place_inner, self.pair_inner):
            free = (ch - inner.winfo_reqheight()) / 2
            inner.place_configure(y=-int(max(0, min(band / 2, free))))

    def _fit_big_text(self):
        """Shrink the big word(s) so a long one still fits on a line (down to about a third, then it wraps).

        Short words keep the normal size. The shared role fonts are used only by these labels, so
        resizing them here affects nothing else.
        """
        width = self.center.winfo_width()
        if width < 50:                         # not laid out yet
            return
        f = ui_factor(self.root)
        for role, texts, avail in (
                ("word", [self.word_card.word], width - int(80 * f) - 2 * self.word_card.padx),
                ("pair", [self.left_btn.cget("text"), self.right_btn.cget("text")],
                 (width - int(220 * f)) // 2 - int(80 * f))):
            base = max(7, int(round(ROLES[role][0] * self.font_scale * self.zoom)))
            fnt = font(role)
            fnt.configure(size=base)
            need = max((fnt.measure(t) for t in texts if t), default=0)
            if need > avail > 0:
                fnt.configure(size=max(7, int(base * 0.35), int(base * avail / need)))
        refresh_widgets(self.center)           # the word card and duel cards follow the (possibly shrunk) fonts

    def _content_size(self):
        """(width, height) the window needs to show everything without clipping, in pixels.

        Fixed rows (header, stats, bottom bar, definition pane when shown) report their own size; the
        centre area uses `place`, which does not report one, so the two views' inner frames are
        measured and given some breathing room.
        """
        r = self.root
        r.update_idletasks()
        f = ui_factor(r) * self.font_scale * self.zoom
        rows = [w for w in r.pack_slaves() if w is not self.center]
        extra = 0 if self.opt_frame.winfo_manager() else self.opt_frame.winfo_reqheight() + 16  # refine/boundary row
        inner_w = max(self.place_inner.winfo_reqwidth(), self.pair_inner.winfo_reqwidth())
        inner_h = max(self.place_inner.winfo_reqheight(), self.pair_inner.winfo_reqheight() + extra)
        width = max([w.winfo_reqwidth() for w in rows] + [inner_w + int(60 * f)])
        height = sum(w.winfo_reqheight() for w in rows) + inner_h + int(50 * f)
        return width, height

    def _fit_window(self, initial=False):
        """Size and place the main window for this screen and these contents.

        First call: if the contents cannot fit the screen even at the right size, the fonts are
        shrunk step by step (FONT_STEPS) until they do; then the window opens at the preferred size
        (BASE_SIZE scaled for dpi), at least as big as the contents need, no bigger than the usable
        screen, centred. Later calls (mode or definition pane changed) only grow it if the contents
        now need more room. The minimum size always follows the contents.
        """
        r = self.root
        f = ui_factor(r)
        area = usable_area(r)
        if initial:
            self.font_scale = 1.0
        # Make the contents fit the usable area: first shorten the definition pane (down to 3 lines),
        # then take the next font step down, and repeat. Later calls never grow the fonts back.
        steps = [st for st in self.FONT_STEPS if st <= self.font_scale + 1e-9]
        for step in steps:
            self.font_scale = step
            scale_fonts(step * self.zoom)
            self._apply_wraps(area[2])
            refresh_widgets(self.root)
            for lines in (range(9, 2, -1) if self.show_defs else (9,)):
                self.def_text.config(height=lines)
                cw, ch = self._content_size()
                if cw <= area[2] and ch <= area[3]:
                    break
            else:
                continue
            break
        if not self.show_defs and int(self.def_text.cget("height")) != 9:
            self.def_text.config(height=9)
        r.update_idletasks()
        self._fit_big_text()                   # fonts may have changed even if the window size did not
        fs = self.font_scale * self.zoom
        min_w = min(max(cw, int(self.MIN_SIZE[0] * f * fs)), area[2])
        min_h = min(max(ch, int(self.MIN_SIZE[1] * f * fs)), area[3])
        r.minsize(min_w, min_h)
        if initial:
            pref = (int(self.BASE_SIZE[0] * f * fs), int(self.BASE_SIZE[1] * f * fs))
            w, h = fit_size((min_w, min_h), pref, (area[2], area[3]))
            r.geometry(center_geometry(w, h, area))
        else:
            r.update_idletasks()
            w, h = max(r.winfo_width(), min_w), max(r.winfo_height(), min_h)
            if (w, h) != (r.winfo_width(), r.winfo_height()):
                r.geometry(f"{w}x{h}")

    # ---- layout toggles -------------------------------------------------------------------------------
    def _layout_defs(self, animate=False):
        """Show or hide the definition drawer to match self.show_defs (easing open / shut when `animate`)."""
        d = self.def_frame
        d.settle()
        if animate and self.show_defs == d.is_open:      # no change: nothing to animate
            animate = False
        if self.show_defs:
            if not animate:
                d.set_open(True)
            d.pack(side="bottom", fill="x", padx=10, pady=(0, 6), before=self.center)
            self._render_defs()
            if animate:
                self._fit_window()             # size for the open drawer first, then ease it open
                d.open()
        elif d.winfo_manager():
            if animate:
                d.close(on_closed=lambda: not self.show_defs and d.pack_forget())
            else:
                d.set_open(False)
                d.pack_forget()

    def toggle_defs(self, value=None):
        """Show/hide definitions (D key, menu, button). `value` forces on/off; the choice is saved."""
        self.show_defs = (not self.show_defs) if value is None else bool(value)
        self.defs_var.set(self.show_defs)
        self.store.set_meta("show_defs", int(self.show_defs))
        was_open = self.def_frame.is_open
        self._layout_defs(animate=True)
        if not self.show_defs or was_open:
            self._fit_window()

    def toggle_motion(self):
        """View > Reduce motion: turn animations off (they jump to their end state). Saved."""
        self.reduce_motion = self.motion_var.get()
        self.anim.reduce_motion = self.reduce_motion
        self.anim.finish_all()
        self.store.set_meta("reduce_motion", int(self.reduce_motion))

    def toggle_auto(self):
        """'Always compare new words to anchors' menu switch (saved); restarts any comparison."""
        self.auto_compare = self.auto_var.get()
        self.store.set_meta("auto_compare", int(self.auto_compare))
        self.cmp = None
        self.refresh()

    def _update_options(self):
        """Show the tier / boundary drop-down for refine and boundary modes, hide it otherwise."""
        if self.mode == "refine":
            self.opt_label.config(text="Tier:")
            self.filter_cb.set_values(["All tiers"] + TIERS)
            self.filter_var.set("All tiers")
            self.opt_frame.grid()
        elif self.mode == "boundary":
            self.opt_label.config(text="Boundary:")
            vals = [f"{TIERS[i]} | {TIERS[i + 1]}" for i in range(len(TIERS) - 1)]
            self.filter_cb.set_values(["All boundaries"] + vals)
            self.filter_var.set("All boundaries")
            self.opt_frame.grid()
        else:
            self.opt_frame.grid_remove()
        self._update_focus_label()

    def _update_focus_label(self):
        """Show 'Focus: word (N duels left)' and the Clear button while a refine session is running."""
        if self.mode == "refine" and self.focus:
            self.focus_lbl.config(text=f"Focus: {self.focus} ({self.focus_left} duels left)")
            self.focus_clear.pack(side="left")
        else:
            self.focus_lbl.config(text="")
            self.focus_clear.pack_forget()

    def _on_filter(self):
        """A tier/boundary was picked in the drop-down: drop any focus word and load a new pair."""
        self.focus = None
        self.refresh()

    @property
    def toast(self):
        """The newest message (the one on top)."""
        return self.toasts[-1]

    def _new_toast(self):
        """A fresh Toast for a new message, on top; the older ones still showing speed out of the way
        underneath (hurry), so fast sorting never piles messages up or cuts one off mid-air."""
        for t in list(self.toasts):
            if t.cget("text"):
                t.hurry()
            else:                                   # already gone (it was the newest when it went)
                self.toasts.remove(t)
                t.destroy()
        t = Toast(self.root, font("label"), animator=self.anim, on_gone=self._toast_gone)
        self.toasts.append(t)
        return t

    def _toast_gone(self, t):
        if t is not self.toasts[-1] and t in self.toasts:     # the newest stays (hidden) for the next message
            self.toasts.remove(t)
            t.destroy()

    def flash(self, text, bg=PALETTE["ok"][0], fg=PALETTE["ok"][1], ms=3500):
        """Show a message in the toast (a pill coloured bg / fg) for `ms` milliseconds. A new message
        replaces the old one."""
        self._new_toast().show(text, (bg, fg), ms, in_=self.center,
                         wraplength=max(240, self.center.winfo_width() - 120))

    # ---- refresh ----------------------------------------------------------------------------------------
    def refresh(self):
        """Redraw everything from the Store: header numbers, then the place view or the pair view."""
        self._update_stats()
        self._update_focus_label()
        if self.mode == "place":
            self._show_place()
        else:
            self._show_pair()
        self.root.after_idle(self._recenter)     # the content's height may have changed

    def after_external_change(self):
        """Call after something outside the normal flow changed the save (Browse edits, merge, anchors)."""
        self.cmp = None
        self.refresh()

    def _update_stats(self):
        """Status band: one quiet line (format_stats), "+N today", and the tier chart."""
        s = self.store.stats()
        self.stats_lbl.config(text=format_stats(s))
        self.today_lbl.config(text=f"+{self.store.actions_since(local_midnight()):,} today")
        # the tier chart belongs to Place new words; the other tabs get their own views later (UI-31)
        # (it keeps its space in the other tabs, so the page does not move when switching)
        if self.mode == "place":
            self.chart.set([s["tiers"].get(t, 0) for t in range(len(TIERS))], animate=self._chart_ready)
            self._chart_ready = True             # the first fill does not grow from zero
            self.chart.show(True)
        elif self.chart.shown:
            self.chart.show(False)
            self._chart_ready = False            # back in Place it shows the counts as they are, no growth

    def _pace_text(self):
        """The hover note on "+N today": this session's pace, once there is enough to say anything."""
        hours = (time.time() - self.session_start) / 3600.0
        if self.session_count < 5 or hours <= 0:
            return "Words and duels done today"
        return (f"Words and duels done today. This session: {self.session_count:,}, "
                f"about {self.session_count / hours:,.0f} an hour")

    def _hint(self):
        """Bottom-right key reminder: only the keys no button on screen already shows. The tier pills,
        compare / don't-know buttons, Better / Same / Worse / Back, the duel cards and Tie / Skip carry
        their own key hints, and the Definition (D) button names its key."""
        if self.mode == "place" and self.cmp:
            h = "Esc cancel"
        else:
            h = "Backspace or Ctrl+Z undo"
        self.hint_lbl.config(text=h)

    # ---- place mode ------------------------------------------------------------------------------------------
    def _show_place(self):
        """Place view: show the next unplaced word (or the 'all placed' message) and set up its buttons."""
        self.pair_frame.pack_forget()
        self.place_frame.pack(fill="both", expand=True)
        row = self.store.next_unplaced()
        if row is None:
            self.cur_word = None
            self.word_card.set("All words placed", "Switch to Refine / Boundary to keep improving the ranking.")
            self._set_question("")
            self.tier_row.grid_remove()
            self.cmp_row.grid_remove()
            self.act_row.grid_remove()
            self._render_defs([])
            self._hint()
            return
        self.cur_word = row["word"]
        notes = (" - revisiting a word you skipped" if row["skips"] > 0 else "") + \
                (" - compound word" if row["pen"] else "")
        self.word_card.set(row["word"], f"frequency rank #{row['rank'] + 1:,}{notes}")
        self._fit_big_text()
        anchors_ok = all(self.anchors)
        self.compare_btn.set_enabled(anchors_ok)
        if self.cmp is None and self.auto_compare and anchors_ok:
            self.cmp = {"lo": 0, "hi": len(TIERS) - 1, "stack": [], "log": [], "mid": None}
            self._cmp_step()
        else:
            self._render_place_state()
        self._render_defs([row["word"]])

    def _render_place_state(self):
        """Switch the place view between its three states: tier buttons, anchor question, or 'set anchors'."""
        if self.cmp:
            mid = self.cmp["mid"]
            anchor = self.anchors[mid]
            self._set_question(f"Is it better or worse than  \"{anchor}\"  ?\n(anchor for tier {TIERS[mid]})")
            self.tier_row.grid_remove()
            self.act_row.grid_remove()
            self.cmp_row.grid()
            if not self.ladder.winfo_manager():                     # not shown yet
                self.ladder.update_range(0, len(TIERS) - 1, None)   # a fresh comparison starts full
            self.ladder.grid()
            self.ladder.update_range(self.cmp["lo"], self.cmp["hi"], mid)
        else:
            self.ladder.grid_remove()
            self._set_question("" if all(self.anchors) else "Set anchor words (Settings) to enable comparing.")
            self.cmp_row.grid_remove()
            self.tier_row.grid()
            self.act_row.grid()
        self._hint()

    def _set_question(self, text):
        """The line under the card (the anchor question); hidden when empty so it leaves no gap."""
        self.vs_lbl.config(text=text)
        if text:
            self.vs_lbl.grid()
        else:
            self.vs_lbl.grid_remove()

    def place_word(self, tier):
        """Put the current word straight into `tier` (keys 1-6 or the tier buttons)."""
        if not self.cur_word or self.cmp:
            return
        word = self.cur_word
        self.store.place(word, tier)
        self._after_place(word, tier)

    def skip_word(self):
        """'Don't know / later': move the current word behind every fresh word."""
        if not self.cur_word or self.cmp:
            return
        word = self.cur_word
        self.store.skip(word)
        self.session_count += 1
        old_sub = self.word_card.sub
        self.flash(f"'{word}' moved to the back of the queue", bg=PALETTE["info"][0], fg=PALETTE["info"][1], ms=1800)
        self.refresh()
        f = ui_factor(self.root)               # "later": it drifts back (up and away) instead of toward a tier
        self.word_card.transition_from(word, old_sub, dx=0, dy=-int(10 * f), animator=self.anim)

    def _after_place(self, word, tier):
        """Shared tail of every placement: count it, show the next word (the old one nudges toward its tier
        and fades, UI-16), confirm in the toast."""
        self.session_count += 1
        self.cmp = None
        old_sub = self.word_card.sub
        self.refresh()
        f = ui_factor(self.root)
        self.word_card.transition_from(word, old_sub, dx=int((tier - 2.5) * 5 * f), dy=int(12 * f),
                                       animator=self.anim)
        self._fling_toast(f"{word}  \u2192  {TIERS[tier]}", tier)

    def _fling_toast(self, text, tier):
        """The placement message rises out of the word card's top edge, rests above it, then flies into its
        tier's bar in the chart, fading as it goes, and the bar pulses (UI-11, UI-17)."""
        card, c, ch = self.word_card, self.center, self.chart
        if not (card.winfo_ismapped() and ch.shown and ch.winfo_ismapped()):
            self.flash(text, bg=TIER_COLORS[tier], fg=TIER_TEXT, ms=1500)
            return
        f = ui_factor(self.root)
        card_top = card.winfo_rooty() - c.winfo_rooty()
        card_bottom = card_top + card.winfo_height() - WordCard.SHADOW
        bx, by = ch.bar_top(tier)

        def under(y):          # the card is white, the page around it cream
            return PALETTE["surface"] if card_top + 2 < y < card_bottom - 2 else PALETTE["bg"]
        # it starts at the card's top edge: over the word itself it would hide the letters (the toast is an
        # opaque canvas; tk has no transparency)
        self._new_toast().fling(text, (TIER_COLORS[tier], TIER_TEXT), start_mid=card_top + int(14 * f),
                          rest_bottom=card_top - int(8 * f),
                          target=(bx - (c.winfo_rootx() + c.winfo_width() / 2), by - c.winfo_rooty()),
                          in_=c, wraplength=max(240, c.winfo_width() - 120), under=under,
                          on_arrive=lambda: ch.pulse(tier))

    def start_compare(self):
        """Begin placing the current word by comparing it to anchors (a binary search over the six tiers)."""
        if not self.cur_word or self.mode != "place" or self.cmp:
            return
        if not all(self.anchors):
            self.flash("Set all six anchor words first (Settings > Anchor words...)", bg=PALETTE["warn"][0], fg=PALETTE["warn"][1])
            return
        self.cmp = {"lo": 0, "hi": len(TIERS) - 1, "stack": [], "log": [], "mid": None}
        self._cmp_step()

    def _cmp_step(self):
        """Ask about the middle anchor of the remaining tier range, or finish if the range is empty."""
        c = self.cmp
        if c["lo"] > c["hi"]:
            # Fell between two anchors: the lower of the two tiers (duels will refine it).
            self._cmp_finish(min(max(c["lo"], 0), len(TIERS) - 1))
            return
        c["mid"] = (c["lo"] + c["hi"]) // 2
        self._render_place_state()

    def cmp_answer(self, ans):
        """Handle Better / Worse / Same for the current anchor: 'same' places the word in that tier;
        better/worse halves the range (better = toward S = lower tier index).
        """
        c = self.cmp
        if not c:
            return
        mid = c["mid"]
        c["stack"].append((c["lo"], c["hi"], len(c["log"])))
        c["log"].append((self.anchors[mid], {"better": "a", "worse": "b", "same": "tie"}[ans]))
        if ans == "same":
            self._cmp_finish(mid)
            return
        if ans == "better":
            c["hi"] = mid - 1
        else:
            c["lo"] = mid + 1
        self._cmp_step()

    def _cmp_finish(self, tier):
        """Place the word in `tier` and save the anchor answers as comparisons (they feed conflict detection)."""
        word, log = self.cur_word, self.cmp["log"]
        self.cmp = None
        self.store.place(word, tier, comps=log)
        self._after_place(word, tier)

    def cmp_back(self):
        """Undo the last anchor answer, or leave the comparison if no answers are left."""
        c = self.cmp
        if not c:
            return
        if c["stack"]:
            lo, hi, n = c["stack"].pop()
            c["lo"], c["hi"] = lo, hi
            del c["log"][n:]
            self._cmp_step()
        else:
            self.cmp = None
            self._render_place_state()

    # ---- pair modes -----------------------------------------------------------------------------------------------
    def _pick_pair(self):
        """Ask the Store for the next duel for the current mode. Returns {left, right, ctx} or None if there is none."""
        if self.mode == "refine":
            sel = self.filter_var.get()
            tier = TIERS.index(sel) if sel in TIERS else None
            res = self.store.pick_within(tier, self.focus)
            if not res:
                return None
            a, b, t = res
            ctx = f"Refining tier {TIERS[t]}"
            if self.focus:
                ctx += f"   -   focus word: {self.focus}"
        elif self.mode == "boundary":
            sel = self.filter_var.get()
            bnd = TIERS.index(sel.split("|")[0].strip()) if "|" in sel else None
            res = self.store.pick_boundary(bnd)
            if not res:
                return None
            a, b, t = res
            ctx = (f"Boundary {TIERS[t]} | {TIERS[t + 1]}: if you prefer the {TIERS[t + 1]}-tier word, "
                   f"the two swap tiers")
        else:
            res = self.store.pick_conflict()
            if not res:
                return None
            a, b = res
            ctx = "Conflict: your answers about this pair contradict each other. Decide again."
        pair = [a, b]
        random.shuffle(pair)  # avoid left/right position bias
        return {"left": pair[0], "right": pair[1], "ctx": ctx}

    def _show_pair(self):
        """Pair view: show the next duel, or a friendly message with the buttons disabled when none is available."""
        self.place_frame.pack_forget()
        self.pair_frame.pack(fill="both", expand=True)
        self.pair = self._pick_pair()
        if self.pair is None:
            msg = {
                "refine": "Nothing to refine yet: you need two words in the same tier "
                          "(or the focus word has faced all nearby words).",
                "boundary": "Nothing to compare yet: you need words in two neighbouring tiers.",
                "conflict": "No conflicts flagged. Nice and consistent.",
            }[self.mode]
            if self.focus:
                self.flash(f"No fresh opponents left for '{self.focus}'", bg=PALETTE["warn"][0], fg=PALETTE["warn"][1])
                self.focus = None
                self._update_focus_label()
            self.left_btn.config(text="-")
            self.right_btn.config(text="-")
            self.ctx_lbl.config(text=msg)
            self.duel.set_enabled(False)
            self._render_defs([])
        else:
            self.duel.show(self.pair["left"], self.pair["right"])
            self._fit_big_text()
            self.ctx_lbl.config(text=self.pair["ctx"])
            self._render_defs([self.pair["left"], self.pair["right"]])
        self._hint()

    def pair_answer(self, ans):
        """Record a duel result ('left' | 'right' | 'tie'), report swaps/conflicts, count down a focus session."""
        if not self.pair:
            return
        a, b = self.pair["left"], self.pair["right"]
        kind = {"refine": "within", "boundary": "boundary", "conflict": "conflict"}[self.mode]
        res = {"left": "a", "right": "b", "tie": "tie"}[ans]
        info = self.store.record_comparison(a, b, res, kind)
        self.session_count += 1
        if info["swapped"]:
            w, wt, l, lt = info["swapped"]
            self.flash(f"Swapped: {w} \u2192 {TIERS[wt]},  {l} \u2192 {TIERS[lt]}", bg=TIER_COLORS[wt], fg=TIER_TEXT)
        elif info["conflict"]:
            self.flash("Conflict: that contradicts earlier answers. Pair saved for review "
                       "(Resolve conflicts).", bg=PALETTE["alert"][0], fg=PALETTE["alert"][1], ms=5000)
        else:                                  # every duel answer gets its little message, not only swaps
            win, lose = (a, b) if ans != "right" else (b, a)
            tier = self.store.get_word(win)["tier"]
            tint = TIER_COLORS[tier] if tier is not None else PALETTE["info"][0]
            self.flash(f"{win}  {'=' if ans == 'tie' else '>'}  {lose}", bg=tint, fg=TIER_TEXT, ms=1400)
        if self.focus:
            self.focus_left -= 1
            if self.focus_left <= 0:
                self.flash(f"Finished refining '{self.focus}'", bg=PALETTE["ok"][0])
                self.focus = None
        self.pair = None                       # answered: nothing more to click until the next pair is up
        if ans in ("left", "right"):
            self.duel.resolve(ans, self.anim, self.refresh)    # winner lifts, loser dims, then the next pair
        else:
            self.refresh()

    def _on_duel(self, side):
        """A duel card or the Tie / Skip button was clicked (or pressed with its key)."""
        if side == "skip":
            self.skip_pair()
        else:
            self.pair_answer(side)

    def skip_pair(self):
        """Show a different pair without recording anything."""
        if self.pair:
            self.refresh()

    def start_focus(self, word):
        """Refine one word: switch to refine mode with `word` in every duel for FOCUS_ROUNDS rounds."""
        self.focus, self.focus_left = word, FOCUS_ROUNDS
        self.mode = "refine"
        self.mode_var.set("refine")
        self.mode_switch.set("refine")
        self.store.set_meta("mode", "refine")
        self.cmp = None
        self._update_options()
        self.refresh()
        self.root.lift()
        self.root.focus_force()

    def clear_focus(self):
        """End a focus session and go back to ordinary refine duels."""
        self.focus = None
        self.refresh()

    def on_mode_change(self):
        """The mode was switched (mode switch, or mode_var set by code): save it and reset any in-progress
        comparison, pair or focus."""
        self.mode = self.mode_var.get()
        self.mode_switch.set(self.mode)
        self.store.set_meta("mode", self.mode)
        self.cmp = None
        self.pair = None
        self.focus = None
        self._update_options()
        self.refresh()
        self._fit_window()

    # ---- undo ------------------------------------------------------------------------------------------------------------
    def undo(self):
        """Undo: step back inside an anchor comparison, otherwise revert the last saved action (survives restarts)."""
        if self.mode == "place" and self.cmp:
            self.cmp_back()
            return
        word = self.store.undo()
        if word is None:
            self.flash("Nothing to undo", bg=PALETTE["info"][0], fg=PALETTE["info"][1], ms=1500)
            return
        self.session_count = max(0, self.session_count - 1)
        self.cmp = None
        self.flash(f"Undid last action ({word})", bg=PALETTE["info"][0], fg=PALETTE["info"][1], ms=1800)
        self.refresh()

    # ---- keys --------------------------------------------------------------------------------------------------------------
    def on_key(self, e):
        """Every key press. D and Backspace work everywhere; the rest depends on mode and comparison state
        (see _hint for the full list of keys).
        """
        # a key press never waits for an animation: running ones speed out of the way (the new one starts on
        # top), except the duel result, which the next pair waits for
        self.anim.hurry_all(HURRY_MS, finish=(self.duel.anim_key,))
        ks = e.keysym
        if self.header.open_name is not None:      # a header menu is open: Escape closes it, nothing else runs
            if ks == "Escape":
                self.header.close()
            return
        low = ks.lower()
        if low == "d":
            self.toggle_defs()
            return
        if ks == "BackSpace" and not (self.mode == "place" and self.cmp):
            self.undo()
            return
        if self.mode == "place" and not self.cmp and ks == "Escape":
            return
        target = self._key_target(ks, low)
        if target is None:
            return
        button, action = target
        if button is not None and not button.enabled:
            return                                 # a greyed-out button's key is off too
        action()                                   # the action first: input is never delayed (UI-18) ...
        if button is not None:
            button.flash()                         # ... then the button it stands for dips (not when disabled,
                                                   # not with Reduce motion: RoundButton.flash checks both)

    def _key_target(self, ks, low):
        """The one key -> (button, action) map (UI-18), for the current view; None if the key does nothing here.
        Every hotkey that has a button on screen names it, so pressing the key looks like pressing it."""
        if self.mode == "place":
            if self.cmp:
                b = self.cmp_btns
                if ks == "Up" or low == "b":
                    return b["better"], lambda: self.cmp_answer("better")
                if ks == "Down" or low == "w":
                    return b["worse"], lambda: self.cmp_answer("worse")
                if low == "e" or ks in ("equal", "Return"):
                    return b["same"], lambda: self.cmp_answer("same")
                if ks == "BackSpace":
                    return b["back"], self.cmp_back
                if ks == "Escape":
                    return None, self._cancel_compare
                return None
            if ks in ("1", "2", "3", "4", "5", "6"):
                t = int(ks) - 1
                return self.tier_btns[t], lambda: self.place_word(t)
            if ks == "space":
                return self.compare_btn, self.start_compare
            if low == "u" or ks == "question":
                return self.later_btn, self.skip_word
            return None
        sides = {"Left": "left", "a": "left", "Right": "right", "l": "right", "Down": "tie", "t": "tie", "s": "skip"}
        side = sides.get(ks) or sides.get(low)
        if side is None:
            return None
        return self.duel.buttons[side], lambda: self._on_duel(side)

    def _cancel_compare(self):
        self.cmp = None
        self._render_place_state()

    # ---- definitions -----------------------------------------------------------------------------------------------------------
    def get_def(self, word):
        """Definition text if known (memory, then the save), else None and a lookup starts in the background."""
        if word in self.mem_defs:
            return self.mem_defs[word]
        text = self.defs.request(word)
        if text is not None:
            self.mem_defs[word] = text
        return text

    def _render_defs(self, words=None):
        """Redraw the definition pane for the words on screen (pass `words` to change which; no-op when hidden)."""
        if words is not None:
            self.def_words = words
        if not self.show_defs:
            return
        self.def_frame.show_words(self.def_words, self.get_def)

    def _poll_defs(self):
        """Every 120 ms: collect finished lookups, cache them in the save, and redraw the panes that show them."""
        changed = False
        for word, text, found in self.defs.drain():
            if found:
                self.store.set_def(word, text)
            self.mem_defs[word] = text
            changed = True
        if changed:
            self._render_defs()
            for bw in list(self.browsers):
                if bw.alive():
                    bw.render_def()
        self.root.after(120, self._poll_defs)

    # ---- dialogs / misc -------------------------------------------------------------------------------------------------------------
    def open_browser(self):
        """Open the Browse window, or raise it if one is already open."""
        for bw in self.browsers:
            if bw.alive():
                bw.win.lift()
                return
        Browser(self)

    def edit_anchors(self):
        """Dialog to choose the six anchor words (checked: filled in, distinct, and in the word list)."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Anchor words")
        dlg.transient(self.root)
        try:  # some Linux window managers refuse a grab before the window is visible
            dlg.wait_visibility()
            dlg.grab_set()
        except tk.TclError:
            pass
        intro = ("Pick one reference word per tier. New words are compared against these\n"
                 "to find their tier quickly. Choose words you know well that feel typical\n"
                 "of each tier. Edit freely; every word must be in the word list.")
        ttk.Label(dlg, text=intro, padding=12, justify="left").grid(row=0, column=0, columnspan=2)
        current = self.store.get_anchors()
        vars_ = []
        for t in range(len(TIERS)):
            pre = current[t] or (DEFAULT_ANCHORS[t] if self.store.has_word(DEFAULT_ANCHORS[t]) else "")
            tk.Label(dlg, text=TIERS[t], bg=TIER_COLORS[t], font=font("head"), width=3
                     ).grid(row=t + 1, column=0, padx=(12, 6), pady=3)
            v = tk.StringVar(value=pre)
            ttk.Entry(dlg, textvariable=v, width=26).grid(row=t + 1, column=1, padx=(0, 12), pady=3)
            vars_.append(v)

        def save():  # validate, store the anchors and close
            words = [v.get().strip().lower() for v in vars_]
            if any(not w for w in words):
                messagebox.showerror("Anchor words", "Fill in all six anchors.", parent=dlg)
                return
            if len(set(words)) != len(words):
                messagebox.showerror("Anchor words", "Anchors must be six different words.", parent=dlg)
                return
            for w in words:
                if not self.store.has_word(w):
                    messagebox.showerror("Anchor words", f"'{w}' is not in the word list.", parent=dlg)
                    return
            self.store.set_anchors(words)
            self.anchors = self.store.get_anchors()
            dlg.destroy()
            self.after_external_change()

        bar = ttk.Frame(dlg, padding=12)
        bar.grid(row=len(TIERS) + 1, column=0, columnspan=2)
        ttk.Button(bar, text="Save anchors", command=save).pack(side="left", padx=6)
        ttk.Button(bar, text="Cancel", command=dlg.destroy).pack(side="left")
        place_dialog(dlg, self.root)

    def apply_queue_settings(self, seed_text, spread_text, shape, compound_text):
        """Validate and apply the queue settings, then reshuffle. Returns an error message or None."""
        try:
            seed = int(seed_text.strip())
            spread = float(spread_text.strip().replace(",", ""))
            compound = float(compound_text.strip())
        except ValueError:
            return "Seed must be a whole number; spread and compound strength must be numbers."
        if spread < 100:
            return "Spread must be at least 100 (it is measured in frequency ranks)."
        if not 0 <= compound <= 10:
            return "Compound strength must be between 0 (off) and 10."
        if shape not in ("exp", "gauss"):
            return "Pick a shape."
        self.store.reshuffle(seed=seed, spread=spread, shape=shape, compound=compound)
        self.cmp = None
        return None

    def edit_queue(self):
        """Dialog for the queue's seed, spread, shape and compound strength; Apply reshuffles the unplaced words."""
        cfg = self.store.queue_settings()
        dlg = tk.Toplevel(self.root)
        dlg.title("Queue randomness")
        dlg.transient(self.root)
        try:
            dlg.wait_visibility()
            dlg.grab_set()
        except tk.TclError:
            pass
        intro = ("New words are drawn at random, but the odds fall off with how rare a word is: a word\n"
                 "'spread' ranks further down the frequency list is about 2.7x less likely to come up\n"
                 "early (exponential), or drops off faster still (gaussian). The same seed always\n"
                 "gives the same order. Applying reshuffles the words you haven't placed yet.")
        ttk.Label(dlg, text=intro, padding=12, justify="left").grid(row=0, column=0, columnspan=3)
        seed_v, spread_v = tk.StringVar(value=str(cfg["seed"])), tk.StringVar(value=f"{cfg['spread']:.0f}")
        comp_v, shape_v = tk.StringVar(value=f"{cfg['compound']:g}"), tk.StringVar(value=cfg["shape"])
        ttk.Label(dlg, text="Seed:").grid(row=1, column=0, sticky="e", padx=(12, 6), pady=3)
        ttk.Entry(dlg, textvariable=seed_v, width=14).grid(row=1, column=1, sticky="w")
        ttk.Button(dlg, text="New random seed",
                   command=lambda: seed_v.set(str(random.SystemRandom().randrange(1, 2 ** 31)))
                   ).grid(row=1, column=2, padx=12)
        ttk.Label(dlg, text="Spread (ranks):").grid(row=2, column=0, sticky="e", padx=(12, 6), pady=3)
        ttk.Entry(dlg, textvariable=spread_v, width=14).grid(row=2, column=1, sticky="w")
        info = ttk.Label(dlg, text="", foreground=PALETTE["muted"])
        info.grid(row=2, column=2, sticky="w", padx=12)
        ttk.Label(dlg, text="Shape:").grid(row=3, column=0, sticky="e", padx=(12, 6), pady=3)
        sh = ttk.Frame(dlg)
        sh.grid(row=3, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(sh, text="Exponential (e^-x)", value="exp", variable=shape_v).pack(side="left")
        ttk.Radiobutton(sh, text="Gaussian", value="gauss", variable=shape_v).pack(side="left", padx=12)
        ttk.Label(dlg, text="Compound strength:").grid(row=4, column=0, sticky="e", padx=(12, 6), pady=3)
        ttk.Entry(dlg, textvariable=comp_v, width=14).grid(row=4, column=1, sticky="w")
        ttk.Label(dlg, text="0 = treat compounds like any word, 1 = default, higher = rarer",
                  foreground=PALETTE["muted"]).grid(row=4, column=2, sticky="w", padx=12)
        status = ttk.Label(dlg, text="", foreground=PALETTE["bad"][1])
        status.grid(row=5, column=0, columnspan=3, pady=(6, 0))

        def update_info(*_):  # live hint under "Spread": the median rank of early words
            try:
                s = float(spread_v.get().replace(",", ""))
            except ValueError:
                info.config(text="")
                return
            med = s * math.log(2) if shape_v.get() == "exp" else s * 0.6745
            info.config(text=f"half of early words rank below ~{med:,.0f}")

        spread_v.trace_add("write", update_info)
        shape_v.trace_add("write", update_info)
        update_info()

        def apply():  # validate and reshuffle through apply_queue_settings()
            status.config(text="Shuffling...", foreground=PALETTE["muted"])
            dlg.update_idletasks()
            err = self.apply_queue_settings(seed_v.get(), spread_v.get(), shape_v.get(), comp_v.get())
            if err:
                status.config(text=err, foreground=PALETTE["bad"][1])
                return
            dlg.destroy()
            self.after_external_change()
            self.flash("Queue reshuffled", ms=2000)

        bar = ttk.Frame(dlg, padding=12)
        bar.grid(row=6, column=0, columnspan=3)
        ttk.Button(bar, text="Apply & reshuffle", command=apply).pack(side="left", padx=6)
        ttk.Button(bar, text="Cancel", command=dlg.destroy).pack(side="left")
        place_dialog(dlg, self.root)

    # ---- earlier progress ------------------------------------------------------------------------
    def show_save_location(self):
        """File > Where is my save file?"""
        messagebox.showinfo(
            "Save file",
            f"Your progress is saved automatically, after every action, in:\n\n{self.store.path}\n\n"
            "If you replace or move tierlist.py, this file is found and reused automatically. "
            "To back it up, copy it somewhere safe.", parent=self.root)

    @staticmethod
    def describe_merge(res):
        placed = f"{res['placed']:,} words placed"
        if res["added"]:
            placed += f" ({res['added']:,} of them were not in this list yet)"
        parts = [placed]
        if res["skipped"]:
            parts.append(f"{res['skipped']:,} skipped words")
        if res["comparisons"]:
            parts.append(f"{res['comparisons']:,} past duels")
        text = "Brought over " + ", ".join(parts) + "."
        if res["same"]:
            text += f"\n{res['same']:,} words were already placed the same way."
        if res["differs"]:
            text += f"\n{res['differs']:,} words were in a different tier here and were left as they are."
        if res["backup"]:
            text += f"\n\nA backup of this list from before the merge is at:\n{res['backup']}"
        return text

    def merge_file(self, path, backup=True):
        """Merge another save or export into this list. Returns (ok, message)."""
        name = os.path.basename(path)
        try:
            res = self.store.merge(path, backup=backup)
        except (ValueError, OSError, sqlite3.Error) as exc:
            return False, f"{name}: could not import ({exc})"
        self.cmp = None
        return True, f"{name}\n{self.describe_merge(res)}"

    def import_progress(self):
        """File > Import earlier progress: pick a save file or export and merge it in."""
        path = filedialog.askopenfilename(
            parent=self.root, title="Import earlier progress",
            filetypes=[("Tier list save or export", "*.db *.csv *.txt *.md"), ("All files", "*.*")])
        if not path:
            return
        ok, text = self.merge_file(path)
        (messagebox.showinfo if ok else messagebox.showerror)("Import earlier progress", text, parent=self.root)
        self.after_external_change()

    def offer_merge(self, others):
        """Other save files with progress were found: offer (once per file) to merge them in."""
        done = set(json.loads(self.store.get_meta("merge_prompted", "[]")))
        todo = [o for o in others if o["key"] not in done]
        if not todo:
            return
        lines = "\n".join(f"   {o['path']}   ({o['placed']:,} placed, {o['skipped']:,} skipped)" for o in todo)
        yes = messagebox.askyesno(
            "Merge your earlier progress?",
            f"Found other tier list save files with progress:\n\n{lines}\n\n"
            f"Merge their progress into the list you're using now?\n\n   {self.store.path}\n\n"
            "Nothing already placed here is overwritten, the other files are not changed, and a "
            "backup of this list is saved first. You can also do this later from "
            "File > Import earlier progress.", parent=self.root)
        self.store.set_meta("merge_prompted", json.dumps(sorted(done | {o["key"] for o in todo})))
        if not yes:
            self.flash("Not merged. You can do it any time from File > Import earlier progress...", ms=8000)
            return
        msgs = [self.merge_file(o["path"], backup=(i == 0))[1] for i, o in enumerate(todo)]
        self.after_external_change()
        messagebox.showinfo("Merged", "\n\n".join(msgs), parent=self.root)

    def export(self):
        """File > Export tier list: write the placed words (and skipped ones) to .txt, .csv or .md."""
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Export tier list", defaultextension=".txt", initialfile="tierlist.txt",
            filetypes=[("Text", "*.txt"), ("CSV", "*.csv"), ("Markdown", "*.md")])
        if not path:
            return
        rows = self.store.export_rows()
        try:
            write_export(path, rows, self.store.skipped_words())
        except OSError as exc:
            show_exception("Export failed", exc, self.root, f"The tier list could not be saved to\n{path}")
            return
        self.flash(f"Exported {len(rows):,} placed words", ms=3000)

    def on_close(self):
        """Close the save cleanly and quit."""
        self.anim.cancel_all()
        self.store.close()
        self.root.destroy()
