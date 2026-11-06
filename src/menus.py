"""The program's own menus and tabs (UI-10, UI-43): DropMenu (a borderless drop-down kept built and hidden while
closed), ChoiceButton (a drop-down choice), HeaderMenus (File / Edit / View / Settings) and TabBar (folder-style tabs).
No ttk.Combobox or tk.Menu popups: they grab input and float over other programs on Linux. close_popups /
watch_focus close every open drop-down (the program lost focus).
"""
import tkinter as tk

from sizing import clamp_to_monitor
from smooth import SmoothCanvas
from theme import PALETTE
from buttons import RoundButton


class TabBar(SmoothCanvas):
    """Folder-style tabs over a page (UI-10): a hairline runs the full width under the tabs, and the
    chosen tab is drawn in the page colour with its sides and rounded top outlined, open at the bottom,
    so it looks joined to the page below.

        tabs = TabBar(parent, [("place", "Place new words"), ...], on_change, font("label"),
                      animator=app.anim, page_bg=PALETTE["bg"])
        tabs.pack(fill="x")
        tabs.set("refine")        # move to a tab without calling on_change (e.g. after a key)
        tabs.show_only({"place", "refine"})   # the other tabs fold away (UI-46)

    A click on another tab slides the open tab there (SLIDE_MS, ease-out; jumps with Reduce motion) and
    calls on_change(key). Tabs are all as wide as the widest label and sit centred. A tab that is shown or
    hidden grows or folds over SLIDE_MS too; its label shows once its tab is wide enough for it.
    """
    SLIDE_MS = 180

    def __init__(self, parent, options, on_change, font=None, animator=None, canvas_bg=None, page_bg=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["surface"], takefocus=0)
        self.options = list(options)
        self._keys = [k for k, _ in self.options]
        self._on_change, self._font, self._anim = on_change, font, animator
        self._page = page_bg or PALETTE["bg"]
        self.value = self._keys[0]
        self.visible = set(self._keys)
        self._open = {k: 1.0 for k in self._keys}   # how open each tab is, 0 (folded away) .. 1 (animated)
        self._x = 0.0                        # left edge of the open tab, in tab widths (animated)
        self._sliding = False
        self._hover = None
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<ButtonRelease-1>", self._on_click)
        self.bind("<Configure>", lambda e: self._draw())
        self._draw()

    def _metrics(self):
        f = self._font
        line = f.metrics("linespace") if f else 16
        widest = max((f.measure(lbl) if f else 8 * len(lbl)) for _, lbl in self.options)
        tab_w = widest + 2 * int(line * 1.1)
        h = int(line * 2.1)
        n = len(self.options)
        width = max(self.winfo_width(), n * tab_w + 20)
        shown = sum(self._open.values())
        return tab_w, h, (width - shown * tab_w) / 2, width   # tab width, height, left edge of the tabs, width

    def _slot(self, key):
        """Left edge of a tab, in tab widths from the left edge of the tabs."""
        return sum(self._open[k] for k in self._keys[:self._keys.index(key)])

    def _draw(self):
        self.delete("all")
        tab_w, h, x0, width = self._metrics()
        super().configure(height=h + 1, cursor="hand2")
        super().configure(width=len(self.options) * tab_w + 20)
        self.round_rect(0, 0, 0, 0, 0, fill=PALETTE["surface2"], tags="hoverfill")
        # the open tab: page coloured with a hairline, round on top; its bottom edge sits just below the canvas,
        # so it is open at the bottom (it runs into the page)
        self.round_rect(0, 0, 0, 0, 0, fill=self._page, outline=PALETTE["border"], tags="tabfill")
        self.create_line(0, 0, 0, 0, fill=PALETTE["border"], state="hidden", tags="tabedge")   # (its outline, for tests)
        self.create_line(0, 0, 0, 0, fill=PALETTE["border"], tags="baseline_left")
        self.create_line(0, 0, 0, 0, fill=PALETTE["border"], tags="baseline_right")
        for key, label in self.options:
            self.create_text(0, 2 + h / 2, text=label, font=self._font, tags=("label", f"label_{key}"))
        self._place_tab()

    @staticmethod
    def _tab_shape(x1, x2, top, bottom, r):
        """Outline of a tab with rounded top corners and square bottom corners (points doubled at the
        bottom so a smoothed polygon keeps them sharp)."""
        return [x1, bottom, x1, bottom, x1, top + r, x1, top, x1 + r, top, x2 - r, top, x2, top,
                x2, top + r, x2, bottom, x2, bottom]

    def _place_tab(self):
        tab_w, h, x0, width = self._metrics()
        base = h                                     # y of the page line
        top = 4
        r = max(4, h // 4)
        x1 = x0 + self._x * tab_w + 2
        x2 = x1 + self._open[self.value] * tab_w - 4
        shape = self._tab_shape(x1, max(x2, x1 + 2 * r), top, base + 1, r)
        self.round_rect_coords("tabfill", x1, top, max(x2, x1 + 2 * r), base + 3, radii=(r, r, 0, 0))
        self.coords("tabedge", *shape[2:-2])       # sides and top only: open at the bottom
        self.coords("baseline_left", 0, base, x1, base)
        self.coords("baseline_right", x2, base, width, base)
        hov = self._hover if self._hover != self.value else None
        if hov is not None:
            hx1 = x0 + self._slot(hov) * tab_w + 6
            self.round_rect_coords("hoverfill", hx1, top + 4, hx1 + tab_w - 12, base - 1, radii=(r, r, 0, 0))
            self.itemconfigure("hoverfill", state="normal")
        else:
            self.itemconfigure("hoverfill", state="hidden")
        for key, label in self.options:
            on = key == self.value or key == self._hover
            w = self._open[key] * tab_w
            fits = w >= (self._font.measure(label) if self._font else 8 * len(label)) + 4
            self.coords(f"label_{key}", x0 + self._slot(key) * tab_w + w / 2, 2 + h / 2)
            self.itemconfigure(f"label_{key}", fill=PALETTE["text"] if on else PALETTE["muted"],
                               state="normal" if fits else "hidden")
        self.tag_raise("label")

    def _index_at(self, x):
        tab_w, _h, x0, _w = self._metrics()
        for key in self._keys:
            left = x0 + self._slot(key) * tab_w
            if key in self.visible and left <= x < left + self._open[key] * tab_w:
                return key
        return None

    def tab_x(self, key):
        """Centre x of a tab, in canvas pixels (for tests)."""
        tab_w, _h, x0, _w = self._metrics()
        return x0 + (self._slot(key) + self._open[key] / 2) * tab_w

    def _on_motion(self, e):
        self._set_hover(self._index_at(e.x))

    def _set_hover(self, key):
        if key != self._hover:
            self._hover = key
            self._place_tab()

    def _on_click(self, e):
        key = self._index_at(e.x)
        if key is not None and key != self.value:
            self.set(key)
            self._on_change(key)

    def set(self, key):
        """Show `key` as the open tab (slides; does not call on_change)."""
        if key not in self._keys:
            return
        self.value = key
        start = self._x

        def frame(p):
            self._sliding = p < 1
            self._x = start + (self._slot(self.value) - start) * p   # follows tabs that fold meanwhile
            self._place_tab()
        if self._anim is None:
            frame(1.0)
        else:
            self._anim.run(f"tabs{id(self)}", self.SLIDE_MS, frame)

    def show_only(self, keys, animate=True):
        """Show just these tabs (the open one always stays): the others fold away and new ones grow in
        (UI-46). animate=False sets them at once (when the window is first built)."""
        keys = set(keys) | {self.value}
        if keys == self.visible:
            return
        self.visible = keys
        start = dict(self._open)

        def frame(p):
            for k in self._keys:
                goal = 1.0 if k in self.visible else 0.0
                self._open[k] = start[k] + (goal - start[k]) * p
            if not self._sliding:
                self._x = self._slot(self.value)
            if self._hover not in self.visible:
                self._hover = None
            self._place_tab()
        if self._anim is None or not animate:
            frame(1.0)
        else:
            self._anim.run(f"tabfold{id(self)}", self.SLIDE_MS, frame)

    def get(self):
        return self.value

    def refresh(self):
        self._draw()


class DropMenu:
    """A styled drop-down menu (UI-10): a borderless window with roomy rows, the pastel highlight, check
    marks and shortcut hints, used by the header's File / Edit / View / Settings buttons.

        items = [("command", "Export tier list...", app.export, None),
                 ("check", "Reduce motion", app.motion_var, app.toggle_motion),
                 ("radio", "Tier S", app.filter_var, "S", app.refresh),
                 ("separator",),
                 ("command", "Undo", app.undo, "Ctrl+Z")]
        DropMenu(root, items, font("body")).open(x, y, on_close)

    Mouse: hover highlights, click runs the item and closes. Keys: Up / Down move, Return runs, Escape
    closes. It never grabs input (unlike tk's own menus and ttk drop-down lists), so switching to another
    program closes it (watch_focus -> close_popups, UI-43); a click elsewhere in the window does too.
    """
    open_menus = set()                 # every DropMenu showing right now (close_popups closes them all)

    def __init__(self, root, items, font=None):
        self.root, self.items, self.font = root, list(items), font
        self.win = None                  # built once and kept (hidden while closed): rebuilt only for other items
        self._built = None               # what the kept window was built for (_shape)
        self._shown = False
        self._rows, self._active, self._on_close = [], None, None
        self._prev_focus = ""
        self.on_side = None              # called with -1 / +1 for Left / Right (HeaderMenus: the next menu)

    @staticmethod
    def labels(items):
        """The labels of the clickable items (for tests and docs)."""
        return [it[1] for it in items if it[0] in ("command", "check", "radio")]

    def is_open(self):
        return self._shown

    def _shape(self):
        """What the rows look like apart from their check marks: the kept window is reused while this holds (the
        items' functions may be new ones: App.apply_keys makes the list again)."""
        out = []
        for it in self.items:
            if it[0] == "separator":
                out.append(("separator",))
            else:
                out.append((it[0], it[1], it[3] if it[0] == "command" and len(it) > 3 else None))
        return tuple(out)

    def prepare(self):
        """Build the window now, hidden and laid out (_warm), so the first open is quick too (HeaderMenus does it
        while idle)."""
        if self._shown:
            return
        try:
            if self.win is None or self._built != self._shape() or not self.win.winfo_exists():
                self._build()
                self._warm()
        except tk.TclError:
            pass

    WARM_TEXT = "\u2713"                 # drawn on an open only: its font (a fallback on many systems) found ahead

    def _warm(self):
        """Do ahead, without showing anything, the work a first open did beyond building (F-56, asked for: the
        first open of each top menu was slow on Fedora / GNOME): lay out the rows, make every row's system window
        and look up the fonts for the check mark (Tk searches the system's fonts for a symbol its own font lacks,
        slow the first time where many fonts are installed)."""
        win = self.win
        win.update_idletasks()
        for row, parts, _it in self._rows:
            row.winfo_id()
            for w in parts:
                w.winfo_id()
        win.winfo_id()
        fonts = {str(parts[0].cget("font")) for _row, parts, _it in self._rows}
        for f in fonts:
            win.tk.call("font", "measure", f, self.WARM_TEXT)

    def _build(self):
        """Make the (hidden) window and its rows for the items (asked for: menus opened slowly, 40-190 ms each time,
        when each open made its window again: now it is made once and kept)."""
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
        win = self.win = tk.Toplevel(self.root, bg=PALETTE["border"])
        win.withdraw()
        win.overrideredirect(True)
        # (not "-topmost": that kept it in front of other programs after switching away, UI-43)
        body = tk.Frame(win, bg=PALETTE["surface"], padx=6, pady=6)
        body.pack(padx=1, pady=1)                 # the 1 px border is the window's own colour
        self._rows = []
        for it in self.items:
            if it[0] == "separator":
                tk.Frame(body, height=1, bg=PALETTE["border"]).pack(fill="x", padx=8, pady=5)
                continue
            kind, label = it[0], it[1]
            extra = it[3] if len(it) > 3 else None
            row = tk.Frame(body, bg=PALETTE["surface"], cursor="hand2")
            row.pack(fill="x")
            parts = [tk.Label(row, text="", width=2, bg=PALETTE["surface"], fg=PALETTE["accent_text"],
                              font=self.font, anchor="w"),
                     tk.Label(row, text=label, bg=PALETTE["surface"], fg=PALETTE["text"], font=self.font,
                              anchor="w", padx=4, pady=5)]
            accel = extra if kind == "command" else None
            if accel:
                parts.append(tk.Label(row, text=accel, bg=PALETTE["surface"], fg=PALETTE["muted"],
                                      font=self.font, anchor="e", padx=10))
            parts[0].pack(side="left", padx=(6, 0))
            parts[1].pack(side="left")
            if accel:
                parts[2].pack(side="right")
            i = len(self._rows)
            self._rows.append((row, parts, it))
            for w in [row] + parts:
                w.bind("<Enter>", lambda e, i=i: self._highlight(i))
                w.bind("<ButtonRelease-1>", lambda e, i=i: self.invoke(i))
        win.bind("<Escape>", lambda e: self.close())
        win.bind("<Up>", lambda e: self._step(-1))
        win.bind("<Down>", lambda e: self._step(1))
        win.bind("<Return>", lambda e: self._active is not None and self.invoke(self._active))
        win.bind("<Left>", lambda e: self.on_side and self.on_side(-1))
        win.bind("<Right>", lambda e: self.on_side and self.on_side(1))
        self._built = self._shape()

    def _refresh_rows(self):
        """The kept rows take the current items (their functions) and check marks, none highlighted."""
        clickable = [it for it in self.items if it[0] != "separator"]
        self._rows = [(row, parts, it) for (row, parts, _old), it in zip(self._rows, clickable)]
        for row, parts, it in self._rows:
            kind, target = it[0], it[2]
            mark = ""
            if kind == "check":
                mark = "\u2713" if target.get() else ""
            elif kind == "radio":
                mark = "\u2713" if target.get() == it[3] else ""
            if parts[0].cget("text") != mark:
                parts[0].configure(text=mark)
        self._highlight(None)

    def open(self, x, y, on_close=None):
        """Show the menu with its top-left corner at screen position (x, y)."""
        self.close()
        self._on_close = on_close
        self._prev_focus = str(self.root.tk.call("focus"))    # given back on close (UI-27)
        self.prepare()
        win = self.win
        self._refresh_rows()
        win.update_idletasks()
        # keep it on screen
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        x, y = clamp_to_monitor(win, x, y, w, h)     # on the monitor it opens from, not the main one
        win.geometry(f"+{x}+{y}")
        win.deiconify()
        win.lift()
        self._shown = True
        DropMenu.open_menus.add(self)
        try:
            win.focus_force()
        except tk.TclError:
            pass

    def _highlight(self, i):
        self._active = i
        for j, (row, parts, _it) in enumerate(self._rows):
            bg = PALETTE["select_bg"] if j == i else PALETTE["surface"]
            if row.cget("bg") != bg:
                for w in [row] + parts:
                    w.configure(bg=bg)

    def _step(self, d):
        if not self._rows:
            return
        i = 0 if self._active is None and d > 0 else (len(self._rows) - 1 if self._active is None else
                                                      (self._active + d) % len(self._rows))
        self._highlight(i)

    def invoke(self, i):
        """Run row `i` (0 = first clickable item) and close the menu."""
        _row, _parts, it = self._rows[i]
        self.close()
        if it[0] == "check":
            var, command = it[2], (it[3] if len(it) > 3 else None)
            var.set(not var.get())
            if command:
                command()
        elif it[0] == "radio":
            var, value, command = it[2], it[3], (it[4] if len(it) > 4 else None)
            var.set(value)
            if command:
                command()
        else:
            it[2]()

    def close(self):
        """Close it. If it had the keyboard focus, the focus goes back to where it was before it opened, so
        keys keep working (closing with Escape used to leave no focus at all); not when the program has
        lost the focus to another one."""
        DropMenu.open_menus.discard(self)
        if not self._shown:
            return
        self._shown = False
        try:
            had_focus = str(self.win.tk.call("focus")).startswith(str(self.win))
            self.win.withdraw()              # (kept, hidden, for the next open; F-54: never parked off-screen)
            if had_focus:                    # forced: the window manager does not hand focus back from a
                self.root.nametowidget(self._prev_focus or ".").focus_force()   # borderless window
        except (tk.TclError, KeyError):
            pass
        self._active = None
        cb, self._on_close = self._on_close, None
        if cb:
            cb()


class ChoiceButton(RoundButton):
    """A drop-down choice (UI-43): a soft button showing the current value and a little arrow; a click opens a
    DropMenu with the choices (a check mark on the current one). Replaces ttk.Combobox, whose list grabs all
    input and so stayed in front of other programs.

        ChoiceButton(parent, app.filter_var, ["All tiers", "S", "A"], on_change=app.refresh, font=font("body"))

    It is as wide as its longest choice, so it does not change size when the value does.
    """

    def __init__(self, parent, variable, values, on_change=None, font=None, animator=None, canvas_bg=None):
        self.var, self.values, self._on_change = variable, list(values), on_change
        super().__init__(parent, "", self.toggle, bg=PALETTE["surface"], font=font, padx=12, pady=5, radius=10,
                         animator=animator, canvas_bg=canvas_bg)
        self.menu = DropMenu(self.winfo_toplevel(), [], font)
        variable.trace_add("write", lambda *_: self._show())
        self._show()

    def set_values(self, values):
        self.values = list(values)
        self._show()

    def _show(self):
        """Label it with the current value; the minimum width fits the longest choice."""
        f = self._font
        self._minwidth = max((f.measure(f"{v}   \u25be") for v in self.values), default=0) + 2 * self._padx + 4
        self.config(text=f"{self.var.get()}   \u25be")

    def toggle(self):
        if self.menu.is_open():
            self.menu.close()
            return
        self.menu.items = [("radio", v, self.var, v, self._picked) for v in self.values]
        self.menu.open(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height() + 2)

    def _picked(self):
        if self._on_change:
            self._on_change()

    def refresh(self):
        self._show()


class HeaderMenus(tk.Frame):
    """The row of header menu buttons (File, Edit, View, Settings) with their DropMenus (UI-10).

        HeaderMenus(parent, [("File", items), ("Edit", items), ...], font("body"), animator=app.anim)

    Clicking a button opens its menu under it (clicking again closes it); while one menu is open,
    hovering another button switches to that menu, like a desktop menu bar, and so do Left / Right.
    open_menu(name) opens one from the keyboard (Alt+F and friends, F10).
    """

    def __init__(self, parent, menus, font=None, animator=None, bg=None):
        bg = bg or PALETTE["surface"]
        super().__init__(parent, bg=bg)
        self.menus, self.buttons, self.drops = dict(menus), {}, {}
        self._open = None
        for name, items in menus:
            b = RoundButton(self, name, lambda n=name: self.toggle(n), font=font, padx=12, pady=5, radius=10,
                            animator=animator, canvas_bg=bg, flat=True)
            b.pack(side="left", padx=(0, 2))
            b.bind("<Enter>", lambda e, n=name: self._hover_switch(n), add="+")
            self.buttons[name] = b
            self.drops[name] = DropMenu(self.winfo_toplevel(), items, font)
            self.drops[name].on_side = lambda d, n=name: self._side(n, d)
        top = self.winfo_toplevel()
        top.bind("<ButtonPress-1>", self._click_outside, add="+")
        self._top_geo = None
        top.bind("<Configure>", lambda e: e.widget is top and self._top_configured(), add="+")
        top.bind("<Unmap>", lambda e: e.widget is top and self.close(), add="+")
        self._to_prepare = list(self.drops)
        self.after(self.PREPARE_MS, self._prepare_next)

    PREPARE_MS, PREPARE_GAP_MS = 1500, 250   # the menus are built hidden, one at a time, once the window is up

    def _prepare_next(self):
        """Build the next menu's window ahead of its first open (DropMenu.prepare), one every PREPARE_GAP_MS."""
        if not self._to_prepare or not self.winfo_exists():
            return
        self.drops[self._to_prepare.pop(0)].prepare()
        if self._to_prepare:
            self.after(self.PREPARE_GAP_MS, self._prepare_next)

    def _top_geometry(self):
        top = self.winfo_toplevel()
        return top.winfo_rootx(), top.winfo_rooty(), top.winfo_width(), top.winfo_height()

    def _top_configured(self):
        """The main window moved or changed size since the menu opened: the menu would be left behind, so it
        closes. Windows also sends <Configure> when nothing changed (as the focus goes back to the window while
        the pointer moves from one menu to the next), which must not close the menu just opened; so the window's
        place is compared with where it was when the menu opened, not with the event's own numbers."""
        if self._open is not None and self._top_geometry() != self._top_geo:
            self.close()

    def _click_outside(self, e):
        """A click anywhere in the main window closes the open menu (its own button toggles it instead)."""
        if self._open is not None and e.widget not in self.buttons.values():
            self.close()

    @property
    def open_name(self):
        return self._open

    def toggle(self, name):
        if self._open == name:
            self.close()
        else:
            self.open_menu(name)

    def open_menu(self, name):
        self.close()
        b = self.buttons[name]
        self._open, self._top_geo = name, self._top_geometry()
        b.set_selected(True)
        self.drops[name].open(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height() + 2,
                              on_close=lambda n=name: self._closed(n))

    def _closed(self, name):
        if self._open == name:
            self._open = None
        try:
            self.buttons[name].set_selected(False)
        except tk.TclError:
            pass

    def _side(self, name, d):
        """Left / Right in an open menu: open the neighbouring one (wrapping round, like a menu bar)."""
        names = list(self.buttons)
        self.open_menu(names[(names.index(name) + d) % len(names)])

    def _hover_switch(self, name):
        if self._open is not None and self._open != name:
            self.open_menu(name)

    def close(self):
        if self._open is not None:
            self.drops[self._open].close()


def close_popups():
    """Close every drop-down the program has open (UI-43): all DropMenus (header menus, ChoiceButtons). Called
    when the program loses focus, so nothing is left floating in front of another program."""
    for menu in list(DropMenu.open_menus):
        menu.close()


def watch_focus(root, on_lost=None):
    """When the whole program loses focus (another program came to the front), close its drop-downs
    (close_popups) and call on_lost(). Moving focus between the program's own windows does nothing.
    (ttk drop-down lists cannot be closed this way: they grab all input, so no focus event arrives at
    all; the program uses ChoiceButton instead.)"""
    state = {"job": None}

    def check():
        state["job"] = None
        try:
            # ask Tcl, not focus_get(): while a ttk drop-down list is open the focus is in its pop-down,
            # which tkinter does not know, and focus_get() raises instead of answering
            focused = root.tk.call("focus")
        except tk.TclError:
            return
        if not str(focused):
            close_popups()
            if on_lost:
                on_lost()

    def later(_e):
        if state["job"] is None:
            state["job"] = root.after(120, check)
    root.bind_all("<FocusOut>", later, add="+")
    return check
