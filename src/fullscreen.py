"""Full screen (FS-2, asked for: "slightly video gamie"): the pause menu that stands in for the top menus while the
window fills the screen, and the Back bar a dialog wears there.

    menu = PauseMenu(app.root, pages, anim=app.anim, on_close=app.after_pause_menu, keys=app.keys)
    menu.open()                       # over the whole page; Esc on its first page closes it again
    menu.open(["Menu", "Settings"])   # straight onto a page (a new look rebuilt the window: App.take_over)

`pages` is {name: rows}; the first page is the one the menu opens on. A row is
    ("page", label, page_name)        opens another page (a chevron at its right)
    ("command", label, function)      runs it; the menu stays (a dialog opened from it shows over the menu, and
                                      closing that dialog is Back to here)
    ("check", label, variable, function)   a switch: flips the variable, then runs the function
    ("gap",)                          a little room between groups
Up / Down move the highlight, Enter (or Right on a page row) opens, Esc / Backspace / Left go back a page. Pages
slide in sideways and the lit row pops a little (both jump with Reduce motion: the Animator's own rule).

Tk has no see-through widgets, so the page behind is not shown dimmed (UI-74, UI-32): the menu covers it with a
soft lilac backdrop instead, with a few faint tier-coloured rounds for a game-like feel.
"""
import tkinter as tk

from fonts import font
from keymap import NAMES
from smooth import SmoothCanvas
from theme import PALETTE, TIER_COLORS
from ui_motion import lerp_color
from widgets import RoundButton

SLIDE_MS = 200          # a page sliding in
POP_MS = 140            # the lit row growing a little
SEP = "  ›  "      # the trail's separator: "Menu  >  Settings"


def backdrop_colour():
    """The colour behind the pause menu: the page tinted toward the accent (lilac in both looks)."""
    return lerp_color(PALETTE["bg"], PALETTE["accent"], 0.32)


def key_names(*keysyms):
    """How navigation keys read on screen (keymap.NAMES), joined: ("Escape", "BackSpace") -> "Esc / Backspace"."""
    return " / ".join(NAMES.get(k, k) for k in keysyms)


class PauseMenu:
    """The full screen menu: a card in the middle of a backdrop that covers the whole window (see the module)."""

    def __init__(self, root, pages, anim=None, on_close=None, extra_keys=None):
        self.root, self.pages, self.anim = root, dict(pages), anim
        self.on_close = on_close
        self.extra_keys = extra_keys          # (event) -> True when it handled a key the menu does not (F11)
        self.path, self.sel = [], {}
        self.canvas = None
        self._rows = []                        # (row, box) of the page on screen, row = the page's row tuple
        self._gen = 0

    # -- open / close
    def is_open(self):
        return self.canvas is not None

    def open(self, path=None):
        """Cover the window and show the first page (or `path`, a list of page names from the first)."""
        first = next(iter(self.pages))
        path = [p for p in (path or [first]) if p in self.pages] or [first]
        if path[0] != first:
            path = [first] + path
        if self.canvas is None:
            c = self.canvas = SmoothCanvas(self.root, bd=0, highlightthickness=0, bg=backdrop_colour(),
                                           takefocus=1)
            c.place(x=0, y=0, relwidth=1, relheight=1)
            c.bind("<Configure>", lambda e: self._draw())
            c.bind("<Key>", self._on_key)
            c.bind("<Motion>", self._on_motion)
            c.bind("<ButtonRelease-1>", self._on_click)
        self.path = path
        self._pointer = None                   # (where the pointer was: a menu opening under it must not light a row)
        self.canvas.tk.call("raise", self.canvas._w)     # (a Canvas's own lift() raises items, not the widget)
        self.canvas.focus_set()
        self._draw()

    def close(self):
        if self.canvas is None:
            return
        try:
            self.canvas.destroy()
        except tk.TclError:
            pass
        self.canvas, self._rows = None, []
        self._pointer = None
        if self.anim:
            self.anim.finish("pause_slide")
            self.anim.finish("pause_pop")
        if self.on_close:
            self.on_close()

    def trail(self):
        """The pages from the first to the one showing ("Menu", "Settings")."""
        return list(self.path)

    # -- moving about
    def go(self, page):
        self.path.append(page)
        self._draw(slide=1)

    def back(self):
        """One page back; on the first page, close the menu (asked for: Esc again goes back to the words)."""
        if len(self.path) > 1:
            left = self.path.pop()
            rows = self.pages[self.path[-1]]
            for i, r in enumerate(rows):                # (the row of the page just left is lit again)
                if r[0] == "page" and r[2] == left:
                    self.sel[self.path[-1]] = i
            self._draw(slide=-1)
        else:
            self.close()

    def activate(self, i):
        rows = self.pages[self.path[-1]]
        if not 0 <= i < len(rows):
            return
        row = rows[i]
        self.sel[self.path[-1]] = i
        if row[0] == "page":
            self.go(row[2])
        elif row[0] == "command":
            row[2]()
            if self.is_open():
                self._draw()
        elif row[0] == "check":
            row[2].set(not row[2].get())
            if len(row) > 3 and row[3]:
                row[3]()
            if self.is_open():
                self._draw()

    def _step(self, d):
        rows = self.pages[self.path[-1]]
        live = [i for i, r in enumerate(rows) if r[0] != "gap"]
        if not live:
            return
        cur = self.sel.get(self.path[-1])
        if cur not in live:
            nxt = live[0] if d > 0 else live[-1]
        else:
            nxt = live[(live.index(cur) + d) % len(live)]
        self._light(nxt)

    # -- input
    def _on_key(self, e):
        ks = e.keysym
        if ks in ("Up", "KP_Up"):
            self._step(-1)
        elif ks in ("Down", "KP_Down"):
            self._step(1)
        elif ks in ("Return", "KP_Enter", "space"):
            i = self.sel.get(self.path[-1])
            if i is not None:
                self.activate(i)
        elif ks == "Right":
            i = self.sel.get(self.path[-1])
            rows = self.pages[self.path[-1]]
            if i is not None and rows[i][0] == "page":
                self.activate(i)
        elif ks in ("Escape", "BackSpace", "Left"):
            self.back()
        elif self.extra_keys:
            self.extra_keys(e)
        return "break"                    # (nothing reaches the page behind while the menu is open)

    def _row_at(self, x, y):
        for i, (_row, box) in enumerate(self._rows):
            if box and box[0] <= x <= box[2] and box[1] <= y <= box[3]:
                return i
        return None

    def _on_motion(self, e):
        """The pointer lights the row it moves onto. The first motion only notes where it is: a menu appearing
        under a still pointer can get one, which would light the row under it instead of the one the keys left."""
        if self._pointer is None or self._pointer == (e.x_root, e.y_root):
            self._pointer = (e.x_root, e.y_root)
            return
        self._pointer = (e.x_root, e.y_root)
        i = self._row_at(e.x, e.y)
        if i is not None and i != self.sel.get(self.path[-1]):
            self._light(i)

    def _on_click(self, e):
        if self._back_box and self._back_box[0] <= e.x <= self._back_box[2] and \
                self._back_box[1] <= e.y <= self._back_box[3]:
            self.back()
            return
        i = self._row_at(e.x, e.y)
        if i is not None:
            self.activate(i)

    # -- drawing
    _back_box = None
    _pointer = None

    def _metrics(self):
        f = font("title")
        line = f.metrics("linespace")
        rows = self.pages[self.path[-1]]
        labels = [r[1] for r in rows if r[0] != "gap"]
        widest = max([f.measure(t) for t in labels] + [f.measure("n") * 18])
        row_h = round(line * 2.0)
        pad = round(line * 1.4)
        width = widest + 4 * line + (3 * line if any(r[0] == "check" for r in rows) else 0)
        return f, line, row_h, pad, width

    def _draw(self, slide=0):
        """Draw the page on screen (slide: +1 in from the right, -1 from the left, 0 at once)."""
        c = self.canvas
        if c is None:
            return
        if self.anim:                          # (a pop or slide still running belongs to the page going away)
            self.anim.stop("pause_pop")
            self.anim.stop("pause_slide")
        self._gen += 1
        c.delete("all")
        W, H = max(c.winfo_width(), 2), max(c.winfo_height(), 2)
        bg = backdrop_colour()
        c.configure(bg=bg)
        # a few faint rounds in the tier colours: the "game" backdrop
        for i, col in enumerate(TIER_COLORS):
            r = (0.16 + 0.05 * (i % 3)) * min(W, H)
            cx = W * (0.08 + 0.17 * i)
            cy = H * (0.18 if i % 2 else 0.86)
            c.round_rect(cx - r, cy - r, cx + r, cy + r, r, fill=lerp_color(bg, col, 0.28), tags="deco")
        f, line, row_h, pad, width = self._metrics()
        page = self.path[-1]
        rows = self.pages[page]
        first = len(self.path) == 1
        head_h = font("pair").metrics("linespace") if first else round(line * 2.2)
        gaps = sum(1 for r in rows if r[0] == "gap")
        body = (len(rows) - gaps) * (row_h + line // 2) + gaps * line
        card_w = min(W - 2 * line, width + 2 * pad)
        card_h = min(H - 2 * line, head_h + body + 3 * pad)
        x0, y0 = (W - card_w) // 2, (H - card_h) // 2
        c.round_rect(x0, y0, x0 + card_w, y0 + card_h, round(line * 1.3), fill=PALETTE["bg"],
                     outline=PALETTE["border"], width=2, shadow=(lerp_color(bg, PALETTE["text"], 0.18), 0, 6))
        # the head: the menu's title on its first page; Back and the trail on the others
        self._back_box = None
        hy = y0 + pad
        if first:
            c.create_text(x0 + pad, hy, text=page, anchor="nw", font=font("pair"), fill=PALETTE["text"],
                          tags="page")
        else:
            bw, bh = font("label").measure("Back") + round(line * 2.4), round(line * 1.9)
            self._back_box = (x0 + pad, hy, x0 + pad + bw, hy + bh)
            c.round_rect(*self._back_box, bh // 2, fill=PALETTE["surface"], outline=PALETTE["border"], width=2,
                         tags="back")
            icon = c.icon_image("back", round(line * 0.8), PALETTE["text"])
            c.create_image(x0 + pad + round(line * 0.9), hy + bh / 2, image=icon, tags="back")
            c.create_text(x0 + pad + round(line * 1.6), hy + bh / 2, text="Back", anchor="w",
                          font=font("head"), fill=PALETTE["text"], tags="back")
            tx = self._back_box[2] + line
            crumbs = SEP.join(self.path[:-1]) + SEP
            c.create_text(tx, hy + bh / 2, text=crumbs, anchor="w", font=font("label"), fill=PALETTE["muted"],
                          tags="page")
            c.create_text(tx + font("label").measure(crumbs), hy + bh / 2, text=page, anchor="w",
                          font=font("head"), fill=PALETTE["text"], tags="page")
        # the rows
        self._rows = []
        y = y0 + pad + head_h + pad
        if self.sel.get(page) is None or rows[self.sel[page]][0] == "gap":
            self.sel[page] = next((i for i, r in enumerate(rows) if r[0] != "gap"), None)
        for i, row in enumerate(rows):
            if row[0] == "gap":
                self._rows.append((row, None))
                y += line
                continue
            box = (x0 + pad, y, x0 + card_w - pad, y + row_h)
            self._rows.append((row, box))
            self._draw_row(i, row, box, lit=(i == self.sel[page]))
            y += row_h + line // 2
        hint = (f"{key_names('Up', 'Down')}  choose      {key_names('Return')}  open      "
                f"{key_names('Escape')}  " + ("back to the words" if first else "back"))
        c.create_text(W / 2, min(H - line, y0 + card_h + line * 1.6), text=hint, font=font("label"),
                      fill=PALETTE["text"], tags="hint")
        if slide and self.anim:
            self._slide(slide, line)

    def _draw_row(self, i, row, box, lit):
        c = self.canvas
        line = font("title").metrics("linespace")
        tag = f"row{i}"
        x1, y1, x2, y2 = box
        c.round_rect(x1, y1, x2, y2, round(line * 0.6), fill=PALETTE["select_bg"] if lit else PALETTE["surface"],
                     outline=PALETTE["accent"] if lit else PALETTE["border"], width=3 if lit else 2,
                     tags=(tag, f"{tag}shape", "page"))
        cy = (y1 + y2) / 2
        if len(self.path) == 1:              # (the first page: a tier-coloured chip before each row, like the mock-up)
            chip = round(line * 0.75)
            c.round_rect(x1 + line * 0.6, cy - chip / 2, x1 + line * 0.6 + chip, cy + chip / 2, chip // 3,
                         fill=TIER_COLORS[i % len(TIER_COLORS)], tags=(tag, "page"))
            tx = x1 + line * 0.6 + chip + line * 0.6
        else:
            tx = x1 + line
        c.create_text(tx, cy, text=row[1].rstrip(".").rstrip("…"), anchor="w",
                      font=font("choice") if lit else font("title"), fill=PALETTE["text"], tags=(tag, "page"))
        if row[0] == "page" or (row[0] == "command" and row[1].endswith("...")):
            icon = c.icon_image("next", round(line * 0.7), PALETTE["muted"])
            c.create_image(x2 - line, cy, image=icon, tags=(tag, "page"))
        elif row[0] == "check":
            on = bool(row[2].get())
            sw, sh = round(line * 2.2), round(line * 1.1)
            sx = x2 - line * 0.8 - sw
            c.round_rect(sx, cy - sh / 2, sx + sw, cy + sh / 2, sh // 2,
                         fill=PALETTE["accent"] if on else PALETTE["border"], tags=(tag, "page"))
            k = sh - 6
            kx = sx + sw - 3 - k if on else sx + 3
            c.round_rect(kx, cy - k / 2, kx + k, cy + k / 2, k // 2, fill=PALETTE["surface"], tags=(tag, "page"))

    def _light(self, i):
        """Light row `i` (the pointer or the arrows), with a little pop."""
        page = self.path[-1]
        old = self.sel.get(page)
        self.sel[page] = i
        c = self.canvas
        if c is None:
            return
        if self.anim:
            self.anim.finish("pause_slide")     # (the rows are redrawn where they rest)
        for j in (old, i):
            if j is None or j >= len(self._rows) or self._rows[j][1] is None:
                continue
            row, box = self._rows[j]
            c.delete(f"row{j}")
            self._draw_row(j, row, box, lit=(j == i))
        c.tag_raise("hint")
        if self.anim and self._rows[i][1] is not None:
            x1, y1, x2, y2 = self._rows[i][1]
            r = round(font("title").metrics("linespace") * 0.6)
            grow = 5

            gen = self._gen

            def frame(t, tag=f"row{i}shape"):
                g = grow * (1 - abs(1 - 2 * t))              # out and back: a small pop
                if self.canvas is not None and gen == self._gen:
                    self.canvas.round_rect_coords(tag, x1 - g, y1 - g / 2, x2 + g, y2 + g / 2, r)
            self.anim.run("pause_pop", POP_MS, frame)

    def _slide(self, d, line):
        """The page's rows and title slide in from the side (d=+1 from the right), from a little way off."""
        c = self.canvas
        dist = line * 3 * d
        c.move("page", dist, 0)
        moved = {"x": dist}
        gen = self._gen

        def frame(t):
            if self.canvas is None or gen != self._gen:
                return
            target = dist * (1 - t)
            self.canvas.move("page", target - moved["x"], 0)
            moved["x"] = target
        self.anim.run("pause_slide", SLIDE_MS, frame)


def dialog_bar(dlg, trail, on_back):
    """Full screen: a StyledDialog's top gets a Back button and the trail of pages to it ("Menu > Settings > Tier
    colours"); its own Cancel / Close button goes (Back is that), so does a headline that only repeats the trail's
    last step, and so does the title bar (not on macOS: a window without one gets no keys there): a lilac edge
    instead, like a card. Called by App before the dialog shows."""
    bg = PALETTE["bg"]
    box = dlg.body.master
    bar = tk.Frame(box, bg=bg)
    first = box.winfo_children()[0]
    bar.pack(fill="x", pady=(0, 14), before=first)
    RoundButton(bar, "Back", on_back, bg=PALETTE["surface"], font=font("head"), padx=18, pady=7,
                radius=16, canvas_bg=bg).pack(side="left")
    if trail:
        tk.Label(bar, text=SEP.join(trail[:-1]) + (SEP if len(trail) > 1 else ""), font=font("label"), bg=bg,
                 fg=PALETTE["muted"]).pack(side="left", padx=(14, 0))
        tk.Label(bar, text=trail[-1], font=font("head"), bg=bg, fg=PALETTE["text"]).pack(side="left")
        if dlg.head_row is not None:
            head = dlg.head_row.winfo_children()[0]
            if head.cget("text") == trail[-1]:
                head.pack_forget()
                if len(dlg.head_row.winfo_children()) == 1:
                    dlg.head_row.pack_forget()
    for text in ("Cancel", "Close"):
        b = dlg.buttons.get(text)
        if b is not None:
            b.pack_forget()
    win = dlg.win
    if win.tk.call("tk", "windowingsystem") != "aqua":
        win.overrideredirect(True)
        win.configure(bg=PALETTE["accent"], padx=2, pady=2)
    return bar
