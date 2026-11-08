"""The shared dialog frame (UI-24): StyledDialog, a bold headline, a muted line of explanation, a body to fill and a row
of rounded buttons. Every dialog is built on it (errors.show_message / ask_yes_no / show_error for the simple ones):
built withdrawn, placed, then shown with ui_style.show_drawn (F-48). dialog_open says whether one is on screen.
"""
import tkinter as tk
from tkinter import ttk

from fonts import font
from sizing import keep_on_screen, place_dialog
from theme import PALETTE
from ui_style import unveil, veil
from buttons import DevBubble, RoundButton


def dialog_open(root):
    """True while one of our dialogs (StyledDialog: a question, a message, a settings page) is on screen."""
    try:
        return any(getattr(w, "styled_dialog", False) and w.winfo_viewable() for w in root.winfo_children())
    except tk.TclError:
        return False


class StyledDialog:
    """The shared dialog frame (UI-24): a bold headline, a muted line of explanation, a body to fill and
    a row of rounded buttons, the default one (what Enter presses) in lilac and on the right.

        dlg = StyledDialog(parent, "Anchor words", "Pick one word per tier", "New words are compared...")
        ttk.Entry(dlg.body, ...).pack()
        dlg.button("Cancel", dlg.close)
        dlg.button("Save anchors", save, default=True)
        dlg.show()                    # centre over the parent and take the input; wait=True blocks

    Buttons line up left to right in the order added, at the right edge (side="left" puts one at the
    far left instead, like "Show details"). Escape and the close box call on_cancel (default: close).
    """

    decorate = None    # full screen (FS-2): called with the dialog just before it shows (App._dialog_bar: Back)

    def __init__(self, parent, title, headline=None, intro=None, animator=None, wrap_chars=52):
        self.parent, self._anim, self._default = parent, animator, None
        self._when_closed = []
        self._follow_job = None              # (rescale: follows the parent's moves for a moment)
        self.on_cancel = self.close
        bg = PALETTE["bg"]
        self.win = tk.Toplevel(parent)
        self.win.styled_dialog = True            # (a question or message is open: dialog_open)
        self.win.dialog = self                   # (refresh_widgets: an open dialog follows a new text size)
        self._wrap_chars = wrap_chars
        # hidden until show() has sized and centred it: built while showing, it appeared where the window
        # manager put it (the parent's top left) and then jumped to the middle
        self.win.withdraw()
        self.win.bind("<Destroy>", lambda e: e.widget is self.win and self._closed(), add="+")
        self.win.title(title)
        self.win.configure(bg=bg)
        self.win.resizable(False, False)
        try:
            if parent.winfo_viewable():
                self.win.transient(parent)
        except tk.TclError:
            pass
        self.wrap = max(380, font("body").measure("n") * wrap_chars)
        box = tk.Frame(self.win, bg=bg, padx=26, pady=22)
        box.pack(fill="both", expand=True)
        self.head_row = None             # (the headline's row: developer bubbles go at its right, dev_bubbles)
        if headline:
            self.head_row = tk.Frame(box, bg=bg)
            self.head_row.pack(fill="x")
            tk.Label(self.head_row, text=headline, font=font("head"), bg=bg, fg=PALETTE["text"],
                     wraplength=self.wrap, justify="left").pack(side="left", anchor="w")
        if intro:
            tk.Label(box, text=intro, font=font("body"), bg=bg, fg=PALETTE["muted"], wraplength=self.wrap,
                     justify="left").pack(anchor="w", pady=(8 if headline else 0, 0))
        self.body = tk.Frame(box, bg=bg)
        self.body.pack(fill="both", expand=True, pady=(14 if headline or intro else 0, 0))
        self.button_row = tk.Frame(box, bg=bg)
        self.button_row.pack(fill="x", pady=(18, 0))
        self._right = tk.Frame(self.button_row, bg=bg)
        self._right.pack(side="right")
        self.buttons = {}
        self.win.bind("<Return>", lambda e: self._default.invoke() if self._default else None)
        self.win.bind("<Escape>", lambda e: self.on_cancel())
        self.win.protocol("WM_DELETE_WINDOW", lambda: self.on_cancel())

    def dev_bubbles(self, items):
        """Developer tools as small bubbles (DevBubble) at the right of the headline, in the order given: `items` are
        (text, command), or (text, command, variable) for a switch. Returns the bubbles, by text."""
        out = {}
        if self.head_row is None or not items:
            return out
        row = tk.Frame(self.head_row, bg=PALETTE["bg"])
        row.pack(side="right", anchor="n", padx=(24, 0))
        for item in items:
            text, command, variable = (tuple(item) + (None,))[:3]
            b = DevBubble(row, text, command, variable=variable)
            b.pack(side="left", padx=(6 if out else 0, 0))
            out[text] = b
        return out

    def text(self, text, muted=False, parent=None, room=0, **pack):
        """A wrapped line of text in the body (or `parent`), packed to the left (`pack`: more pack options); muted
        for notes. `room`: pixels to leave beside it. Returns the label (its text can change later)."""
        label = ttk.Label(parent or self.body, text=text, wraplength=self.wrap - room, justify="left",
                          **({"foreground": PALETTE["muted"]} if muted else {"font": font("body")}))
        label.pack(**dict({"anchor": "w"}, **pack))
        return label

    def button(self, text, command, default=False, side="right", row=None):
        """Add a rounded button; `default` makes it the lilac one Enter presses. `row`: a frame of the body's to put
        it in instead of the bottom row (a section's own buttons), packed left to right."""
        row = row or (self._right if side == "right" else self.button_row)
        pad = 0 if row is self.button_row or not row.winfo_children() else 8
        b = RoundButton(row, text, command, bg=PALETTE["select_bg"] if default else PALETTE["surface"],
                        font=font("body"), padx=16, pady=6, radius=12, animator=self._anim)
        b.pack(side="left", padx=(pad, 0))
        self.buttons[text] = b
        if default:
            self.make_default(b)
        return b

    def make_default(self, button):
        """Make `button` the lilac one Enter presses (the one before goes back to the plain look)."""
        if self._default is not None and self._default is not button:
            try:
                self._default.config(bg=PALETTE["surface"])
            except tk.TclError:
                pass
        self._default = button
        button.config(bg=PALETTE["select_bg"])

    def clear_buttons(self):
        """Take every button (and anything else in the button row) away, to put others there (a page of steps)."""
        for w in (*self.button_row.winfo_children(), *self._right.winfo_children()):
            if w is not self._right:
                w.destroy()
        self.buttons, self._default = {}, None

    def show(self, wait=False):
        """Size to the contents, centre over the parent, then appear there; take the input (and with wait, block
        until closed)."""
        if StyledDialog.decorate is not None and not getattr(self, "_decorated", False):
            self._decorated = True
            StyledDialog.decorate(self)
        place_dialog(self.win, self.parent)
        veil(self.win)                   # drawn while see-through: it appears complete, not piece by piece
        self.win.deiconify()
        try:                             # some Linux window managers refuse a grab before the window shows
            self.win.wait_visibility()
            self.win.grab_set()
        except tk.TclError:
            pass
        unveil(self.win)
        self.win.lift()                  # in front, even of a window that was raised a moment before
        self.win.focus_force()
        if wait:
            self.win.wait_window()

    def refit(self):
        """Re-size to the contents after something was shown or hidden, kept on its monitor (a dialog that grew
        could run off the bottom of a small screen)."""
        self.win.update_idletasks()
        self.win.geometry("")
        keep_on_screen(self.win)

    def rescale(self):
        """The shared fonts were resized while it is open (the main window's zoom: maximizing brings back its own,
        UI-57): every wrapped line is re-wrapped in proportion to the new text size, then the dialog is sized to
        its contents again and centred over its parent, kept on its monitor. Before, the text grew inside a
        window that kept its size and was cut off (reported)."""
        wrap = max(380, font("body").measure("n") * self._wrap_chars)
        ratio = wrap / self.wrap if self.wrap else 1.0
        self.wrap = wrap
        if ratio != 1.0:
            stack = [self.win]
            while stack:
                w = stack.pop()
                stack.extend(w.winfo_children())
                try:
                    if isinstance(w, (tk.Label, ttk.Label)) and int(str(w.cget("wraplength")) or 0) > 0:
                        w.configure(wraplength=max(1, round(int(str(w.cget("wraplength"))) * ratio)))
                except (tk.TclError, ValueError):
                    pass
        def place():                    # (after the parent's own new size is settled: maximizing moves it too)
            try:
                if self.win.winfo_viewable():
                    place_dialog(self.win, self.parent)
            except tk.TclError:
                pass
        place()
        self.win.after_idle(place)
        # (and where the parent goes next, for a moment: a maximize re-fits inside its first <Configure>, F-50, and
        # macOS moves the window back onto the screen after that; the dialog stayed centred on where it had been)
        if self._follow_job is not None:
            self.win.after_cancel(self._follow_job)
        where = [None]
        def follow(n):
            self._follow_job = None
            try:
                now = (self.parent.winfo_rootx(), self.parent.winfo_rooty(), self.parent.winfo_width())
            except tk.TclError:
                return
            if where[0] is not None and now != where[0]:
                place()
            where[0] = now
            if n > 0 and self.alive():
                self._follow_job = self.win.after(self.FOLLOW_EVERY_MS, follow, n - 1)
        follow(self.FOLLOW_MS // self.FOLLOW_EVERY_MS)

    FOLLOW_MS, FOLLOW_EVERY_MS = 1000, 50

    def close(self):
        if self._follow_job is not None:
            self.win.after_cancel(self._follow_job)
            self._follow_job = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def alive(self):
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def when_closed(self, callback):
        """Call `callback` once the dialog has gone, however it closed (a button, Escape, the close box)."""
        self._when_closed.append(callback)

    def _closed(self):
        calls, self._when_closed = self._when_closed, []
        for cb in calls:              # (after the destroy has finished: the menu is not built inside it)
            try:
                self.parent.after_idle(cb)
            except tk.TclError:
                pass
