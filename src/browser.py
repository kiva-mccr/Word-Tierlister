"""The Browse / edit window: searchable, scalable, lazily-loaded list of every word.

One Browser per window; the App keeps them in app.browsers so it can refresh them all after a change.
Layout, top to bottom: search/filter/sort bar, the word table (Treeview), "Move to" buttons,
a definition pane. How it stays fast with ~1M words:
    * rows are fetched CHUNK at a time and the next page loads when you scroll near the bottom
      (_yscroll -> _load_more), so there is no row limit;
    * typing in the search box waits 200 ms (_debounce) before querying;
    * the window re-queries only when store.version has changed since it last loaded.
Text and row height scale with the window size (_apply_scale); Ctrl +/-/0 and Ctrl+wheel zoom.
"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from constants import TIERS
from errors import show_message
from fonts import family, font
from sizing import center_geometry, fit_size, ui_factor, usable_area
from store import Store
from theme import PALETTE, TIER_COLORS, TIER_ROW, TIER_TEXT
from widgets import ChoiceButton, RoundButton, Toast, refresh_widgets


class Browser:
    """Search / browse / edit window. Text and row height scale with the window; rows load as you scroll."""

    CHUNK = 3000                 # rows fetched per page; the next page loads when you scroll near the end
    BASE_W, BASE_H = 980, 760    # window size at which the text is 12 pt (it grows/shrinks from there)
    OPEN_MS, OPEN_FROM = 150, 0.94   # opening: it eases out from this share of its size, round its centre (UI-38)
    # ...except on Linux (X11), where each step of the ease re-lays out the whole window under a window manager
    # that redraws its frame a beat later, and the rows popped in afterwards: it read as a bounce (M-5). There
    # it opens complete and still. None = automatic; True / False force it (tests).
    EASE_OPEN = None

    def __init__(self, app):
        """Build the window and load the first page of rows. `app` is the main App (store, fonts, definitions)."""
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title("Browse & edit tier list")
        # base_w/base_h: the window size at which the text is 12 pt (the reference scaled for dpi, then
        # raised to what the contents need in _fit_to_contents). On a small screen the window opens
        # smaller than that, so the text starts proportionally smaller (it keeps scaling with resizes).
        f = ui_factor(app.root)
        self.base_w, self.base_h = int(self.BASE_W * f), int(self.BASE_H * f)
        app.browsers.append(self)
        self._job = None
        self._scale_job = None
        self.current = None
        self.loaded = self.total = 0
        self._count_digits = None                 # digits in the total the minimum size was last set for
        self._seen_version = -1
        self._loading = False
        self._toast = None                         # the zoom message (_say_zoom)
        self._opening = True                       # easing open; the list fills when it ends (_open_animation)
        self.fsize = 0
        try:
            self.zoom = max(-4, min(30, int(app.store.get_meta("browse_zoom", "0"))))
        except ValueError:
            self.zoom = 0

        # Shared fonts: resizing these two updates every widget that uses them at once.
        self.f_body = tkfont.Font(family=family(), size=12)
        self.f_bold = tkfont.Font(family=family(), size=12, weight="bold")
        self.sid = f"Br{id(self)}"
        self.style = ttk.Style(self.win)
        self.tstyle = f"{self.sid}.Treeview"
        self.style.configure(self.tstyle, font=self.f_body)
        self.style.configure(self.tstyle + ".Heading", font=self.f_bold)
        self.style.configure(f"{self.sid}.TLabel", font=self.f_body)
        self.style.configure(f"{self.sid}.Bar.TLabel", font=self.f_body, background=PALETTE["surface"])
        self.style.configure(f"{self.sid}.Muted.TLabel", font=self.f_body, foreground=PALETTE["muted"])
        anim, surf = self.app.anim, PALETTE["surface"]

        # the toolbar sits on a white band with a hairline under it, like the main window's header (UI-23)
        top = self.top_bar = tk.Frame(self.win, bg=surf, padx=10, pady=8)
        top.pack(fill="x")
        tk.Frame(self.win, height=1, bg=PALETTE["border"]).pack(fill="x")
        ttk.Label(top, text="Search:", style=f"{self.sid}.Bar.TLabel").pack(side="left")
        self.search_var = tk.StringVar()
        entry = self.entry = ttk.Entry(top, textvariable=self.search_var, width=18, font=self.f_body)
        entry.pack(side="left", padx=6)
        self.search_var.trace_add("write", lambda *_: self._debounce())
        ttk.Label(top, text="Show:", style=f"{self.sid}.Bar.TLabel").pack(side="left", padx=(10, 0))
        self.filter_var = tk.StringVar(value="All placed")
        ChoiceButton(top, self.filter_var, ["All placed"] + [f"Tier {t}" for t in TIERS] + ["Unplaced"],
                     on_change=self.reload, font=self.f_body, animator=anim, canvas_bg=surf).pack(side="left", padx=6)
        ttk.Label(top, text="Sort:", style=f"{self.sid}.Bar.TLabel").pack(side="left", padx=(10, 0))
        self.sort_var = tk.StringVar(value="Default")
        ChoiceButton(top, self.sort_var, list(Store.SORTS), on_change=self.reload, font=self.f_body,
                     animator=anim, canvas_bg=surf).pack(side="left", padx=6)
        for text, delta in (("A+", 1), ("A-", -1)):
            RoundButton(top, text, lambda d=delta: self.zoom_by(d), font=self.f_body, padx=8, pady=4, radius=10,
                        flat=True, animator=anim, canvas_bg=surf).pack(side="right", padx=(2, 0))
        self.count_lbl = ttk.Label(top, text="", style=f"{self.sid}.Bar.TLabel", foreground=PALETTE["muted"])
        self.count_lbl.pack(side="right", padx=10)

        mid = ttk.Frame(self.win)
        mid.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        self.vsb = ttk.Scrollbar(mid, orient="vertical")
        self.tree = ttk.Treeview(mid, columns=("tier", "word", "rating", "games", "freq"),
                                 show="headings", selectmode="browse", style=self.tstyle,
                                 yscrollcommand=self._yscroll)
        self.vsb.configure(command=self.tree.yview)
        for col, text, anchor in (("tier", "Tier", "center"), ("word", "Word", "w"),
                                  ("rating", "Rating", "e"), ("games", "Duels", "e"),
                                  ("freq", "Freq #", "e")):
            self.tree.heading(col, text=text)
            self.tree.column(col, anchor=anchor)
        for t in range(len(TIERS)):
            self.tree.tag_configure(f"t{t}", background=TIER_ROW[t], foreground=TIER_TEXT)
        self.tree.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        # Selection is shown as an outline round the row (the row keeps its tier colour). Treeview
        # cannot draw per-row borders, so four thin frames are placed over the selected row's box.
        self._outline = [tk.Frame(self.tree, bg=PALETTE["accent_text"]) for _ in range(4)]
        self.tree.bind("<<TreeviewSelect>>", lambda e: (self._on_select(), self._draw_outline()))
        self.tree.bind("<Configure>", lambda e: self._draw_outline(), add="+")
        self.tree.bind("<Double-1>", lambda e: self.refine())

        btns = self.btn_bar = ttk.Frame(self.win, padding=(10, 8))
        btns.pack(fill="x")
        ttk.Label(btns, text="Move to:", style=f"{self.sid}.TLabel").pack(side="left")
        for t in range(len(TIERS)):
            RoundButton(btns, TIERS[t], lambda t=t: self.move(t), bg=TIER_COLORS[t], font=self.f_bold,
                        padx=10, pady=3, radius=10, animator=anim).pack(side="left", padx=2)
        for text, command, padx in (("Unplace (back to queue)", self.unplace, (12, 4)),
                                    ("Refine this word", self.refine, (4, 0))):
            RoundButton(btns, text, command, bg=surf, font=self.f_body, padx=12, pady=3, radius=10,
                        animator=anim).pack(side="left", padx=padx)
        RoundButton(btns, "Refresh", lambda: self.reload(keep_view=True), font=self.f_body, padx=12, pady=3,
                    radius=10, flat=True, animator=anim).pack(side="right")

        # the definition: a muted heading over a white pane with a hairline (no grooved frame)
        ttk.Label(self.win, text="Definition", style=f"{self.sid}.Muted.TLabel").pack(anchor="w", padx=12)
        self.def_text = tk.Text(self.win, height=7, wrap="word", state="disabled", font=self.f_body,
                                padx=10, pady=8)
        self.def_text.tag_configure("head", font=self.f_bold)
        self.def_text.pack(fill="x", padx=10, pady=(2, 10))

        # Ctrl + / Ctrl - / Ctrl 0 and Ctrl+mouse wheel zoom the text.
        for seq, delta in (("<Control-plus>", 1), ("<Control-equal>", 1), ("<Control-KP_Add>", 1),
                           ("<Control-minus>", -1), ("<Control-KP_Subtract>", -1), ("<Control-0>", 0),
                           ("<Control-KP_0>", 0)):
            self.win.bind(seq, lambda e, d=delta: self.zoom_by(d))
        for widget in (self.win, self.tree):
            widget.bind("<Control-MouseWheel>", self._wheel_zoom)
            widget.bind("<Control-Button-4>", lambda e: self._wheel_zoom(e, 1))
            widget.bind("<Control-Button-5>", lambda e: self._wheel_zoom(e, -1))
        # Delete unplaces the selected word, like the Unplace button (UI-39; Backspace too on macOS, where the
        # key marked delete sends it); Ctrl+Z undoes it from here. Not while typing in the search box.
        keys = ["<Delete>", "<KP_Delete>"] + (["<BackSpace>"] if self.win.tk.call("tk", "windowingsystem") == "aqua"
                                                 else [])
        for seq in keys:
            self.tree.bind(seq, lambda e: (self.unplace(), "break")[1])
        for seq in ("<Control-z>", "<Command-z>"):
            self.win.bind(seq, lambda e: self.undo())
        self.win.bind("<Configure>", self._on_configure)
        self.win.bind("<FocusIn>", lambda e: self._maybe_refresh() if e.widget is self.win else None)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self._fit_to_contents()
        self._apply_scale()
        entry.focus_set()
        state = getattr(app, "browse_state", None)
        # the rows load once the window has eased open: re-laying out a full list on every frame of the ease
        # made it stutter (40-60 ms a frame)
        self._open_animation(lambda: self._restore(state) if state else self.reload())

    # ---- window lifecycle ---------------------------------------------------------------------
    @property
    def store(self):
        """The shared Store (always the app's current one)."""
        return self.app.store

    def alive(self):
        """False once the window has been destroyed (the App uses this to skip dead windows)."""
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def close(self):
        """Unregister from the App and destroy the window. What you were looking at (search, Show, Sort, the
        selected word, how far you had scrolled) is kept for the next open, so closing by accident costs
        nothing (UI-38; for this run of the program only)."""
        if self in self.app.browsers:
            self.app.browsers.remove(self)
        try:
            self.app.browse_state = {"search": self.search_var.get(), "filter": self.filter_var.get(),
                                     "sort": self.sort_var.get(), "selected": self.current,
                                     "loaded": self.loaded, "view": self.tree.yview()[0]}
        except tk.TclError:
            pass
        self.win.destroy()

    def _restore(self, state):
        """Open where the last Browse window was closed (see close)."""
        self.search_var.set(state["search"])
        if self._job:                                # (setting the search text started the typing timer)
            self.win.after_cancel(self._job)
            self._job = None
        self.filter_var.set(state["filter"])
        self.sort_var.set(state["sort"])
        self.current, self.loaded = state["selected"], state["loaded"]
        self.reload(keep_view=True, view=state["view"])
        if self.current and self.tree.exists(self.current):
            self.render_def()

    def _open_animation(self, then):
        """Ease the window out from slightly smaller round its centre (about 150 ms; none with Reduce motion),
        then call then() (which fills the list). The text is not re-scaled meanwhile: that waits for the size
        to settle (_on_configure)."""
        anim = self.app.anim
        try:
            w, h, x, y = (int(v) for v in self.win.geometry().replace("x", "+").split("+"))
        except ValueError:
            w = 0
        ease = self.EASE_OPEN
        if ease is None:
            ease = self.win.tk.call("tk", "windowingsystem") != "x11"
        if anim.reduce_motion or not w or not ease:
            self._opening = False
            then()                                   # (before the window is first drawn: it appears full)
            return
        cx, cy = x + w / 2, y + h / 2

        def frame(p):
            k = self.OPEN_FROM + (1 - self.OPEN_FROM) * p
            ww, hh = int(round(w * k)), int(round(h * k))
            try:
                self.win.geometry(f"{ww}x{hh}+{int(round(cx - ww / 2))}+{int(round(cy - hh / 2))}")
            except tk.TclError:
                pass                                 # closed while opening
        frame(0.0)                                   # it first appears at the small size...

        def start(e=None):
            self.win.unbind("<Map>")
            # ...and the clock starts once it is on screen and drawn: the first draw of a full list takes a
            # while, and an ease timed from before it was over before anyone saw it
            self.win.after_idle(lambda: self.win.after(0, lambda: anim.run(f"browse-open{id(self)}",
                                                                          self.OPEN_MS, frame, done)))

        def done():
            self._opening = False
            if self.alive():
                then()
        if self.win.winfo_ismapped():
            start()
        else:
            self.win.bind("<Map>", start)

    # ---- scaling ------------------------------------------------------------------------------------
    def _on_configure(self, e):
        """Window resized: re-scale the text, but only after resizing pauses for 80 ms."""
        if e.widget is not self.win:
            return
        if self._scale_job:
            self.win.after_cancel(self._scale_job)
        self._scale_job = self.win.after(80, self._apply_scale)

    def _apply_scale(self):
        """Text size follows the window size (12 pt at the starting size), plus the manual zoom."""
        self._scale_job = None
        try:
            w, h = self.win.winfo_width(), self.win.winfo_height()
        except tk.TclError:
            return
        if w < 100 or h < 100:  # not mapped yet
            w, h = self.base_w, self.base_h
        size = max(8, min(64, int(round(12 * min(w / self.base_w, h / self.base_h))) + self.zoom))
        if size == self.fsize:
            return
        self.fsize = size
        self.f_body.configure(size=size)
        self.f_bold.configure(size=size)
        # Row height must be set explicitly: the tree does not derive it from the font.
        self.style.configure(self.tstyle, rowheight=int(self.f_body.metrics("linespace") * 1.5) + 6)
        self._set_columns()
        refresh_widgets(self.win)                   # the tier buttons and Show / Sort use the shared fonts
        self._update_minsize()

    def _col_widths(self):
        """Column widths in pixels, measured from the current fonts so headings and numbers never clip."""
        m, b = self.f_body.measure, self.f_bold.measure
        pad = m("0") * 2
        return {
            "tier": max(b("Tier"), m("S")) + pad * 2,
            "word": m("0") * 22,
            "rating": max(b("Rating"), m("0000")) + pad,
            "games": max(b("Duels"), m("0000")) + pad,
            "freq": max(b("Freq #"), m("000,000,000")) + pad,
        }

    def _set_columns(self):
        for col, width in self._col_widths().items():
            self.tree.column(col, width=width, stretch=(col == "word"))

    def _needed_size(self):
        """(width, height) the contents need right now: the toolbar rows, the columns, a few rows of list."""
        self.win.update_idletasks()
        cols = self._col_widths()
        tree_w = sum(cols.values()) - cols["word"] + cols["word"] // 2 + self.vsb.winfo_reqwidth() + 16
        # the word count changes length as rows load; leave room for its longest form so it never clips
        count_w = self.f_body.measure(self._longest_count()) + 4
        top_w = self.top_bar.winfo_reqwidth() - self.count_lbl.winfo_reqwidth() + count_w
        w = max(top_w, self.btn_bar.winfo_reqwidth(), tree_w)
        row_h = int(self.f_body.metrics("linespace") * 1.5) + 6
        fixed = sum(x.winfo_reqheight() for x in self.win.pack_slaves() if x is not self.tree.master)
        return w, fixed + row_h * 8 + 16

    def _update_minsize(self):
        area = usable_area(self.app.root)
        nw, nh = self._needed_size()
        self.win.minsize(min(nw, area[2]), min(nh, area[3]))

    def _fit_to_contents(self):
        """First sizing, once the widgets exist: at the 12 pt reference text, make sure the preferred
        size is not smaller than what the toolbars and columns need, then place the window."""
        self.fsize = 12
        self.f_body.configure(size=12)
        self.f_bold.configure(size=12)
        self.style.configure(self.tstyle, rowheight=int(self.f_body.metrics("linespace") * 1.5) + 6)
        self._set_columns()
        refresh_widgets(self.win)
        area = usable_area(self.app.root)
        nw, nh = self._needed_size()
        self.base_w, self.base_h = max(self.base_w, nw + 20), max(self.base_h, nh + 20)
        w, h = fit_size((min(nw, area[2]), min(nh, area[3])), (self.base_w, self.base_h), (area[2], area[3]))
        self.win.geometry(center_geometry(w, h, area))
        self._update_minsize()
        self.fsize = 0                                         # force the first _apply_scale to run

    def zoom_by(self, delta):
        """Manual text zoom on top of the automatic scaling (0 resets). Saved with the save file."""
        self.zoom = 0 if delta == 0 else max(-4, min(30, self.zoom + delta))
        self.store.set_meta("browse_zoom", self.zoom)
        self._apply_scale()
        self._say_zoom()
        return "break"

    def _say_zoom(self):
        """'Zoom 100%' (the manual zoom against the 12 pt text) at the bottom of the definition pane, every time
        a zoom key is pressed, even when nothing changed (M-6). One message, replaced by the next."""
        if self._toast is None:
            self._toast = Toast(self.win, font("label"), animator=self.app.anim, page_bg=PALETTE["surface"])
        self._toast.show(f"Zoom {round((12 + self.zoom) / 12 * 100)}%", (PALETTE["info"][0], PALETTE["info"][1]),
                         ms=900, in_=self.def_text)

    def _wheel_zoom(self, e, direction=None):
        """Ctrl+mouse-wheel zoom. Windows/macOS give e.delta; X11 passes `direction` from Button-4/5."""
        if direction is None:
            direction = 1 if e.delta > 0 else -1
        self.zoom_by(direction)
        return "break"

    # ---- loading rows -----------------------------------------------------------------------------------
    def _debounce(self):
        """Restart the 200 ms timer that reloads the list after the search text stops changing."""
        if self._job:
            self.win.after_cancel(self._job)
        self._job = self.win.after(200, self.reload)

    def _maybe_refresh(self):
        """Reload (keeping the scroll position) if anything changed in the save since the last load. Not while
        the window is still opening: the list fills when the ease ends (a load mid-ease made it stutter)."""
        if self._opening:
            return
        if self.store.version != self._seen_version:
            self.reload(keep_view=True)

    def _query(self, **kw):
        """Ask the Store for a page of words using the current search text, tier filter and sort."""
        return self.store.list_words(self.search_var.get().strip().lower(), self.filter_var.get(),
                                     self.sort_var.get(), **kw)

    def _add_rows(self, rows):
        """Append rows to the table, colouring placed words by tier. The word itself is the row id."""
        for r in rows:
            tier = "-" if r["tier"] is None else TIERS[r["tier"]]
            tags = () if r["tier"] is None else (f"t{r['tier']}",)
            try:
                self.tree.insert("", "end", iid=r["word"], tags=tags, values=(
                    tier, r["word"], "" if r["tier"] is None else f"{r['rating']:.0f}",
                    r["games"], f"{r['rank'] + 1:,}"))
            except tk.TclError:  # the same word arriving twice because the list changed under us
                pass

    def _clear_tree(self):
        """Empty the table (in slices, which is much faster than one huge delete)."""
        kids = self.tree.get_children()
        for i in range(0, len(kids), 2000):
            self.tree.delete(*kids[i:i + 2000])

    def _longest_count(self):
        """The longest text the word count can show for the current total (for the minimum size)."""
        t = max(self.total, 1)
        return f"{t:,} of {t:,} (more on scroll)"

    def _update_count(self):
        """Show 'N words' or 'N of M (more on scroll)'. A total with more digits than before raises the
        window's minimum size, so the count is never clipped."""
        if len(f"{self.total:,}") != self._count_digits:
            self._count_digits = len(f"{self.total:,}")
            self._update_minsize()
        if self.loaded < self.total:
            self.count_lbl.config(text=f"{self.loaded:,} of {self.total:,} (more on scroll)")
        else:
            self.count_lbl.config(text=f"{self.total:,} words")

    def reload(self, keep_view=False, view=None):
        """Reload the list from the top, or (keep_view) as many rows as were showing, at the same scroll spot
        (or at `view`, a fraction of the list, when reopening)."""
        self._job = None
        keep = self.current
        want = max(self.CHUNK, self.loaded) if keep_view else self.CHUNK
        if view is None:
            view = self.tree.yview()[0] if keep_view else 0.0
        rows, total = self._query(limit=want)
        self._clear_tree()
        self._add_rows(rows)
        self.loaded, self.total = len(rows), total
        self._seen_version = self.store.version
        self._update_count()
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)
            if not keep_view:
                self.tree.see(keep)
        elif keep:
            self.current = None
            self.render_def()
        self.tree.yview_moveto(view)

    def _yscroll(self, lo, hi):
        """Scrollbar callback: also starts loading the next page when the view reaches the last 10%."""
        self.vsb.set(lo, hi)
        self.win.after_idle(self._draw_outline)
        if float(hi) > 0.9 and self.loaded < self.total and not self._loading:
            self.win.after_idle(self._load_more)

    def _draw_outline(self):
        """Place the selection outline round the selected row, or hide it when that row is scrolled out."""
        try:
            sel = self.tree.selection()
            box = self.tree.bbox(sel[0]) if sel else None
        except tk.TclError:
            return
        if not box:
            for edge in self._outline:
                edge.place_forget()
            return
        # The native selection tint is replaced by the row's own tier colour (the outline marks it).
        tag = next((g for g in self.tree.item(sel[0], "tags") if g.startswith("t")), None)
        if tag:
            colour = TIER_COLORS[int(tag[1:])]
            self.style.map(self.tstyle, background=[("selected", colour)], foreground=[("selected", TIER_TEXT)])
        x, y, w, h = box
        t = max(2, self.fsize // 5)                    # line thickness follows the text size
        for edge, (ex, ey, ew, eh) in zip(self._outline, (
                (x, y, w, t), (x, y + h - t, w, t), (x, y, t, h), (x + w - t, y, t, h))):
            edge.place(x=ex, y=ey, width=ew, height=eh)
            edge.lift()

    def _load_more(self):
        """Fetch and append the next page of rows (no-op if already loading or everything is loaded)."""
        if self._loading or not self.alive() or self.loaded >= self.total:
            return
        self._loading = True
        try:
            rows, _ = self._query(limit=self.CHUNK, offset=self.loaded, with_total=False)
            self._add_rows(rows)
            self.loaded += len(rows)
            if not rows:
                self.total = self.loaded
            self._update_count()
        finally:
            self._loading = False

    # ---- selection / editing -----------------------------------------------------------------------------
    def _selected(self):
        """The selected word, or None."""
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _on_select(self):
        """Selection changed: remember it and show its definition."""
        self.current = self._selected()
        self.render_def()

    def render_def(self):
        """Fill the definition pane for the selected word (shows 'Looking up...' until the lookup finishes)."""
        w = self.current
        self.def_text.config(state="normal")
        self.def_text.delete("1.0", "end")
        if w:
            self.def_text.insert("end", w + "\n", "head")
            self.def_text.insert("end", self.app.get_def(w) or "Looking up definition...")
        self.def_text.config(state="disabled")

    def move(self, tier):
        """Move the selected word to `tier` and refresh every window. An anchor word may move too: its old tier's
        anchor passes to its neighbour there, and a message says so (UI-40)."""
        w = self._selected()
        if not w:
            return
        row = self.store.get_word(w)
        if row is not None and row["tier"] == tier:
            return                                   # already there (placing again would reset its duels)
        changes = self.store.place(w, tier)
        self.app.after_external_change()
        self.app.note_anchor_changes(changes)
        self.reload(keep_view=True)

    def unplace(self):
        """Send the selected word back to the front of the queue (anchor words are protected)."""
        w = self._selected()
        if not w:
            return
        if w in self.store.get_anchors():
            show_message("Anchor word", f"'{w}' is an anchor", "Change anchors in Settings first.", parent=self.win)
            return
        self.store.unplace(w)
        self.app.after_external_change()
        self.reload(keep_view=True)

    def undo(self):
        """Ctrl+Z in Browse: undo the last saved action (an unplace, a move) and show the result here."""
        self.app.undo(saved_only=True)
        self.reload(keep_view=True)

    def refine(self):
        """Start a refine session for the selected word in the main window (it must already be placed)."""
        w = self._selected()
        if not w:
            return
        row = self.store.get_word(w)
        if row is None or row["tier"] is None:
            show_message("Not placed", f"'{w}' is not placed yet", "Place the word in a tier first, then refine it.",
                         parent=self.win)
            return
        self.app.start_focus(w)
