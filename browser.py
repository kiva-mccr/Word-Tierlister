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
from tkinter import messagebox, ttk

from constants import TIERS
from fonts import family
from sizing import center_geometry, fit_size, ui_factor, usable_area
from store import Store
from theme import PALETTE, TIER_COLORS, TIER_TEXT
from widgets import RoundButton, refresh_widgets


class Browser:
    """Search / browse / edit window. Text and row height scale with the window; rows load as you scroll."""

    CHUNK = 3000                 # rows fetched per page; the next page loads when you scroll near the end
    BASE_W, BASE_H = 980, 760    # window size at which the text is 12 pt (it grows/shrinks from there)

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
        self._seen_version = -1
        self._loading = False
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
        self.style.configure(f"{self.sid}.TButton", font=self.f_body)
        self.style.configure(f"{self.sid}.TLabelframe.Label", font=self.f_bold)
        # Dropdowns take their text size from the style (the widget's own font option is ignored for
        # read-only ones), so the shared font object must be named here or the text clips as it scales.
        self.style.configure(f"{self.sid}.TCombobox", font=self.f_body, padding=(6, 4))
        self.win.option_add("*TCombobox*Listbox.font", self.f_body)

        top = self.top_bar = ttk.Frame(self.win, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Search:", style=f"{self.sid}.TLabel").pack(side="left")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.search_var, width=18, font=self.f_body)
        entry.pack(side="left", padx=6)
        self.search_var.trace_add("write", lambda *_: self._debounce())
        ttk.Label(top, text="Show:", style=f"{self.sid}.TLabel").pack(side="left", padx=(10, 0))
        self.filter_var = tk.StringVar(value="All placed")
        cb = ttk.Combobox(
            top, textvariable=self.filter_var, state="readonly", width=11, font=self.f_body,
            style=f"{self.sid}.TCombobox",
            values=["All placed"] + [f"Tier {t}" for t in TIERS] + ["Unplaced"],
        )
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.reload())
        ttk.Label(top, text="Sort:", style=f"{self.sid}.TLabel").pack(side="left", padx=(10, 0))
        self.sort_var = tk.StringVar(value="Default")
        sc = ttk.Combobox(top, textvariable=self.sort_var, state="readonly", width=10,
                          font=self.f_body, style=f"{self.sid}.TCombobox", values=list(Store.SORTS))
        sc.pack(side="left", padx=6)
        sc.bind("<<ComboboxSelected>>", lambda e: self.reload())
        ttk.Button(top, text="A+", width=3, style=f"{self.sid}.TButton",
                   command=lambda: self.zoom_by(1)).pack(side="right")
        ttk.Button(top, text="A-", width=3, style=f"{self.sid}.TButton",
                   command=lambda: self.zoom_by(-1)).pack(side="right", padx=(0, 4))
        self.count_lbl = ttk.Label(top, text="", style=f"{self.sid}.TLabel")
        self.count_lbl.pack(side="right", padx=10)

        mid = ttk.Frame(self.win)
        mid.pack(fill="both", expand=True, padx=8)
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
            self.tree.tag_configure(f"t{t}", background=TIER_COLORS[t], foreground=TIER_TEXT)
        self.tree.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        # Selection is shown as an outline round the row (the row keeps its tier colour). Treeview
        # cannot draw per-row borders, so four thin frames are placed over the selected row's box.
        self._outline = [tk.Frame(self.tree, bg=PALETTE["accent_text"]) for _ in range(4)]
        self.tree.bind("<<TreeviewSelect>>", lambda e: (self._on_select(), self._draw_outline()))
        self.tree.bind("<Configure>", lambda e: self._draw_outline(), add="+")
        self.tree.bind("<Double-1>", lambda e: self.refine())

        btns = self.btn_bar = ttk.Frame(self.win, padding=8)
        btns.pack(fill="x")
        ttk.Label(btns, text="Move to:", style=f"{self.sid}.TLabel").pack(side="left")
        for t in range(len(TIERS)):
            RoundButton(btns, TIERS[t], lambda t=t: self.move(t), bg=TIER_COLORS[t], font=self.f_bold,
                        padx=10, pady=3, radius=10, animator=self.app.anim).pack(side="left", padx=2)
        ttk.Button(btns, text="Unplace (back to queue)", style=f"{self.sid}.TButton",
                   command=self.unplace).pack(side="left", padx=10)
        ttk.Button(btns, text="Refine this word", style=f"{self.sid}.TButton",
                   command=self.refine).pack(side="left")
        ttk.Button(btns, text="Refresh", style=f"{self.sid}.TButton",
                   command=lambda: self.reload(keep_view=True)).pack(side="right")

        dfr = ttk.LabelFrame(self.win, text="Definition", style=f"{self.sid}.TLabelframe")
        dfr.pack(fill="x", padx=8, pady=(0, 8))
        self.def_text = tk.Text(dfr, height=7, wrap="word", state="disabled", font=self.f_body)
        self.def_text.tag_configure("head", font=self.f_bold)
        self.def_text.pack(fill="x", padx=4, pady=4)

        # Ctrl + / Ctrl - / Ctrl 0 and Ctrl+mouse wheel zoom the text.
        for seq, delta in (("<Control-plus>", 1), ("<Control-equal>", 1), ("<Control-KP_Add>", 1),
                           ("<Control-minus>", -1), ("<Control-KP_Subtract>", -1), ("<Control-0>", 0)):
            self.win.bind(seq, lambda e, d=delta: self.zoom_by(d))
        for widget in (self.win, self.tree):
            widget.bind("<Control-MouseWheel>", self._wheel_zoom)
            widget.bind("<Control-Button-4>", lambda e: self._wheel_zoom(e, 1))
            widget.bind("<Control-Button-5>", lambda e: self._wheel_zoom(e, -1))
        self.win.bind("<Configure>", self._on_configure)
        self.win.bind("<FocusIn>", lambda e: self._maybe_refresh() if e.widget is self.win else None)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self._fit_to_contents()
        self._apply_scale()
        entry.focus_set()
        self.reload()

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
        """Unregister from the App and destroy the window."""
        if self in self.app.browsers:
            self.app.browsers.remove(self)
        self.win.destroy()

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
        refresh_widgets(self.btn_bar)               # the tier buttons use the shared fonts
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
        w = max(self.top_bar.winfo_reqwidth(), self.btn_bar.winfo_reqwidth(), tree_w)
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
        refresh_widgets(self.btn_bar)
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
        return "break"

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
        """Reload (keeping the scroll position) if anything changed in the save since the last load."""
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

    def _update_count(self):
        """Show 'N words' or 'N of M (more on scroll)'."""
        if self.loaded < self.total:
            self.count_lbl.config(text=f"{self.loaded:,} of {self.total:,} (more on scroll)")
        else:
            self.count_lbl.config(text=f"{self.total:,} words")

    def reload(self, keep_view=False):
        """Reload the list from the top, or (keep_view) as many rows as were showing, at the same scroll spot."""
        self._job = None
        keep = self.current
        want = max(self.CHUNK, self.loaded) if keep_view else self.CHUNK
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
        """Move the selected word to `tier` (anchor words are protected) and refresh every window."""
        w = self._selected()
        if not w:
            return
        if w in self.store.get_anchors():
            messagebox.showinfo("Anchor word", f"'{w}' is an anchor. Change anchors in Settings first.",
                                parent=self.win)
            return
        self.store.place(w, tier)
        self.app.after_external_change()
        self.reload(keep_view=True)

    def unplace(self):
        """Send the selected word back to the front of the queue (anchor words are protected)."""
        w = self._selected()
        if not w:
            return
        if w in self.store.get_anchors():
            messagebox.showinfo("Anchor word", f"'{w}' is an anchor. Change anchors in Settings first.",
                                parent=self.win)
            return
        self.store.unplace(w)
        self.app.after_external_change()
        self.reload(keep_view=True)

    def refine(self):
        """Start a refine session for the selected word in the main window (it must already be placed)."""
        w = self._selected()
        if not w:
            return
        row = self.store.get_word(w)
        if row is None or row["tier"] is None:
            messagebox.showinfo("Not placed", "Place the word in a tier first, then refine it.",
                                parent=self.win)
            return
        self.app.start_focus(w)
