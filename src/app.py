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
import re
import sqlite3
import sys
import threading
import time
import webbrowser

import tkinter as tk
from tkinter import filedialog, ttk

import deps
import rudeness
from definitions import Online, wiktionary_url
import wordsource
from browser import Browser
from dealing import DealDialog
from errors import ask_yes_no, show_error, show_exception, show_message
from constants import (CENSOR_CAVEAT, CENSOR_CAVEAT_HEAD, CENSOR_CAVEAT_SHORT, DEFAULT_ANCHORS, FOCUS_ROUNDS, MODES,
                       QUEUE_SHAPES, RUDE_NAMES, TIERS, card_label, mask_word, typed_word)
from fonts import ROLES, init_fonts, font, scale_fonts
from keymap import Keymap, display, spec_of
from saves import app_dir, is_frozen, write_export
from shortcuts import ShortcutsDialog
from tiercolours import TierColoursDialog
from sources import SourceDialog
import standalone
from sizing import center_geometry, fit_size, is_maximized, ui_factor, usable_area
import theme
from theme import PALETTE, TIER_COLORS, TIER_TEXT
from ui_motion import HURRY_MS, Animator
from ui_style import apply_ttk_style
from filepicker import ask_export, ask_import, use_themed
from ui_chart import Bookshelf, ConflictCard, DistributionChart, SettledChart
from widgets import (AnchorLadder, ChoiceButton, DefinitionDrawer, EmptyCard, DuelCards, HeaderMenus, RoundButton, StyledDialog, TabBar, TierChip, TierRow, Toast,
                     Tooltip, WordCard, dialog_open, refresh_widgets, watch_focus)


SCRIPT_DIR = app_dir()          # where tierlist.py is, or a built program (T-1)


def format_stats(stats):
    """The status line (UI-15): one quiet line. Placed / total stays next to the progress bar (UI-14); "N left"
    went (UI-34: it repeats placed / total); conflicts only appear when there are some."""
    pct = 100.0 * stats["placed"] / stats["total"] if stats["total"] else 0.0
    parts = [f"Placed {stats['placed']:,} of {stats['total']:,} ({pct:.1f}%)",
             f"{stats['skipped']:,} skipped"]
    if stats["conflicts"]:
        parts.append(f"{stats['conflicts']:,} conflict{'s' if stats['conflicts'] != 1 else ''} to look at")
    return "   \u00b7   ".join(parts)


def local_midnight(now=None):
    """The start of today, local time, as a timestamp."""
    t = time.localtime(now if now is not None else time.time())
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))


def apply_look(store):
    """The look the save asks for (UI-61, UI-62): dark mode (meta dark_mode) and the tier colours (meta tier_colors,
    six #RRGGBB as JSON), applied to theme before a window is built."""
    try:
        tiers = json.loads(store.get_meta("tier_colors") or "null")
    except ValueError:
        tiers = None
    theme.apply(dark=store.get_meta("dark_mode") == "1", tiers=tiers if isinstance(tiers, list) else None)


def reopen_while_asked(app, store, defs, new_root):
    """After the window's event loop ended: while it ended to reopen (App.reopen: a new look), build the window again
    in that look on a new root (new_root() -> a hidden Tk with fonts and styles), with the save still open, while
    the old one is still on screen; the new one takes its place, size and state (App.take_over) and shows, and only
    then does the old one close, so the look changes in place instead of the window going away and coming back
    (reported: jarring). Returns the last App."""
    while app.reopening:
        old = app
        apply_look(store)
        root = new_root()
        tk._default_root = root                  # (anything made without a master belongs to the new window)
        app = App(root, store, defs)
        app.take_over(old)
        app.open_window()
        root.after(120, app._drop_old)           # (once the new one is drawn over it)
        root.mainloop()
    return app


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

    def __init__(self, root, store, defs, note=None, other_saves=(), ask_dealing=False, offer_form=False):
        """Build the window. `note` is a one-time message (which save was resumed); `other_saves` are
        extra saves with progress that _startup() offers to merge. `defs` is a Definitions. `ask_dealing`: show
        the first start's "How words are dealt" steps (ST-6; main() asks once per save). `offer_form`: offer the
        other form once (T-9: make a program from source, or unpack the source in the program; main() turns it off
        with --no-install, and tests leave it off).
        """
        self.root, self.store, self.defs = root, store, defs
        self.ask_dealing, self.offer_form = ask_dealing, offer_form
        self.note, self.other_saves = note, list(other_saves)
        self.mode = store.get_meta("mode", "place")
        if self.mode not in self.modes_with_work(store.stats()):
            self.mode = "place"              # unknown, or its tab is hidden (UI-46)
        self.show_defs = store.get_meta("show_defs", "0") == "1"
        self.auto_compare = store.get_meta("auto_compare", "0") == "1"
        self.reduce_motion = store.get_meta("reduce_motion", "0") == "1"
        self.keys = Keymap(store.get_meta("keymap"))      # every action's keys (UI-48)
        self._ws = root.tk.call("tk", "windowingsystem")
        self.cur_word = None
        self.looked_up = None        # a word looked up from the card (UI-51): shown until it is placed or skipped
        self._was_looked_up = None   # the last one placed or skipped: undoing that brings it back to the card
        self._to_add = None          # a word not in the list: Enter again adds it
        self.cmp = None
        self.pair = None
        self.focus = None
        self.focus_left = 0
        self.session_count = 0
        self.session_start = time.time()
        self._active_s = 0.0             # active time this session (UI-33: breaks over PACE_GAP_S do not count)
        self._last_action = self.session_start
        self.mem_defs = {}
        self.def_words = []
        self.def_lookup = None    # a word clicked in the definitions (W-1): the pane shows it until "Back" or the next word
        self.lookups = []         # words looked up so (W-1), shown in Browse for the moment, at the bottom
        self.browsers = []
        self.browse_state = None     # what the last Browse window showed when it closed (UI-38)
        self.online = Online().start()   # (the Wiktionary link on a definition shows only while it can be reached)
        self._was_online = False
        root.after(self.ONLINE_POLL_MS, self._watch_online)
        self.font_scale = 1.0     # < 1 when the fonts had to shrink to fit a small screen (_fit_window)
        self._room_from = None    # the window's height before it grew for the opening drawer (_make_room)
        self._center_w = None     # last width the centre area was fitted for (_on_center_configure)
        self._applied_scale = None  # font scale last applied (skip re-applying the same)
        self.grow = 1.0           # > 1 while the window is bigger than its preferred size (UI-25)
        self._ref_size = None     # the window size at which grow is 1 (set by _fit_window)
        self._grow_job = None
        self.busy = False         # True while a worker thread writes the save (the queue reshuffle)
        self._fit_cache = {}      # (layout, zoom, screen) -> the font step that fitted last time (_fit_window)
        self._def_want = self.DEF_LINES  # lines the definition pane asks for (raised to show every sense: UI-56)
        self._zoom_cap = {}       # layout -> the smallest zoom found not to fit there (a held Ctrl + stops trying)
        self.zoom = store.meta_number("zoom", 1.0, lo=self.ZOOM_MIN, hi=self.ZOOM_MAX)
        kept_max = self._max_zoom(store)
        if kept_max is not None and self.zoom > kept_max:    # (never bigger than when maximized: _keep_compatible)
            self.zoom = kept_max
            store.set_meta("zoom", self.zoom)
        self._maximized = False   # the window maximized: it shows the zoom kept for that ("zoom_max", UI-57)
        self._chart_ready = False
        self._settled_ready = False

        init_fonts(root)
        apply_ttk_style(root)
        root.title(f"Word Tier List  -  {store.path}")
        self.defs_var = tk.BooleanVar(value=self.show_defs)
        self.auto_var = tk.BooleanVar(value=self.auto_compare)
        self.motion_var = tk.BooleanVar(value=self.reduce_motion)
        self.censor_var = tk.BooleanVar(value=store.deal_settings()["censor"])
        self.dark_var = tk.BooleanVar(value=store.get_meta("dark_mode") == "1")
        self.anim = Animator(root, reduce_motion=self.reduce_motion)
        self.mode_var = tk.StringVar(value=self.mode)
        self.filter_var = tk.StringVar()
        self._build_header()
        self._build_ui()
        self.apply_keys()
        # every key goes through on_key and the keymap (UI-48), Ctrl ones too
        root.bind("<Key>", self.on_key)
        root.bind("<KeyRelease>", self.on_key_release)
        self._held = {}                            # keysym -> held-key state (_repeat_allowed)
        watch_focus(root)                          # switching to another program closes open drop-downs (UI-43)
        root.bind("<ButtonPress-1>", self._click_background, add="+")
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._update_options()
        self._layout_defs()
        self.refresh()
        self._fit_window(initial=True)
        root.after(120, self._poll_defs)
        self.rude_read = None     # the background read of Wiktionary's meanings (_start_rude_read), while it runs
        root.after(3000, self._start_rude_read)
        root.after(300, self._startup)

    def open_window(self):
        """Show the main window once it is built, sized and filled (F-1): every pending layout is finished while
        it is still hidden, and it is drawn while see-through (where the system allows it: Windows, macOS, a
        Linux desktop with a compositor), so it appears complete rather than as a blank frame filling in."""
        r = self.root
        r.update_idletasks()
        try:
            r.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        r.deiconify()
        r.update()                                  # (mapped, exposed and every widget drawn)
        r.after(30, self._unveil)

    def _unveil(self):
        try:
            self.root.attributes("-alpha", 1.0)
        except tk.TclError:
            pass

    def _startup(self):
        """One-time prompts after the window opens: which save was resumed, merge offers, how words are dealt
        (ST-6: once per save, then in Settings), anchors."""
        if self.note:
            self.flash(self.note, ms=12000)
        if self.other_saves:
            self.offer_merge(self.other_saves)

        def anchors():
            if not all(self.anchors):
                self.edit_anchors()
        if self.ask_dealing and self.store.get_meta("dealt_asked") != "1":
            self.edit_dealing(first=True, on_done=anchors)
        else:
            anchors()
        if self.offer_form:
            self.root.after(self.FORM_OFFER_MS, self._offer_other_form)

    # ---- T-9: the other form, offered once --------------------------------------------------------------------
    FORM_OFFER_MS = 1500                     # after the start's own questions; then checked this often until quiet
    FORM_ASKED = {False: "offered_program", True: "offered_source"}      # meta: asked once (source / program)

    def _offer_other_form(self):
        """Once (remembered in the save, from source and in the program each), when nothing else is going on: from
        source "Make this a standalone program?" (T-9: yes does what File > Source & Updates would); in the
        program its source is unpacked beside it without asking (T-10, _unpack_beside). Waits while a question or
        settings page is open, while a long job runs and while Wiktionary's meanings are being downloaded."""
        frozen = is_frozen()
        key = self.FORM_ASKED[frozen]
        if not self.root.winfo_exists() or self.store.get_meta(key) == "1":
            return
        if dialog_open(self.root) or self.busy or self.rude_read is not None:
            self.root.after(self.FORM_OFFER_MS, self._offer_other_form)
            return
        if frozen and not standalone.bundled_source():
            return                                   # (built without its source: nothing to offer)
        if not frozen and os.path.exists(standalone.program_path(standalone.ROOT)):
            return                                   # (a program is beside tierlist.py already)
        self.store.set_meta(key, "1")                # (asked once, whatever the answer)
        if frozen:                                   # (T-10, asked for: no question; done once, quietly, unless a
            return self._unpack_beside()             # copy of the source is beside the program already)
        else:
            yes = ask_yes_no("Source & Updates", "Make this a standalone program?",
                             "It builds Word Tier List into one program for this computer, next to tierlist.py "
                             "(a minute or two), then reopens as the program with the same save; Python is no "
                             "longer needed to run it. You can do it any time from File > Source & Updates.",
                             yes="Make it", no="Not now", parent=self.root)
        if yes:
            return SourceDialog(self, go=True)
        return None

    def _unpack_beside(self):
        """The built program's first start (T-10): its source goes into "Word Tier List source" beside it, unless a
        copy is there already (standalone.existing_source: tierlist.py beside it, or a folder holding one). Says
        where in a message; File > Source & Updates can unpack it again, or elsewhere. Returns the folder, or None."""
        if standalone.existing_source():
            return None
        where = standalone.default_source_folder()
        try:
            standalone.unpack(standalone.bundled_source(), where)
        except OSError as exc:
            self.flash(f"The source code could not be unpacked beside the program ({exc.strerror or exc}); "
                       "File > Source & Updates can put it elsewhere", ms=6000)
            return None
        self.flash(f"The source code is unpacked beside the program, in \"{os.path.basename(where)}\" "
                   "(File > Source & Updates)", ms=5000)
        return where

    # ---- construction ------------------------------------------------------------------
    def _menu_items(self):
        """The header menus (UI-10): File (import/export), Edit (undo), View (browse, definitions, motion),
        Settings (anchors, queue). Each item is a DropMenu row: ("command", label, command, shortcut)
        or ("check", label, variable, command). Shortcuts come from the keymap (UI-48)."""
        key = lambda a: (self.keys.display(a) or [None])[0]
        return [
            ("File", [("command", "Import earlier progress...", self.import_progress, None),
                      ("command", "Export tier list...", self.export, None),
                      ("command", "Where is my save file?", self.show_save_location, None),
                      *([("command", "Add to applications menu", self.add_launcher, None)]
                        if sys.platform.startswith("linux") else []),
                      ("command", "Source & Updates...", self.source_updates, None),
                      ("separator",),
                      ("command", "Quit", self.on_close, None)]),
            ("Edit", [("command", "Undo", self.undo, key("undo"))]),
            ("View", [("command", "Browse / edit tier list...", self.open_browser, None),
                      ("separator",),
                      ("command", "Zoom in", lambda: self.zoom_step(1), key("zoom_in")),
                      ("command", "Zoom out", lambda: self.zoom_step(-1), key("zoom_out")),
                      ("command", "Actual size", lambda: self.set_zoom(1.0), key("zoom_reset")),
                      ("separator",),
                      ("check", "Show definitions", self.defs_var, lambda: self.toggle_defs(self.defs_var.get())),
                      ("check", "Reduce motion", self.motion_var, self.toggle_motion),
                      ("check", "Censor obscene words", self.censor_var, self.toggle_censor),
                      ("check", "Dark mode", self.dark_var, self.toggle_dark)]),
            ("Settings", [("command", "Anchor words...", self.edit_anchors, None),
                          ("command", "How words are dealt...", self.edit_dealing, None),
                          ("command", "Keyboard shortcuts...", self.edit_keys, None),
                          ("command", "Tier colours...", self.edit_tier_colours, None),
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
        self.mode_switch.show_only(self.modes_with_work(self.store.stats()), animate=False)
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
        left = ttk.Frame(band)
        left.pack(side="left", anchor="n")
        line = ttk.Frame(left)
        line.pack(side="top", anchor="w")
        self.stats_lbl = ttk.Label(line, anchor="w")
        self.stats_lbl.pack(side="left", anchor="n", pady=(4, 0))
        # "+N today", small and muted; the pace only in a hover note (UI-15: no pressure on screen)
        self.today_lbl = ttk.Label(line, anchor="w", foreground=PALETTE["muted"])
        self.today_lbl.pack(side="left", anchor="n", pady=(4, 0), padx=(14, 0))
        # the progress shelf under it: book spines from common to rare words, and "95% of text" (UI-14)
        self.progress_bar = Bookshelf(left, font("body"), animator=self.anim)
        self.progress_bar.pack(side="top", anchor="w", pady=(8, 0))
        self.progress_tip = Tooltip(self.progress_bar, lambda e: self.progress_bar.note(e.x), font=font("body"))
        self.today_tip = Tooltip(self.today_lbl, lambda e: self._pace_text(), font=font("body"),
                                 side="right")                     # (the progress bar is below it)
        # each tab's own view in one spot (UI-31): they share its space, so switching tabs never moves the page
        views = tk.Frame(band, bg=PALETTE["bg"])
        views.pack(side="right", anchor="n")
        self.chart = DistributionChart(views, TIERS, font("body"), font("head"), animator=self.anim)
        self.settled_chart = SettledChart(views, TIERS, font("body"), font("head"), animator=self.anim)
        self.conflict_card = ConflictCard(views, font("title"), font("body"))
        # (Boundary check has none: its swap strip was archived by request; see "In consideration")
        self.tab_views = {"place": self.chart, "refine": self.settled_chart, "conflict": self.conflict_card}
        for v in self.tab_views.values():
            v.grid(row=0, column=0, sticky="ne")


        # bottom bar first so it keeps the bottom edge
        bottom = ttk.Frame(r, padding=(10, 6))
        bottom.pack(side="bottom", fill="x")
        ttk.Button(bottom, text="Undo", command=self.undo, takefocus=0).pack(side="left")
        ttk.Button(bottom, text="Browse / edit...", command=self.open_browser, takefocus=0).pack(side="left", padx=6)
        self.def_btn = ttk.Button(bottom, text="Definition (D)", command=lambda: self.toggle_defs(), takefocus=0)
        self.def_btn.pack(side="left")
        self.hint_lbl = ttk.Label(bottom, foreground=PALETTE["muted"], justify="right")   # one line (it is short)
        self.hint_lbl.pack(side="right")

        self.def_frame = DefinitionDrawer(r, {"body": font("body"), "head": font("head")}, animator=self.anim, gap=6)
        self.def_text = self.def_frame.text

        self.center = ttk.Frame(r)
        self.center.pack(side="top", fill="both", expand=True)
        # messages float over the page as toasts (UI-11); each message is its own Toast (see _new_toast)
        self.toasts = [Toast(r, font("label"), animator=self.anim, on_gone=self._toast_gone)]

        # ---- place view
        self.place_frame = ttk.Frame(self.center)
        inner = ttk.Frame(self.place_frame)
        self.place_inner = inner
        inner.place(relx=0.5, anchor="n")            # (its top: _recenter)
        self.word_card = WordCard(inner, font("word"), font("body"))
        self.word_card.grid(row=0, column=0, pady=(0, 22))      # breathing room above the tier pills
        self.word_card.on_find, self.word_card.on_enter = self.start_lookup, self.lookup_word   # (UI-51)
        self.word_card.animator = self.anim                       # (a censored word un-smears under the pointer)
        Tooltip(self.word_card, self._card_note, font=font("body"))
        self.place_empty = EmptyCard(inner, font("title"), font("body"))     # every word placed (UI-20)
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
        pi.place(relx=0.5, anchor="n")
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
        self.ctx_lbl = ttk.Label(pi, text="", foreground=PALETTE["muted"], wraplength=720, justify="center")
        self.ctx_lbl.grid(row=3, column=0, pady=(10, 0))
        self.pair_empty = EmptyCard(pi, font("title"), font("body"))         # nothing to duel here (UI-20)
        self.center.bind("<Configure>", self._on_center_configure)
        for inner in (self.place_inner, self.pair_inner):       # (placed by their top: a change of height
            inner.bind("<Configure>", lambda e: self._recenter())   # re-centres them)
        self.root.bind("<Configure>", self._on_root_configure, add="+")

    # ---- zoom (View menu, Ctrl + / Ctrl - / Ctrl 0) ---------------------------------------------------------
    ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.6, 2.0, 0.1

    def set_zoom(self, z):
        """Make everything in the main window bigger or smaller (every shared font scales, so buttons, cards,
        the chart and the menus follow). Saved. The window grows if it has to, never past the screen: what
        shows is the zoom or the biggest size that fits, whichever is smaller (_fit_window). So zoom out is
        always one step and never makes anything bigger; a zoom in that cannot make anything bigger says so
        and leaves the zoom as it was."""
        z = round(min(self.ZOOM_MAX, max(self.ZOOM_MIN, z)), 2)
        if z == self.zoom and self.grow == 1:
            self._say_zoom(z)                     # unchanged (Ctrl 0 at 100%, zoom out at the smallest): say so
            return "break"
        old, before = self.zoom, self.font_scale * self.zoom * self.grow     # what is on screen now
        bigger = z > round(old * self.grow, 2) + 1e-9     # (a zoom in: in a grown window 120% can be a step down)
        cap = self._zoom_cap.get(self._layout_key())
        if bigger and cap is not None and z >= cap:
            z = round(cap - self.ZOOM_STEP, 2)    # known not to fit here: refuse on the spot, nothing tried on screen
            if z <= old and self.grow == 1:
                self._refuse_zoom()
                return "break"
        self._apply_zoom(z)
        now = self.font_scale * self.zoom
        if bigger and now <= before + 1e-9:
            self._zoom_cap[self._layout_key()] = z    # remember: holding the key will not try it again
            self._apply_zoom(old)
            self._refuse_zoom()
            return "break"
        key = self._zoom_key()
        self.store.set_meta(key, z)
        self._keep_compatible(key, z)
        self._say_zoom(z)
        return "break"

    def _max_zoom(self, store=None):
        """The zoom kept for the window maximized (UI-57), or None before one is chosen there."""
        store = store or self.store
        if store.get_meta("zoom_max") is None:
            return None
        return store.meta_number("zoom_max", 1.0, lo=self.ZOOM_MIN, hi=self.ZOOM_MAX)

    def _keep_compatible(self, key, z):
        """The two zooms (UI-57) stay compatible (reported: the window opened with its contents bigger than when
        maximized, so maximizing shrank them): the window at any other size never shows more than maximized. A zoom
        chosen for the usual window above the maximized one raises that too; one chosen maximized below the usual
        one lowers that too."""
        if key == "zoom":
            kept = self._max_zoom()
            if kept is not None and z > kept:
                self.store.set_meta("zoom_max", z)
        else:
            if z < self.store.meta_number("zoom", 1.0, lo=self.ZOOM_MIN, hi=self.ZOOM_MAX):
                self.store.set_meta("zoom", z)

    def _zoom_key(self):
        """Where the zoom is kept: one for the window maximized, one for it at any other size (UI-57: each comes
        back as it was left when the window is maximized or restored again, even after a restart)."""
        return "zoom_max" if is_maximized(self.root) else "zoom"

    def _follow_maximize(self):
        """The window was just maximized or restored: show the zoom kept for that (UI-57; restored: the usual zoom,
        100% until one is chosen). Maximized before any zoom was chosen there, the contents simply grow with it
        (UI-25). True if the zoom changed."""
        m = is_maximized(self.root)
        if m == self._maximized:
            return False
        self._maximized = m
        if m and self.store.get_meta("zoom_max") is None:
            return False
        self._apply_zoom(self.store.meta_number("zoom_max" if m else "zoom", 1.0, lo=self.ZOOM_MIN, hi=self.ZOOM_MAX))
        return True                           # (always: the window's new size is the one that zoom is shown in)

    def _say_zoom(self, z):
        """'Zoom 130%' on a white card, every time a zoom key is pressed, even when nothing changed (M-6)."""
        note = "" if self.font_scale > 0.999 else " (shown smaller, to fit the screen)"
        self.flash(f"Zoom {round(z * 100)}%{note}", kind="info",
                   ms=900 if not note else 1600)

    def zoom_step(self, d):
        """Ctrl + / Ctrl - (and the View menu): one step bigger or smaller than what is on screen now, which in a
        window enlarged by UI-25 is more than the saved zoom."""
        return self.set_zoom(round(self.zoom * self.grow, 1) + d * self.ZOOM_STEP)

    def _layout_key(self):
        """What decides how big things can get: the tab, the definitions pane and the screen."""
        return (self.mode, self.show_defs, tuple(usable_area(self.root)))

    def _refuse_zoom(self):
        """Zoom in cannot go further: say so once; while that message shows, a repeat just wiggles it."""
        t = getattr(self, "_zoom_note", None)
        if t is not None and t.cget("text") == self.ZOOM_FULL and t.wiggle():
            return
        self.flash(self.ZOOM_FULL, kind="info", ms=1500)
        self._zoom_note = self.toast

    ZOOM_FULL = "This is as big as fits on this screen"

    def _apply_zoom(self, z):
        self.zoom = z
        self.grow = 1.0                        # a zoom sets the size: the window as it is now becomes "normal"
        self._ref_size = None                  # (measured afresh at the new zoom, then the window's size at least)
        self._fit_cache.clear()
        self._fit_window(rebase=True)

    # ---- window size: fits the screen and the contents ------------------------------------------
    FIT_STEP, FIT_LOWEST = 0.1, 0.5         # sizes tried until the contents fit: the zoom, then 0.1 less each time,
                                             # down to half the normal size (half the zoom when that is smaller)
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
        """The centre area was resized. Wrapping and the big words' size depend only on the width, so a
        height-only change (the definition drawer sliding, UI-35) just re-centres: re-fitting every
        button on every frame of the slide is what made it stutter."""
        if e.width != self._center_w:
            self._center_w = e.width
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
            # (its top, in whole pixels: centred by Tk with our offset on top, the two roundings took turns and
            # the content shook by a pixel while the definitions pane slid against its top)
            top = int(free - max(0, min(band / 2, free)))
            inner.place_configure(y=top)

    def _fit_big_text(self):
        """Set the big words' fonts to their full size, and shrink the duel's so a long pair still fits on a line
        (down to about a third, then it wraps). The word card fits its own word in a private copy of its font
        (WordCard), so placing a word never resizes a shared font. A font is only configured when its size
        really changes: every change makes Tk re-measure each widget that uses it."""
        width = self.center.winfo_width()
        if width < 50:                         # not laid out yet
            return
        f = ui_factor(self.root)
        changed = False
        for role in ("word", "pair"):
            base = max(7, int(round(ROLES[role][0] * self.font_scale * self.zoom * self.grow)))
            fnt, size = font(role), base
            if role == "pair":
                probe = fnt.copy()                 # measured at the full size without touching the shared font
                probe.configure(size=base)
                avail = (width - int(220 * f)) // 2 - int(80 * f)
                need = max((probe.measure(t) for t in (self.left_btn.cget("text"), self.right_btn.cget("text"))
                            if t), default=0)
                if need > avail > 0:
                    size = max(7, int(base * 0.35), int(base * avail / need))
            if fnt.cget("size") != size:
                fnt.configure(size=size)
                changed = True
        if changed:
            refresh_widgets(self.center)       # the word card and duel cards follow the resized fonts

    def _content_size(self):
        """(width, height) the window needs to show everything without clipping, in pixels.

        Fixed rows (header, stats, bottom bar, definition pane when shown) report their own size; the
        centre area uses `place`, which does not report one, so the two views' inner frames are
        measured and given some breathing room.
        """
        r = self.root
        r.update_idletasks()
        f = ui_factor(r) * self.font_scale * self.zoom * self.grow
        rows = [w for w in r.pack_slaves() if w is not self.center]
        extra = 0 if self.opt_frame.winfo_manager() else self.opt_frame.winfo_reqheight() + 16  # refine/boundary row
        inner_w = max(self.place_inner.winfo_reqwidth(), self.pair_inner.winfo_reqwidth())
        inner_h = max(self.place_inner.winfo_reqheight(), self.pair_inner.winfo_reqheight() + extra)
        width = max([w.winfo_reqwidth() for w in rows] + [inner_w + int(60 * f)])
        height = sum(w.winfo_reqheight() for w in rows) + inner_h + int(50 * f)
        return width, height

    def _fit_window(self, initial=False, rebase=False, folded_drawer=False):
        """Size and place the main window for this screen and these contents.

        The contents are shown at the zoom, or at the biggest size in 0.1 steps below it that fits the screen,
        whichever is smaller (so a zoom bigger than the screen allows shows as big as fits, and a smaller zoom
        is never shown bigger). First call: then the window opens at the preferred size
        (BASE_SIZE scaled for dpi), at least as big as the contents need, no bigger than the usable
        screen, centred. Later calls (mode or definition pane changed) only grow it if the contents
        now need more room. The minimum size always follows the contents. It also sets the size at which
        the contents start to grow with the window (UI-25); `rebase` (after a zoom) makes that at least the
        window's current size. `folded_drawer`: the definitions drawer is folded, about to slide open; count it at
        its full height without showing it (showing it open for the measurement made it flash, UI-35).
        """
        r = self.root
        before = (r.winfo_width(), r.winfo_height())
        if self.show_defs:
            self.def_frame.set_lines(self._def_want)
        if not initial and self.grow > 1:     # still fits at the grown size, the definition pane shortened if it
            for lines in (range(self._def_want, 2, -1) if self.show_defs else (None,)):     # must: re-measuring at
                if lines:                                                     # normal size would flash small text
                    self.def_frame.set_lines(lines)
                cw, ch = self._content_size()
                if folded_drawer:             # (folded, about to slide open: counted at its full height, as below;
                    ch += self.def_frame.unshown_height()        # left out, it slid open over the word card)
                if cw <= r.winfo_width() and ch <= r.winfo_height():
                    return
        f = ui_factor(r)
        area = usable_area(r)
        # Make the contents fit the usable area: first shorten the definition pane (down to 3 lines),
        # then take the next font step down, and repeat. Every fit starts again from the full size (the
        # zoom), so a step taken for a taller view (the definitions open, a duel tab) is undone when it
        # closes; it starts from the step that fitted this layout last time, so it does not flicker.
        key = (self.mode, self.show_defs and self._def_want, self.zoom, tuple(area))
        start = self.zoom if initial else self._fit_cache.get(key, self.zoom)
        if folded_drawer:                # (opening the drawer only ever needs smaller text: tried from the full zoom,
            start = min(start, round(self.font_scale * self.zoom, 2))     # each size tried showed, the page swelling
                                                                          # past the window and stepping back down)
        lowest = min(self.zoom, 1.0) * self.FIT_LOWEST      # (half the normal size: a big zoom on a small
        sizes = [round(self.zoom - k * self.FIT_STEP, 2)      # screen may shrink as far as no zoom would)
                 for k in range(int((self.zoom - lowest) / self.FIT_STEP + 1e-6) + 1)]
        rescaled = False
        self.grow = 1.0                          # measured at the normal size; _apply_grow re-grows after
        for size in [z for z in sizes if z <= start + 1e-9]:
            self.font_scale = size / self.zoom
            if self._applied_scale != size:      # re-scaling and redrawing everything is the slow part:
                self._applied_scale = size       # skip it when the size is already right
                rescaled = True
                scale_fonts(size)
                self._apply_wraps(area[2])
                refresh_widgets(self.root)
            for lines in (range(self._def_want, 2, -1) if self.show_defs else (self.DEF_LINES,)):
                self.def_frame.set_lines(lines)
                cw, ch = self._content_size()
                if folded_drawer:
                    ch += self.def_frame.unshown_height()
                if cw <= area[2] and ch <= area[3]:
                    break
            else:
                continue
            break
        self._fit_cache[key] = round(self.font_scale * self.zoom, 2)
        if not self.show_defs and self.def_frame.lines() != self.DEF_LINES:
            self.def_frame.set_lines(self.DEF_LINES)
        r.update_idletasks()
        if rescaled:
            self._fit_big_text()               # the fonts changed even if the window size did not
        fs = self.font_scale * self.zoom
        min_w = min(max(cw, int(self.MIN_SIZE[0] * f * fs)), area[2])
        min_h = min(max(ch, int(self.MIN_SIZE[1] * f * fs)), area[3])
        r.minsize(min_w, min_h)
        pref = (int(self.BASE_SIZE[0] * f * fs), int(self.BASE_SIZE[1] * f * fs))
        need = (max(pref[0], cw), max(pref[1], ch))
        # The size at which nothing grows (UI-25) is set when the window opens and by a zoom (rebase, below);
        # a later fit (a tab, the definitions pane) may only raise it. Re-measuring it smaller made the contents
        # grow past the zoom, and past what a zoom may reach, after every tab switch or pane close (reported).
        if initial or self._ref_size is None:
            self._ref_size = need
        else:
            self._ref_size = (max(self._ref_size[0], need[0]), max(self._ref_size[1], need[1]))
        if initial:
            w, h = fit_size((min_w, min_h), pref, (area[2], area[3]))
            r.geometry(center_geometry(w, h, area))
        else:
            r.update_idletasks()
            w, h = max(r.winfo_width(), min_w), max(r.winfo_height(), min_h)
            x, y = r.winfo_x(), r.winfo_y()          # grown past the screen's edge (the minimum size grows it
            nx = max(area[0], min(x, area[0] + area[2] - w))        # too): moved back onto it
            ny = max(area[1], min(y, area[1] + area[3] - h))
            # (never while maximized: the window is bigger than the usable area then, and moving it back onto it
            # would un-maximize it)
            # (grown by the minimum size alone, it is set as the size too: left to the minimum, the window shrank
            # back to its old size the moment the minimum fell again, a jump as the definitions pane closed)
            if ((w, h) != before or (nx, ny) != (x, y)) and not is_maximized(r):
                r.geometry(f"{w}x{h}" + (f"+{nx}+{ny}" if (nx, ny) != (x, y) else ""))
            if rebase:
                self._ref_size = (max(self._ref_size[0], w), max(self._ref_size[1], h))
            self._apply_grow()

    # ---- a bigger window, bigger contents (UI-25) ----------------------------------------------------
    GROW_MAX, GROW_STEP = 1.75, 0.05

    def _grow_for(self, w, h):
        """How much bigger than normal the contents may be in a w x h window: 1 up to the preferred size
        (or what the contents need, if more), then in proportion, in steps of GROW_STEP, up to GROW_MAX."""
        rw, rh = self._ref_size
        g = math.floor(min(w / rw, h / rh) / self.GROW_STEP + 1e-6) * self.GROW_STEP
        kept = None if is_maximized(self.root) else self._max_zoom()
        if kept is not None:                  # (a big window, not maximized, never shows more than maximized does)
            shown = self.font_scale * self.zoom
            g = min(g, math.floor(kept / shown / self.GROW_STEP + 1e-6) * self.GROW_STEP)
        return round(max(1.0, min(self.GROW_MAX, g)), 2)

    def _on_root_configure(self, e):
        """The window was resized: re-grow the contents once resizing pauses for 80 ms (like Browse)."""
        if e.widget is not self.root:
            return
        self._give_room(e.height)
        if self._grow_job:
            self.root.after_cancel(self._grow_job)
        self._grow_job = self.root.after(80, self._apply_grow)

    def _apply_grow(self):
        """Scale every shared font with the window (the word card, pills, buttons, chart and menus follow).
        The minimum size stays the one measured at the normal size, so the window can always shrink back."""
        self._grow_job = None
        if not self._ref_size or self._follow_maximize():
            return
        g = self._grow_for(self.root.winfo_width(), self.root.winfo_height())
        if g == 1.0 and self.grow > 1:
            self.grow = 1.0
            self._fit_window()                # back to normal: the full fit (it also renews the minimum size)
            return
        scale = self.font_scale * self.zoom * g
        self.grow = g
        if scale == self._applied_scale:
            return
        self._applied_scale = scale
        scale_fonts(scale)
        self._apply_wraps(self.center.winfo_width())
        refresh_widgets(self.root)
        self._fit_big_text()
        self.root.after_idle(self._recenter)

    # ---- layout toggles -------------------------------------------------------------------------------
    def _layout_defs(self, animate=False, on_closed=None):
        """Show or hide the definition drawer to match self.show_defs (easing open / shut when `animate`);
        on_closed() runs once a closing drawer is out of the layout."""
        d = self.def_frame
        d.settle()
        if animate and self.show_defs == d.is_open:      # no change: nothing to animate
            animate = False
        if self.show_defs:
            if animate:
                d.collapse()                   # packed folded: it must not show at full height first
            else:
                d.set_open(True)
            d.pack(side="bottom", fill="x", padx=10, before=self.center)
            self._render_defs()
            if animate:
                self._make_room(d.natural_height())   # grow the window first only if it must, then ease open
                d.open()
        elif d.winfo_manager():
            self._room_from = None
            def gone():
                if not self.show_defs:
                    d.pack_forget()
                    if on_closed:
                        on_closed()
            if animate:
                d.close(on_closed=gone)
            else:
                d.set_open(False)
                gone()

    def _make_room(self, extra):
        """Opening the drawer (`extra` pixels tall): one quick size check instead of the full fitting pass
        (which took long enough to swallow the slide). The page usually has room; if not, the full fit
        runs (it may shorten the pane or the text), counting the folded drawer at its full height. A window that
        must grow does so with the drawer already holding the room it gains (opened from nothing, the page grew,
        dropped and slid back up as the drawer opened: a jump, seen whenever the window had to grow)."""
        r = self.root
        cw, ch = self._content_size()
        self._room_from = None
        if ch + extra > r.winfo_height() or cw > r.winfo_width():
            self._room_from = r.winfo_height()        # (_on_root_configure: what the window gains goes to the drawer,
            self._fit_window(folded_drawer=True)      # in the very layout of its new size; the drawer stays folded:
            self._give_room(r.winfo_height())         # it never flashes open first)

    def _give_room(self, height):
        """The window is `height` tall now; opening the drawer made it grow: the drawer takes what it gained since
        last time (a window manager may grow it in steps, or only after the slide has begun)."""
        if self._room_from is not None and height > self._room_from:
            self.def_frame.give(height - self._room_from)
            self._room_from = height

    def toggle_defs(self, value=None):
        """Show/hide definitions (D key, menu, button). `value` forces on/off; the choice is saved."""
        self.show_defs = (not self.show_defs) if value is None else bool(value)
        if not self.show_defs:
            self._def_want = self.DEF_LINES     # opened again, it fits the words shown then
        self.defs_var.set(self.show_defs)
        self.store.set_meta("show_defs", int(self.show_defs))
        was_open = self.def_frame.is_open
        self._layout_defs(animate=True, on_closed=self._fit_window)   # closing: re-fit once it is out of the way
        if self.show_defs and was_open:
            self._fit_window()

    def toggle_motion(self):
        """View > Reduce motion: turn animations off (they jump to their end state). Saved."""
        self.reduce_motion = self.motion_var.get()
        self.anim.reduce_motion = self.reduce_motion
        self.anim.finish_all()
        self.store.set_meta("reduce_motion", int(self.reduce_motion))

    def toggle_censor(self):
        """View > Censor obscene words (asked for: the same switch as in How words are dealt, a click away). Saved;
        the card, the duel cards, the definitions and Browse show it at once, and a comparison carries on."""
        self.store.set_censor(self.censor_var.get())
        if self.censor_var.get():
            self.censor_note()
        self.refresh()
        self._render_defs()
        for b in self.browsers:
            if b.alive():
                b.reload(keep_view=True)

    CENSOR_NOTED = "censor_noted"        # meta: the note on censoring has been shown once in this save

    def censor_note(self, show=None, toast=True):
        """Censoring was just turned on (asked for: say it may not be fully accurate). The first time in a save the
        whole note, in the window it was turned on in (asked for: never a window of its own): show(text), as the
        How words are dealt page does under its tick box, or else a longer toast; after that a short toast
        (`toast`), or nothing."""
        if self.store.get_meta(self.CENSOR_NOTED) != "1":
            self.store.set_meta(self.CENSOR_NOTED, "1")
            text = f"{CENSOR_CAVEAT_HEAD}. {CENSOR_CAVEAT}"
            if show:
                show(text)
            else:
                self.flash(text, kind="info", ms=9000)
            return text
        if toast:
            self.flash(CENSOR_CAVEAT_SHORT, kind="info", ms=4000)
        return None

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
            self.focus_lbl.config(text=f"Focus: {self.shown(self.focus)} ({self.focus_left} duels left)")
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

    def flash(self, text, kind="ok", ms=3500, bg=None, fg=None):
        """Show a message in a toast for `ms` milliseconds, coloured for its `kind` ("ok", "info", "warn":
        PALETTE's pairs) or by `bg` / `fg` (a tier's colours). Each message is its own toast, the newest on top."""
        if bg is None:
            bg, fg = PALETTE[kind]
        self._new_toast().show(text, (bg, fg or PALETTE[kind][1]), ms, in_=self.center,
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
        self.censor_var.set(self.store.deal_settings()["censor"])     # (How words are dealt may have changed it)
        self.refresh()

    def _update_stats(self):
        """Status band: one quiet line (format_stats), "+N today", which tabs show (UI-46), and the current
        tab's own view: the tier chart, how settled each tier is, or the conflicts (Boundary check has none)."""
        s = self.store.stats()
        self.stats_lbl.config(text=format_stats(s))
        self.today_lbl.config(text=f"+{self.store.actions_since(local_midnight()):,} today")
        self.mode_switch.show_only(self.modes_with_work(s))
        self.progress_bar.set(self.store.shelf())
        # each tab shows its own view in the chart's spot (UI-31); the others keep their space, hidden
        for mode, view in self.tab_views.items():
            if view.shown != (mode == self.mode):
                view.show(mode == self.mode)
        # on top of the others (a hidden canvas still paints its background); Canvas.lift would raise its items
        if self.mode in self.tab_views:
            self.root.tk.call("raise", str(self.tab_views[self.mode]))
        if self.mode == "place":
            self.chart.set([s["tiers"].get(t, 0) for t in range(len(TIERS))], animate=self._chart_ready)
            self._chart_ready = True             # the first fill does not grow from zero
        else:
            self._chart_ready = False            # back in Place it shows the counts as they are, no growth
        if self.mode == "refine":
            self.settled_chart.set(self.store.settled_shares(self.SETTLED_DUELS, s["tiers"]),
                                   animate=self._settled_ready)
            self._settled_ready = True
        else:
            self._settled_ready = False
        if self.mode == "conflict":
            self.conflict_card.set(s["conflicts"])

    SETTLED_DUELS = 5   # duels a word needs before its place in its tier counts as settled (UI-31)

    @staticmethod
    def modes_with_work(s):
        """The tabs worth showing for Store.stats() `s` (UI-46): Refine once a tier holds two words,
        Boundary check once two neighbouring tiers both hold words, Resolve conflicts while there are any."""
        t = s["tiers"]
        modes = {"place"}
        if any(n >= 2 for n in t.values()):
            modes.add("refine")
        if any(t.get(i) and t.get(i + 1) for i in range(len(TIERS) - 1)):
            modes.add("boundary")
        if s["conflicts"]:
            modes.add("conflict")
        return modes

    PACE_GAP_S = 120     # a longer pause between two actions is a break: it adds only this much to the pace

    def _count_action(self):
        """One more word or duel this session: the time since the last one counts towards the pace, up to
        PACE_GAP_S (UI-33), so stepping away does not drag the number down."""
        now = time.time()
        self._active_s += min(max(0.0, now - self._last_action), self.PACE_GAP_S)
        self._last_action = now
        self.session_count += 1

    def _pace_text(self):
        """The hover note on "+N today": this session's pace, once there is enough to say anything."""
        hours = self._active_s / 3600.0
        if self.session_count < 5 or hours <= 0:
            return None                                 # too early to say anything: no note
        return f"about +{self.session_count / hours:,.0f}/hr"

    def _hint(self):
        """Bottom-right key reminder: only the keys no button on screen already shows. The tier pills,
        compare / don't-know buttons, Better / Same / Worse / Back, the duel cards and Tie / Skip carry
        their own key hints, and the Definition button names its key. All from the keymap (UI-48)."""
        keys = lambda a: " or ".join(self.keys.display(a))
        if self.mode == "place" and self.cmp:
            h = f"{keys('stop')} stop comparing" if self.keys.keys_of("stop") else ""
        else:                                    # (the Compare button that shows Space is hidden meanwhile)
            h = f"{keys('undo')} undo" if self.keys.keys_of("undo") else ""
            if len(self.mode_switch.visible) > 1 and self.keys.keys_of("next_tab"):
                h += ("   \u00b7   " if h else "") + f"{keys('next_tab')} next tab"
        self.hint_lbl.config(text=h)

    def apply_keys(self):
        """Show the keymap's keys everywhere a key is named (UI-48): the buttons' little hints, the Definition
        button, the menus' shortcut column and the bottom-right hint."""
        km = self.keys
        hint = lambda a, sep=" / ", short=True: sep.join(km.display(a, short=short))
        tiers = km.keys_of("place")
        for t, b in enumerate(self.tier_btns):
            b.config(hint=display(tiers[t]) if t < len(tiers) else "")
        for a in ("better", "same", "worse", "back"):
            self.cmp_btns[a].config(hint=hint(a))
        self.compare_btn.config(hint=hint("compare"))
        self.later_btn.config(hint=hint("later"))
        d = self.duel
        d.left.config(hint="  ".join(km.display("left")))
        d.right.config(hint="  ".join(reversed(km.display("right"))))
        d.tie.config(hint="  ".join(km.display("tie")))
        d.skip.config(hint=hint("skip"))
        first = km.display("defs")
        self.def_btn.config(text=f"Definition ({first[0]})" if first else "Definition")
        for name, items in self._menu_items():
            self.header.menus[name] = items
            self.header.drops[name].items = items
        self._hint()

    def _show_frame(self, frame):
        """Show one of the centre's views (place, pair) and hide the other."""
        for f in (self.place_frame, self.pair_frame):
            if f is not frame:
                f.pack_forget()
        frame.pack(fill="both", expand=True)

    # ---- place mode ------------------------------------------------------------------------------------------
    def _show_place(self):
        """Place view: show the next unplaced word (or the 'all placed' message) and set up its buttons."""
        self.progress_bar.mark([])                    # (the shelf marks only the duel tabs' words, UI-55)
        self._show_frame(self.place_frame)
        row = None
        if self.looked_up:                            # a looked-up word comes first, until placed or skipped
            row = self.store.get_word(self.looked_up)
            if row is None or row["tier"] is not None:
                row, self.looked_up, self._was_looked_up = None, None, self.looked_up
        if row is None:
            row = self.store.next_unplaced()
        if row is None:
            self.cur_word = None
            self.word_card.grid_remove()
            out = self.store.left_out()
            if out:
                self.place_empty.set("Every word you chose is placed",
                                     f"{out:,} more are left out (Settings > How words are dealt). Refine within "
                                     "tier and Boundary check can keep polishing the order.")
            else:
                self.place_empty.set("Every word is placed",
                                     "Refine within tier and Boundary check can keep polishing the order.")
            self.place_empty.grid(row=0, column=0)
            self._set_question("")
            self.tier_row.grid_remove()
            self.cmp_row.grid_remove()
            self.act_row.grid_remove()
            self._render_defs([])
            self._hint()
            return
        self.cur_word = row["word"]
        self.place_empty.grid_remove()
        self.word_card.grid()
        notes = (" - looked up" if row["word"] == self.looked_up else "") + \
                (" - revisiting a word you skipped" if row["skips"] > 0 else "")
        label = card_label(row["kinds"], RUDE_NAMES.get(self.store.rude_kind(row["word"])),     # ("noun · sexual";
                           compound=bool(row["pen"]))                                            # compound: asked for)
        self.word_card.set(row["word"], f"frequency rank #{row['rank'] + 1:,}{notes}",   # (it fits the word itself)
                           censor=self.store.censored(row["word"]), kind=label or None)
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
            self._set_question(f"Is it better or worse than  \"{self.shown(anchor)}\"  ?\n(anchor for tier {TIERS[mid]})")
            self.tier_row.grid_remove()
            self.act_row.grid_remove()
            self.cmp_row.grid()
            self.cmp_btns["back"].set_enabled(bool(self.cmp["stack"]))   # nothing to step back to yet
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

    def _word_to_act_on(self):
        """The word on the card, for placing or skipping it, or None (none, or comparing). A word being typed on
        the card is put back first (a button clicked while typing)."""
        if not self.cur_word or self.cmp:
            return None
        self.word_card.end_typing()
        return self.cur_word

    def place_word(self, tier):
        """Put the current word straight into `tier` (keys 1-6 or the tier buttons)."""
        word = self._word_to_act_on()
        if word:
            self.store.place(word, tier)
            self._after_place(word, tier)

    def skip_word(self):
        """'Don't know / later': move the current word behind every fresh word."""
        word = self._word_to_act_on()
        if not word:
            return
        if word == self.looked_up:
            self.looked_up, self._was_looked_up = None, word
        self.store.skip(word)
        self._count_action()
        old_sub = self.word_card.sub
        self.flash(f"'{self.shown(word)}' moved to the back of the queue", kind="info", ms=1800)
        self.refresh()
        f = ui_factor(self.root)               # "later": it drifts back (up and away) instead of toward a tier
        self.word_card.transition_from(word, old_sub, dx=0, dy=-int(10 * f), animator=self.anim)

    def _after_place(self, word, tier):
        """Shared tail of every placement: count it, show the next word (the old one nudges toward its tier
        and fades, UI-16), confirm in the toast."""
        self._count_action()
        self.cmp = None
        old_sub = self.word_card.sub
        self.refresh()
        f = ui_factor(self.root)
        self.word_card.transition_from(word, old_sub, dx=int((tier - 2.5) * 5 * f), dy=int(12 * f),
                                       animator=self.anim)
        self._fling_toast(f"{self.shown(word)}  \u2192  {TIERS[tier]}", tier)

    def _fling_toast(self, text, tier):
        """The placement message rises out of the word card's top edge, rests above it, then flies into its
        tier's bar in the chart, fading as it goes, and the bar pulses (UI-11, UI-17)."""
        card, c, ch = self.word_card, self.center, self.chart
        if not (card.winfo_ismapped() and ch.shown and ch.winfo_ismapped()):
            self.flash(text, bg=TIER_COLORS[tier], fg=TIER_TEXT, ms=1500)
            return
        f = ui_factor(self.root)
        card_top = card.winfo_rooty() - c.winfo_rooty()
        bx, by = ch.bar_top(tier)

        def under(x0, y0, x1, y1):
            """White while the toast is mostly over the word card, else the cream page. Measured each frame:
            the card resizes for the next word while the toast is still on its way."""
            l, t = card.winfo_rootx() - c.winfo_rootx(), card.winfo_rooty() - c.winfo_rooty()
            r, b = l + card.winfo_width() - WordCard.SHADOW, t + card.winfo_height() - WordCard.SHADOW
            over = max(0, min(x1, r) - max(x0, l)) * max(0, min(y1, b) - max(y0, t))
            return PALETTE["surface"] if over * 2 > (x1 - x0) * (y1 - y0) else PALETTE["bg"]
        # it comes out at the card's top edge and rises: never over the card itself, where an opaque canvas
        # (tk has no transparency) would hide the letters or paint a box over the card's edge
        self._new_toast().fling(text, (TIER_COLORS[tier], TIER_TEXT), start_bottom=card_top,
                          rest_bottom=card_top - int(8 * f),
                          target=(bx - (c.winfo_rootx() + c.winfo_width() / 2), by - c.winfo_rooty()),
                          in_=c, wraplength=max(240, c.winfo_width() - 120), under=under,
                          on_arrive=lambda: ch.pulse(tier), clear=ch.bars_top() - c.winfo_rooty())

    def start_compare(self):
        """Begin placing the current word by comparing it to anchors (a binary search over the six tiers)."""
        if not self.cur_word or self.mode != "place" or self.cmp:
            return
        self.word_card.end_typing()            # (a button clicked while typing on the card: the word is back)
        if not all(self.anchors):
            self.flash("Set all six anchor words first (Settings > Anchor words...)", kind="warn")
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
        """Undo the last anchor answer. With none left it does nothing (its button is greyed out): Space leaves
        the comparison (UI-37), so holding Backspace never drops you out of it by surprise."""
        c = self.cmp
        if not c or not c["stack"]:
            return
        lo, hi, n = c["stack"].pop()
        c["lo"], c["hi"] = lo, hi
        del c["log"][n:]
        self._cmp_step()

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
                ctx += f"   -   focus word: {self.shown(self.focus)}"
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

    EMPTY = {   # UI-20: what an empty duel tab says instead of greyed-out cards
        "refine": ("Nothing to refine yet", "Duels start as soon as a tier holds two words. Keep placing!"),
        "boundary": ("Nothing to compare yet",
                     "Boundary checks start once two neighbouring tiers both have words."),
        "conflict": ("No conflicts", "Your answers all agree. Nicely consistent!"),
    }

    def _show_pair(self):
        """Pair view: show the next duel, or a friendly message with the buttons disabled when none is available."""
        self._show_frame(self.pair_frame)
        self.pair = self._pick_pair()
        if self.pair is None:
            title, text = self.EMPTY[self.mode]
            if self.focus:
                self.flash(f"No fresh opponents left for '{self.shown(self.focus)}'", kind="warn")
                self.focus = None
                self._update_focus_label()
            for w in (self.pair_title, self.duel, self.ctx_lbl):
                w.grid_remove()
            self.pair_empty.set(title, text)
            self.pair_empty.grid(row=2, column=0)
            self.duel.set_enabled(False)              # (their keys are off too)
            self._render_defs([])
            self.progress_bar.mark([])
        else:
            self.pair_empty.grid_remove()
            for w in (self.pair_title, self.duel, self.ctx_lbl):
                w.grid()
            words = [self.pair["left"], self.pair["right"]]
            tiers = [self.store.get_word(w)["tier"] for w in words]
            # the duel cards wear their word's tier colour (a neutral pastel without a tier)
            self.duel.show(*words, colors=[TIER_COLORS[t] if t is not None else PALETTE["neutral"] for t in tiers],
                           censor=[self.store.censored(w) for w in words])
            self._fit_big_text()
            self.ctx_lbl.config(text=self.pair["ctx"])
            self._render_defs(words)
            # little triangles on the shelf over where the two words come from (UI-55; one if they share a spine),
            # each in its word's tier colour (M-4)
            self.progress_bar.mark([self.store.spine_of(w) for w in words], tiers)
        self._hint()

    def pair_answer(self, ans):
        """Record a duel result ('left' | 'right' | 'tie'), report swaps/conflicts, count down a focus session."""
        if not self.pair:
            return
        a, b = self.pair["left"], self.pair["right"]
        kind = {"refine": "within", "boundary": "boundary", "conflict": "conflict"}[self.mode]
        res = {"left": "a", "right": "b", "tie": "tie"}[ans]
        info = self.store.record_comparison(a, b, res, kind)
        self._count_action()
        if info["swapped"]:
            w, wt, l, lt = info["swapped"]
            self.flash(f"Swapped: {self.shown(w)} \u2192 {TIERS[wt]},  {self.shown(l)} \u2192 {TIERS[lt]}", bg=TIER_COLORS[wt], fg=TIER_TEXT)
            self.note_anchor_changes(info["anchors"])
        elif info["conflict"]:
            self.flash("Conflict: that contradicts earlier answers. Pair saved for review "
                       "(Resolve conflicts).", bg=PALETTE["alert"][0], fg=PALETTE["alert"][1], ms=5000)
        else:                                  # every duel answer gets its little message, not only swaps
            win, lose = (a, b) if ans != "right" else (b, a)
            tier = self.store.get_word(win)["tier"]
            tint = TIER_COLORS[tier] if tier is not None else PALETTE["info"][0]
            self.flash(f"{self.shown(win)}  {'=' if ans == 'tie' else '>'}  {self.shown(lose)}", bg=tint, fg=TIER_TEXT,
                       ms=1400)
        if self.focus:
            self.focus_left -= 1
            if self.focus_left <= 0:
                self.flash(f"Finished refining '{self.shown(self.focus)}'")
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

    # ---- looking up a word to sort it now (UI-51) --------------------------------------------------------------
    def start_lookup(self):
        """The magnifier on the card (or its key): type a word on the card, Enter brings it up to sort now (the
        queue order of the rest does not change). The magnifier again, or Escape, goes back."""
        card = self.word_card
        if card.typing:
            card.end_typing()
            return
        if self.mode != "place" or not self.cur_word or self.busy:
            return
        if self.cmp:
            self._cancel_compare()
        self._to_add = None
        card.begin_typing()

    def lookup_word(self, text):
        """Enter on the card: an unplaced word comes up to sort; a placed one, or one not in the list, shakes the
        card and says so (Enter again adds a word the list does not have)."""
        card = self.word_card
        text = typed_word(text)
        if not text:
            card.end_typing()
            return
        if not any(ch.isalnum() for ch in text):
            card.note("Type a word: letters or numbers", self.anim)
            return
        row = self.store.get_word(text) or self.store.get_word(text.lower())
        if row is not None and row["tier"] is not None:
            card.note(f"Already placed in {TIERS[row['tier']]}  \u00b7  Browse to change it", self.anim)
            return
        if row is None:
            if self._to_add != text:
                self._to_add = text
                card.note("Not in the word list  \u00b7  Enter again to add it", self.anim)
                return
            text = text.lower()                # (the list is all lower case: "Zorp" is the word zorp)
            self.store.add_word(text)
            row = self.store.get_word(text)
            self.flash(f"'{text}' added to the word list", kind="info", ms=1800)
        self._to_add = None
        self.looked_up = row["word"]
        card.end_typing(restore=False)
        self.refresh()

    def _card_note(self, e):
        """The magnifier's hover note."""
        x, y, size = self.word_card.find_box()
        if not (x - 4 <= e.x <= x + size + 4 and y - 4 <= e.y <= y + size + 4):
            return None
        if self.word_card.typing:
            return "Back to the word"
        keys = self.keys.display("find")
        return "Look up a word" + (f" ({keys[0]})" if keys else "")

    def on_mode_change(self):
        """The mode was switched (mode switch, or mode_var set by code): save it and reset any in-progress
        comparison, pair or focus."""
        self.anim.finish(self.duel.anim_key)   # a duel result still showing finishes first (it loads a pair)
        self.mode = self.mode_var.get()
        self.word_card.end_typing()            # (a word half typed on the card is dropped)
        self.mode_switch.set(self.mode)
        self.store.set_meta("mode", self.mode)
        self.cmp = None
        self.pair = None
        self.focus = None
        self._update_options()
        self.refresh()
        self._fit_window()

    # ---- undo ------------------------------------------------------------------------------------------------------------
    def undo(self, saved_only=False):
        """Undo: step back inside an anchor comparison, otherwise revert the last saved action (survives restarts).
        `saved_only` (Ctrl+Z in Browse): always the saved action, never a step inside a comparison."""
        if self.mode == "place" and self.cmp and not saved_only:
            self.cmp_back()
            return
        self.word_card.end_typing()            # (Edit > Undo while typing on the card: the word is back first)
        word = self.store.undo()
        if word is None:
            self.flash("Nothing to undo", kind="info", ms=1500)
            return
        self.session_count = max(0, self.session_count - 1)
        self.cmp = None
        if word == self._was_looked_up and (self.store.get_word(word) or {"tier": 0})["tier"] is None:
            self.looked_up = word              # (a looked-up word comes back where it was: on the card, not the queue)
        self.flash(f"Undid last action ({self.shown(word)})", kind="info", ms=1800)
        self.refresh()

    def shown(self, word):
        """How `word` is written in messages and labels: masked (b\u2022\u2022\u2022\u2022\u2022d) when Censor obscene words
        is on and it is one (ST-6); the big cards smear it instead."""
        return mask_word(word) if self.store.censored(word) else word

    # ---- keys --------------------------------------------------------------------------------------------------------------
    # A held key repeats like a keyboard does (the usual defaults): nothing for REPEAT_DELAY_MS after the first
    # press, then at most one action per REPEAT_INTERVAL_MS. Faster auto-repeats are dropped, so holding a
    # tier key can no longer queue up placements that carry on after it is released.
    REPEAT_DELAY_MS, REPEAT_INTERVAL_MS = 500, 250

    def _repeat_allowed(self, e):
        """False for an auto-repeat of a held key that comes too soon. A held key is recognised on Windows
        (presses with no release between) and on X11 (a release and press with the same timestamp)."""
        ks, now = e.keysym, time.monotonic() * 1000
        h = self._held.get(ks)
        held = h is not None and (h["down"] or (h["release"] is not None and h["release"] == getattr(e, "time", None)))
        if not held:
            self._held[ks] = {"down": True, "release": None, "first": now, "last": now}
            return True
        h["down"] = True
        if now - h["first"] < self.REPEAT_DELAY_MS or now - h["last"] < self.REPEAT_INTERVAL_MS:
            return False
        h["last"] = now
        return True

    def _action_done(self, e):
        """A held key's next repeat waits REPEAT_INTERVAL_MS from when this action finished, not from when it
        started: on a big save an action can take longer than the interval, and the window must still get
        time to draw and answer between repeats."""
        h = self._held.get(e.keysym)
        if h is not None:
            h["last"] = time.monotonic() * 1000

    def on_key_release(self, e):
        h = self._held.get(e.keysym)
        if h is not None:
            h["down"], h["release"] = False, getattr(e, "time", None)

    def on_key(self, e):
        """Every key press: the keymap (UI-48) says what it does in the current view (its own keys first, then the
        Everywhere ones: Backspace is Back while comparing, Undo otherwise). While a word is being typed on the
        card (UI-51) every key is the card's."""
        if self.word_card.typing and self.mode == "place":
            self.word_card.type_key(e)
            return "break"
        if not self._repeat_allowed(e):
            return
        # a key press never waits for an animation: running ones speed out of the way (the new one starts on
        # top), except the duel result, which the next pair waits for
        self.anim.hurry_all(HURRY_MS, finish=(self.duel.anim_key,))
        if self.header.open_name is not None:      # a header menu is open: Escape closes it, nothing else runs
            if e.keysym == "Escape":
                self.header.close()
            return
        spec = spec_of(e, self._ws)
        if spec is None:
            return
        view = ("compare" if self.cmp else "place") if self.mode == "place" else "duel"
        action = self.keys.lookup(view, spec)
        tab = action in ("next_tab", "prev_tab") or e.keysym in ("Tab", "ISO_Left_Tab")
        if action is None:
            return "break" if tab else None        # (no focus traversal in the main window)
        everywhere = {"next_tab": lambda: self.next_tab(1), "prev_tab": lambda: self.next_tab(-1),
                      "defs": self.toggle_defs, "undo": self.undo, "zoom_in": lambda: self.zoom_step(1),
                      "zoom_out": lambda: self.zoom_step(-1), "zoom_reset": lambda: self.set_zoom(1.0)}
        if action in everywhere:
            everywhere[action]()
            self._action_done(e)
            return "break" if tab or action.startswith("zoom") else None
        button, act = self._key_target(action, spec)
        if button is not None and not button.enabled:
            return                                 # a greyed-out button's key is off too
        act()                                      # the action first: input is never delayed (UI-18) ...
        self._action_done(e)
        if button is not None:
            button.flash()                         # ... then the button it stands for dips (not when disabled,
                                                   # not with Reduce motion: RoundButton.flash checks both)
        return "break" if tab else None

    def next_tab(self, d):
        """Go to the next (d=1) or previous (d=-1) tab, wrapping round and skipping hidden ones (UI-47); the
        same as clicking it."""
        keys = [k for k, _ in MODES if k in self.mode_switch.visible]
        i = keys.index(self.mode) if self.mode in keys else 0
        key = keys[(i + d) % len(keys)]
        if key != self.mode:
            self._on_mode_switch(key)

    def _key_target(self, action, spec):
        """(button, action) for a view's own key (UI-18): every hotkey that has a button on screen names it, so
        pressing the key looks like pressing it."""
        if action == "place":
            t = self.keys.place_tier(spec)
            return self.tier_btns[t], lambda: self.place_word(t)
        if action in ("better", "same", "worse"):
            return self.cmp_btns[action], lambda: self.cmp_answer(action)
        if action in ("left", "right", "tie", "skip"):
            return self.duel.buttons[action], lambda: self._on_duel(action)
        return {"compare": (self.compare_btn, self.start_compare), "later": (self.later_btn, self.skip_word),
                "find": (None, self.start_lookup),
                "back": (self.cmp_btns["back"], self.cmp_back), "stop": (None, self._cancel_compare)}[action]

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
        """Redraw the definition pane for the words on screen (pass `words` to change which; no-op when hidden).
        A word clicked in it (W-1) shows instead, under a "Back to ..." line, until then or until the words change."""
        if words is not None:
            if words != self.def_words:
                self.def_lookup = None
            self.def_words = words
        if not self.show_defs:
            return
        back = None
        if self.def_lookup:
            back = ("Back to " + ", ".join(self.shown(w) for w in self.def_words), self._def_back)
        self.def_frame.show_words([self.def_lookup] if self.def_lookup else self.def_words, self.get_def,
                                  self.store.censored,
                                  self.store.smeared_meanings if self.store.deal_settings()["censor"] else None,
                                  on_word=self._def_clicked, back=back, link=self.wiktionary_link())
        self._fit_defs()

    # ---- the word's Wiktionary page, from a definition (asked for: its etymology and the rest) ------------------
    ONLINE_POLL_MS = 3000

    def wiktionary_link(self):
        """What a definitions pane's link opens with (open_wiktionary), or None while Wiktionary cannot be reached."""
        return self.open_wiktionary if self.online.online else None

    def open_wiktionary(self, word):
        """Open `word`'s Wiktionary page in the browser."""
        try:
            webbrowser.open(wiktionary_url(word), new=2)
        except Exception:                       # (no browser to open: say where it is)
            self.flash(f"No web browser could be opened: {wiktionary_url(word)}", kind="warn", ms=6000)

    def _watch_online(self):
        """Every few seconds: when the connection comes or goes, the definitions panes show or hide the link."""
        now = self.online.online
        if now != self._was_online:
            self._was_online = now
            self._render_defs()
            for b in self.browsers:
                if b.alive():
                    b.render_def()
        self.root.after(self.ONLINE_POLL_MS, self._watch_online)

    # ---- looking a word up from a definition (W-1) -------------------------------------------------------------
    def look_up(self, word, parent=None):
        """A word clicked in a definition (the drawer, or Browse's pane): True if it is in the word list, and then
        it waits in Browse for the moment (self.lookups, shown at the bottom until Browse refreshes or closes, so it
        can be placed there). A word the list does not have is offered to add first; no keeps it out."""
        if not self.store.has_word(word):
            if not ask_yes_no("Look up a word", f"'{self.shown(word)}' is not in the word list",
                              "Add it, so you can sort it in Browse? Its definition shows either way.",
                              yes="Add it", no="Just show it", parent=parent or self.root):
                return False
            self.store.add_word(word)
            self.flash(f"'{self.shown(word)}' added to the word list", kind="info", ms=1800)
        if word not in self.lookups:
            self.lookups.append(word)
        return True

    def _def_clicked(self, word):
        """A word clicked in the main window's definitions: shown there in their place, and waiting in Browse."""
        if self.look_up(word):
            for bw in self.browsers:
                if bw.alive():
                    bw.show_lookups()
            row = self.store.get_word(word)
            if row is not None and row["tier"] is None:
                self.flash(f"'{self.shown(word)}' is in Browse for now, at the bottom, to sort it", kind="info",
                           ms=2200)
        self.def_lookup = word
        self._render_defs()

    def _def_back(self):
        """The definitions' "Back to ..." line: the words on screen again."""
        self.def_lookup = None
        self._render_defs()

    DEF_LINES, DEF_LINES_MAX = 9, 40     # the definition pane's usual height in lines, and the most it asks for

    def _fit_defs(self):
        """Make the definition pane tall enough to show every sense on it (UI-56), growing the window if the
        screen has room; where it has not, _fit_window gives the pane what fits. The pane only grows from word
        to word (shrinking back for each short definition would make the page jump on every word); it goes
        back to its usual height when it is closed."""
        for _ in range(3):             # a taller window may grow the fonts (UI-25), and the text then needs more
            want = min(self.DEF_LINES_MAX, max(self.DEF_LINES, self.def_frame.lines_needed()))
            if want <= self._def_want:
                return
            self._def_want = want
            if not self.def_frame.is_open:   # about to slide open: _layout_defs makes room for it at this height
                self.def_frame.set_lines(want)
                return
            self.def_frame.settle()          # (a definition arriving while it slides open: fitted against the
            self._fit_window()               # half-open pane, it ended taller than fits, over the word card)

    # ---- Wiktionary's meanings for a save without them (OB-6), read in the background ------------------------
    def _start_rude_read(self):
        """A save from before OB-6 (or from a word list) keeps no Wiktionary meanings for the rudeness rules: read
        them once in the background (a 3 GB download, resumable), then score and save them a little at a time.
        Until then the words smeared before (and the short hand-picked list) stand in."""
        if not wordsource.wants_rude_fetch(self.store):
            return
        self.store.set_meta("rude_tried", time.time())
        state = self.rude_read = {"line": "", "result": None, "error": None}
        path = self.store.path

        def work():                                  # (no tkinter, and its own read-only connection)
            try:
                db = sqlite3.connect(f"file:{os.path.abspath(path)}?mode=ro", uri=True)
                try:
                    words = {r[0] for r in db.execute("SELECT word FROM words")}
                finally:
                    db.close()
                log = lambda text: state.__setitem__("line", text)      # noqa: E731
                saved = wordsource.fetch_rude_senses(path, words, log)
                log("Scoring rude meanings (100%)")
                state["result"] = (saved, wordsource.find_rude(words, saved, log=log))
            except Exception as exc:                 # offline, disk full, ...: tried again later (RUDE_RETRY_S)
                state["error"] = str(exc) or type(exc).__name__
        threading.Thread(target=work, daemon=True).start()
        self.root.after(2000, self._poll_rude_read)

    def rude_read_note(self):
        """How far the background read has come ("12%"), or None when none is running (How words are dealt)."""
        if not self.rude_read:
            return None
        m = re.search(r"\((\d+)%\)", self.rude_read["line"])
        return m.group(1) + "%" if m else "starting"

    def _poll_rude_read(self):
        state = self.rude_read
        if state["error"]:
            self.rude_read = None
            return
        if state["result"] is None or self.busy:
            self.root.after(2000, self._poll_rude_read)
            return
        saved, found = state["result"]
        steps = [self.store.save_rude_senses(saved, chunk=4000), self.store.set_rude(found, chunk=4000)]

        def tick():                                  # a few thousand rows a frame, never while a reshuffle writes
            if not self.busy:
                if next(steps[0], StopIteration) is StopIteration:
                    steps.pop(0)
                    if not steps:
                        self.store.set_meta("rude_done", rudeness.RUDENESS_VERSION)
                        self.rude_read = None
                        self.after_external_change()
                        self.flash("Rude meanings read from Wiktionary", ms=2500)
                        return
            self.root.after(15, tick)
        tick()

    def _poll_defs(self):
        """Every 120 ms: collect finished lookups, cache them in the save, and redraw the panes that show them."""
        if self.busy:                          # a reshuffle is writing the save: collect them afterwards
            self.root.after(120, self._poll_defs)
            return
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

    # ---- anchors ----------------------------------------------------------------------------------------------
    @property
    def anchors(self):
        """The six anchor words (None for an empty slot), read from the save: they can change under us (UI-40)."""
        return self.store.get_anchors()

    def note_anchor_changes(self, changes):
        """A short message for each anchor that moved and handed its tier's anchor on (UI-40)."""
        for word, old, new_tier, new in changes:
            where = f"moved to {TIERS[new_tier]}" if new_tier is not None else "left its tier"
            then = (f"the {TIERS[old]} anchor is now {self.shown(new)}" if new else
                    f"tier {TIERS[old]} has no anchor until you pick one (Settings)")
            self.flash(f"{self.shown(word)} {where}; {then}", bg=TIER_COLORS[old], fg=TIER_TEXT, ms=3500)

    # ---- dialogs / misc -------------------------------------------------------------------------------------------------------------
    def _click_background(self, e):
        """A click on the main window's empty background (a bare frame, not a pill, card, button, label or the
        shelf) closes the Browse window (UI-38), so a quick click on something never loses your place."""
        if not self.browsers or type(e.widget) not in (tk.Tk, tk.Frame, ttk.Frame):
            return                     # (exactly a frame: the tier pills' row and other widgets are frames too)
        for bw in list(self.browsers):
            if bw.alive():
                bw.close()

    def open_browser(self):
        """Open the Browse window, or raise it if one is already open."""
        for bw in self.browsers:
            if bw.alive():
                bw.win.lift()
                return
        Browser(self)

    def edit_anchors(self):
        """Dialog to choose the six anchor words (UI-28): a pill per tier, and any problem (empty, used twice,
        not in the word list) shown as a note under its own field."""
        dlg = StyledDialog(self.root, "Anchor words", "Anchor words",
                           "One familiar word per tier. New words are compared against these to find their "
                           "tier in a few questions.", animator=self.anim, wrap_chars=40)
        current = self.store.get_anchors()
        vars_, notes = [], []
        for t in range(len(TIERS)):
            pre = current[t] or (DEFAULT_ANCHORS[t] if self.store.has_word(DEFAULT_ANCHORS[t]) else "")
            TierChip(dlg.body, TIERS[t], TIER_COLORS[t], font("head")).grid(row=2 * t, column=0, padx=(0, 12),
                                                                           pady=(6, 0))
            v = tk.StringVar(value=pre)
            entry = ttk.Entry(dlg.body, textvariable=v, width=24, font=font("body"))
            entry.grid(row=2 * t, column=1, sticky="we", pady=(6, 0), ipady=2)
            if t == 0:
                entry.focus_set()
            note = ttk.Label(dlg.body, text="", foreground=PALETTE["bad"][1])     # shown only with a problem
            v.trace_add("write", lambda *_, n=note: n.grid_remove())                # editing clears it
            vars_.append(v)
            notes.append(note)
        dlg.body.columnconfigure(1, weight=1)

        def problems(words):
            """{field index: note} for every field that needs fixing."""
            out = {}
            for i, w in enumerate(words):
                if not w:
                    out[i] = "Fill this one in"
                elif words.count(w) > 1:
                    out[i] = "Used twice: each tier needs its own word"
                elif not self.store.has_word(w):
                    out[i] = "Not in the word list"
            return out

        def save():  # validate, store the anchors and close
            words = [v.get().strip().lower() for v in vars_]
            found = problems(words)
            for i, note in enumerate(notes):
                if i in found:
                    note.config(text=found[i])
                    note.grid(row=2 * i + 1, column=1, sticky="w")
                else:
                    note.grid_remove()
            if found:
                dlg.refit()
                return
            self.store.set_anchors(words)
            dlg.close()
            self.after_external_change()

        dlg.button("Cancel", dlg.close)
        dlg.button("Save anchors", save, default=True)
        dlg.show()
        return dlg

    @staticmethod
    def parse_queue_settings(seed_text, spread_text, shape, compound_text):
        """Check the order fields of How words are dealt (seed, spread, shape, compound strength). Returns (settings for Store.reshuffle, None) or (None, error)."""
        try:
            seed = int(seed_text.strip())
            spread = float(spread_text.strip().replace(",", ""))
            compound = float(compound_text.strip())
        except ValueError:
            return None, "Seed must be a whole number; spread and compound strength must be numbers."
        if spread < 100:
            return None, "Spread must be at least 100 (it is measured in frequency ranks)."
        if not 0 <= compound <= 10:
            return None, "Compound strength must be between 0 (off) and 10."
        if shape not in QUEUE_SHAPES:
            return None, "Pick a shape."
        return {"seed": seed, "spread": spread, "shape": shape, "compound": compound}, None

    def queue_unchanged(self, cfg):
        """True if `cfg` (from parse_queue_settings) is what the save already uses."""
        cur = self.store.queue_settings()
        return (cfg["seed"] == cur["seed"] and cfg["shape"] == cur["shape"]
                and abs(cfg["spread"] - cur["spread"]) < 1e-9 and abs(cfg["compound"] - cur["compound"]) < 1e-9)

    def add_launcher(self):
        """File > Add to applications menu (Linux, ST-5): a launcher that starts the program with no terminal."""
        try:
            path, how = deps.add_to_menu(sys.executable, None if is_frozen() else os.path.join(SCRIPT_DIR, "tierlist.py"))
        except OSError as exc:
            show_exception("Applications menu", exc, self.root, "Could not add Word Tier List to the applications menu.")
            return
        text = ("Word Tier List added to your applications menu (it starts without a terminal)" if how == "added"
                else "Word Tier List updated in your applications menu")
        self.flash(text, kind="info", ms=2600)
        return path

    def source_updates(self):
        """File > Source & Updates... (T-6, T-7): from source, make a standalone program for this computer; in the
        program, unpack the source code it was built from."""
        return SourceDialog(self)

    def edit_tier_colours(self):
        """Settings > Tier colours... (UI-61)."""
        return TierColoursDialog(self)

    def toggle_dark(self):
        """View > Dark mode (UI-62, not the default): saved, and the window reopens in it."""
        self.store.set_meta("dark_mode", "1" if self.dark_var.get() else "0")
        self.reopen()

    def edit_keys(self):
        """Settings > Keyboard shortcuts... (UI-48)."""
        return ShortcutsDialog(self)

    def edit_dealing(self, first=False, on_done=None):
        """Settings > How words are dealt... (ST-6; it grew out of Queue randomness): the order new words come in,
        which kinds of words, censoring obscene ones. `first`: the three-step version for the first start."""
        self._dealing = DealDialog(self, first=first, on_done=on_done)
        return self._dealing

    # ---- earlier progress ------------------------------------------------------------------------
    def show_save_location(self):
        """File > Where is my save file?"""
        show_message(
            "Save file", "Where your progress is saved",
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
        """File > Import earlier progress: pick a save file or export and merge it in. On Linux the app's own
        picker (filepicker.py, UI-42: what it found first, a browser behind it); elsewhere the system's."""
        if use_themed(self.root):
            path = ask_import(self.root, self.store.path, SCRIPT_DIR, animator=self.anim)
        else:
            path = filedialog.askopenfilename(
                parent=self.root, title="Import earlier progress",
                filetypes=[("Tier list save or export", "*.db *.csv *.txt *.md"), ("All files", "*.*")])
        if not path:
            return
        ok, text = self.merge_file(path)
        if ok:
            show_message("Import earlier progress", "Earlier progress brought in", text, parent=self.root)
        else:
            show_error("Import earlier progress", text, parent=self.root, headline="That file could not be imported")
        self.after_external_change()

    def offer_merge(self, others):
        """Other save files with progress were found: offer (once per file) to merge them in."""
        done = set(json.loads(self.store.get_meta("merge_prompted", "[]")))
        todo = [o for o in others if o["key"] not in done]
        if not todo:
            return
        lines = "\n".join(f"   {o['path']}   ({o['placed']:,} placed, {o['skipped']:,} skipped)" for o in todo)
        yes = ask_yes_no(
            "Merge your earlier progress?", "Merge your earlier progress?",
            f"Found other tier list save files with progress:\n\n{lines}\n\n"
            f"Merge their progress into the list you're using now?\n\n   {self.store.path}\n\n"
            "Nothing already placed here is overwritten, the other files are not changed, and a "
            "backup of this list is saved first. You can also do this later from "
            "File > Import earlier progress.", yes="Merge", no="Not now", parent=self.root, wrap_chars=70)
        self.store.set_meta("merge_prompted", json.dumps(sorted(done | {o["key"] for o in todo})))
        if not yes:
            self.flash("Not merged. You can do it any time from File > Import earlier progress...", ms=8000)
            return
        msgs = [self.merge_file(o["path"], backup=(i == 0))[1] for i, o in enumerate(todo)]
        self.after_external_change()
        show_message("Merged", "Your earlier progress is merged in", "\n\n".join(msgs), parent=self.root)

    def export(self):
        """File > Export tier list: write the placed words (and skipped ones) to .txt, .csv or .md. On Linux the
        app's own dialog (UI-42: name, format, folder; the folder and format are remembered)."""
        if use_themed(self.root):
            folder = self.store.get_meta("export_dir") or ""
            if not os.path.isdir(folder):
                docs = os.path.join(os.path.expanduser("~"), "Documents")
                folder = docs if os.path.isdir(docs) else os.path.expanduser("~")
            path, kind, folder = ask_export(self.root, folder, kind=self.store.get_meta("export_kind", "txt"),
                                            save_dir=os.path.dirname(os.path.abspath(self.store.path)),
                                            animator=self.anim)
            if path:
                self.store.set_meta("export_dir", folder)
                self.store.set_meta("export_kind", kind)
        else:
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

    reopening = False         # set by reopen(): main() builds the window again, in the look now chosen
    _browse_was_open = False
    _old = None               # the window this one replaces (take_over), until it is closed

    def _drop_old(self):
        """Close the window this one replaced (its save stays open: it is this one's)."""
        old, self._old = self._old, None
        if old is not None:
            try:
                old._shut(close_store=False)
            except tk.TclError:
                pass

    def take_over(self, old):
        """Become the window `old` was (reopening in a new look): its place and size, maximized or not, the word
        looked up on its card and its Browse window (closed there, opened here as it was)."""
        try:
            maximized = is_maximized(old.root)
            geometry = old.root.geometry()
        except tk.TclError:
            return
        self.root.geometry(geometry)
        if maximized:
            try:
                self.root.state("zoomed")            # (Windows, macOS)
            except tk.TclError:
                try:
                    self.root.attributes("-zoomed", True)     # (Linux)
                except tk.TclError:
                    pass
        self._old = old
        self.looked_up = old.looked_up
        for bw in list(old.browsers):
            if bw.alive():
                bw.close()                           # (it saves what it showed: browse_state)
        self.browse_state = old.browse_state
        self.refresh()
        if old._browse_was_open:
            self.root.after(150, self.open_browser)

    def reopen(self):
        """Close this window but keep the save open: main() builds it again at once, so a new look (dark mode, the
        tier colours: UI-61, UI-62) shows everywhere. Waits while a long job writes the save, as on_close."""
        if self.busy:
            self.root.after(200, self.reopen)
            return
        self.reopening = True
        for bw in self.browsers:                 # (a Browse window open now opens again in the new look)
            if bw.alive():
                self._browse_was_open = True
        self.root.after(0, self.root.quit)       # (main() builds the new window over this one, then closes it;
                                                 # from the event loop: a quit asked before it runs is forgotten)

    def on_close(self):
        """Close the save cleanly and quit. While a long job writes the save (a reshuffle: App.busy) it waits for
        it to finish (closing then would shut the save under the worker thread). Timers still waiting are dropped
        first, so none fires into a window that is gone (each was logged as an error at every quit)."""
        if self.busy:
            self.root.after(200, self.on_close)
            return
        self._shut(close_store=True)

    def _shut(self, close_store):
        self.online.stop()
        self._drop_old()                         # (closed before the window it replaced was: that one goes too)
        for bw in list(self.browsers):
            if bw.alive():
                bw.close()
        self.anim.cancel_all()
        try:
            for job in self.root.tk.splitlist(self.root.tk.call("after", "info")):
                self.root.tk.call("after", "cancel", job)   # (not after_cancel: it frees a command its widget
                                                            # still lists, and destroy then fails freeing it again)
        except tk.TclError:
            pass
        if close_store:
            self.store.close()
        self.root.destroy()
