"""Settings > Keyboard shortcuts... (UI-48): every action that has a key, in cards side by side by view (the
layout the user chose, mock-up C). Click a key, press the new one; "+" adds another; a key already used in the
same view offers a swap. Changes apply at once (App.apply_keys) and are saved in the save (meta keymap).

    ShortcutsDialog(app)                  # app: the App (its keymap, store, animator and apply_keys)
"""
import tkinter as tk

from fonts import font
from keymap import (GROUP_NAMES, LABEL_OF, ACTIONS, MAX_KEYS, RESERVED, display, event_spec,
                    place_display, place_keys)
from theme import PALETTE
from widgets import RoundButton, StyledDialog

COLUMNS = (("all", "browse"), ("place", "compare"), ("duel",))     # the cards, left to right


class ShortcutsDialog:
    def __init__(self, app):
        self.app, self.km = app, app.keys
        self.waiting = None                     # (action, slot) while a key is being changed (slot None: a new key)
        self.offer = None                       # a pending swap: (action, new keys, other action, its new keys)
        self.dlg = dlg = StyledDialog(app.root, "Keyboard shortcuts", "Keyboard shortcuts",
                                      "Click a key to change it, then press the new one. Click it again to keep "
                                      "it as it was.", animator=app.anim, wrap_chars=110)
        self.cards = tk.Frame(dlg.body, bg=PALETTE["bg"])
        self.cards.pack(anchor="w")
        self.note = tk.Frame(dlg.body, bg=PALETTE["bg"])
        self.note.pack(anchor="w", fill="x", pady=(12, 0))
        dlg.button("Done", dlg.close, default=True)
        dlg.button("Reset all to defaults", self.reset_all, side="left")
        self.caps = {}                          # (action, slot) -> its keycap, for tests
        self._draw()
        self._say("")
        dlg.show()

    # ---- drawing ------------------------------------------------------------------------------------------
    def _draw(self):
        """The cards, once: a label, a strip of keycaps and a cell for "↺ default" per action. Changes refill
        only the strips (_refresh): rebuilding every row at once (Reset all) emptied the window for a moment, so
        it shrank and showed black."""
        bg, f = PALETTE["bg"], font("body")
        line = f.metrics("linespace")
        self.rows = {}                          # action -> (its keycap strip, its "↺ default" cell)
        for ci, groups in enumerate(COLUMNS):
            col = tk.Frame(self.cards, bg=bg)
            col.grid(row=0, column=ci, sticky="n", padx=(0 if ci == 0 else round(line * 1.4), 0))
            # room for "↺ default" kept on every row, so nothing shifts when one appears
            col.columnconfigure(2, minsize=f.measure("\u21ba default") + 2 * 6 + 4)
            r = 0
            for gi, g in enumerate(groups):
                tk.Label(col, text=GROUP_NAMES[g], bg=bg, fg=PALETTE["muted"], font=f).grid(
                    row=r, column=0, columnspan=3, sticky="w", pady=(0 if gi == 0 else round(line * 0.8), 2))
                r += 1
                for a, ga, _label, _k in ACTIONS:
                    if ga == g:
                        tk.Label(col, text=LABEL_OF[a], bg=bg, fg=PALETTE["text"], font=f, anchor="w").grid(
                            row=r, column=0, sticky="w", pady=2, padx=(0, 12))
                        strip, cell = tk.Frame(col, bg=bg), tk.Frame(col, bg=bg)
                        strip.grid(row=r, column=1, sticky="w")
                        cell.grid(row=r, column=2, sticky="w")
                        self.rows[a] = (strip, cell)
                        r += 1
        self._refresh()

    def _refresh(self, actions=None):
        """Refill these actions' keycaps (all by default). The new ones go in before the old ones go, so a row is
        never empty and the window keeps its size; it only grows if a row needs more room."""
        for a in actions or list(self.rows):
            self._fill(a)
        win = self.dlg.win
        win.update_idletasks()
        if win.winfo_reqwidth() > win.winfo_width() or win.winfo_reqheight() > win.winfo_height():
            self.dlg.refit()

    def _fill(self, action):
        bg, f = PALETTE["bg"], font("body")
        strip, cell = self.rows[action]
        old = strip.winfo_children() + cell.winfo_children()
        self.caps = {k: c for k, c in self.caps.items() if k[0] != action}
        shown = [place_display(self.km.keys["place"][0])] if action == "place" else \
            [display(k) for k in self.km.keys[action]]
        slots = list(range(len(shown)))
        if action != "place" and len(shown) < MAX_KEYS:
            slots.append(None)                                   # "+": another key for it
        for slot in slots:
            waiting = self.waiting == (action, slot)
            if slot is None:
                text, fill, flat = ("\u2026", PALETTE["select_bg"], False) if waiting else ("+", bg, True)
            else:                                       # (waiting: "…", about a key wide, so the row keeps still)
                text = "\u2026" if waiting else shown[slot]
                fill, flat = (PALETTE["select_bg"] if waiting else PALETTE["surface"]), False
            cap = RoundButton(strip, text, lambda a=action, s=slot: self.listen(a, s), bg=fill, font=f, padx=10,
                              pady=2, radius=8, canvas_bg=bg, flat=flat, animator=self.app.anim)
            cap.pack(side="left", padx=(0, 6))
            self.caps[(action, slot)] = cap
            if waiting:
                cap.bind("<Key>", self._caught)
                cap.after_idle(cap.focus_set)
        if not self.km.is_default(action):
            RoundButton(cell, "\u21ba default", lambda a=action: self.reset(a), bg=bg, font=f, padx=6, pady=2,
                        radius=8, canvas_bg=bg, flat=True, animator=self.app.anim).pack(side="left")
        for w in old:
            w.destroy()

    def _say(self, text, buttons=()):
        """The line under the cards: what is happening, and the buttons for it (Swap, Remove...)."""
        old = self.note.winfo_children()                 # (removed after the new line is in: no jump)
        bg = PALETTE["bg"]
        tk.Label(self.note, text=text or " ", bg=bg, fg=PALETTE["warn"][1], font=font("body")).pack(side="left")
        for label, command in buttons:
            RoundButton(self.note, label, command, bg=PALETTE["surface"], font=font("body"), padx=10, pady=2,
                        radius=10, canvas_bg=bg, animator=self.app.anim).pack(side="left", padx=(8, 0))
        for w in old:
            w.destroy()
        self.note_text = text

    # ---- changing a key -------------------------------------------------------------------------------------
    def listen(self, action, slot):
        """A keycap was clicked: wait for its new key (the same one again: keep it as it was)."""
        if self.waiting == (action, slot):
            self.cancel()
            return
        self.waiting, self.offer = (action, slot), None
        self._refresh()
        what = LABEL_OF[action]
        if action == "place":
            self._say("Press the first of the six placing keys: the other five follow it along its row (1, Q, A, "
                      "Z, F1...)", [("Cancel", self.cancel)])
        elif slot is None:
            self._say(f"Press another key for {what}", [("Cancel", self.cancel)])
        else:
            self._say(f"Press the new key for {what}", [("Remove this key", self.remove), ("Cancel", self.cancel)])

    def cancel(self):
        self.waiting = self.offer = None
        self._refresh()
        self._say("")

    def _caught(self, e):
        self.press(event_spec(e.keysym, getattr(e, "state", 0), self.app._ws))
        return "break"                          # (Enter, Escape, Tab... are the new key, not the dialog's)

    def press(self, spec):
        """The new key for the waiting keycap (a key name, as keymap.event_spec gives it)."""
        if self.waiting is None or spec is None:
            return
        action, slot = self.waiting
        if spec in RESERVED:
            self._say(f"{display(spec)} {RESERVED[spec]}: pick another key", [("Cancel", self.cancel)])
            return
        if action == "place":
            if place_keys(spec) is None:
                self._say(f"{display(spec)} has no five keys after it on its row: try 1, Q, A, Z or F1",
                          [("Cancel", self.cancel)])
                return
            new = [spec]
        else:
            old = self.km.keys[action]
            if slot is None:                             # another key for it (moved to the end if it had it)
                new = [k for k in old if k != spec] + [spec]
            else:                                        # this key changed (and not twice in the list)
                new = [spec if i == slot else k for i, k in enumerate(old)]
                new = [k for i, k in enumerate(new) if k != spec or i == slot]
        specs = place_keys(new[0]) if action == "place" else new
        clash = self.km.clash(action, specs)
        if clash and clash[0] == "place":                # one of the six: they move only as a set
            self._say(f"{display(clash[1])} is one of the placing keys ({place_display(self.km.keys['place'][0])}): "
                      f"pick another key, or move the placing keys first", [("Cancel", self.cancel)])
            return
        if clash:
            other, key = clash
            mine = self.km.keys_of(action)
            given = mine[specs.index(key)] if action == "place" else (mine[slot] if slot is not None else None)
            theirs = [k for k in self.km.keys[other] if k != key]
            if given is not None and given not in theirs:
                theirs.insert(self.km.keys[other].index(key), given)
            self.offer = (action, new, other, theirs)
            was = f": {LABEL_OF[other]} gets {display(given)}" if given else ""
            self._say(f"{display(key)} is already {LABEL_OF[other]}. Swap them{was}?",
                      [("Swap", self.swap), ("Cancel", self.cancel)])
            return
        self._apply({action: new})

    def swap(self):
        if self.offer:
            action, new, other, theirs = self.offer
            self._apply({action: new, other: theirs})
            left = self.km.clash(action, self.km.keys_of(action))    # (the placing set can meet two)
            if left:
                self._say(f"{display(left[1])} is also {LABEL_OF[left[0]]}: change one of them")

    def remove(self):
        if self.waiting is None:
            return
        action, slot = self.waiting
        keys = list(self.km.keys[action])
        if slot is not None and slot < len(keys):
            del keys[slot]
            self._apply({action: keys})

    def reset(self, action):
        self.km.reset(action)
        self.waiting = self.offer = None
        self._saved(f"{LABEL_OF[action]} is back to its default")

    def reset_all(self):
        self.km.reset()
        self.waiting = self.offer = None
        self._saved("Every key is back to its default")

    def _apply(self, changes):
        for a, ks in changes.items():
            self.km.set(a, ks)
        self.waiting = self.offer = None
        names = " and ".join(LABEL_OF[a] for a in changes)
        self._saved(f"Saved: {names}")

    def _saved(self, text):
        self.app.store.set_meta("keymap", self.km.dumps())
        self.app.apply_keys()
        self._refresh()
        self._say(text)
        self.note.winfo_children()[0].configure(fg=PALETTE["muted"])
