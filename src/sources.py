"""File > Source & Updates... (T-6; T-7 adds the built program's side): from source, make a standalone program.

    SourceDialog(app)       the page: what it does, where the program goes, and whether one is already up to date

"Make the program" builds a one-file program for this computer from the source as it is now (src/standalone.py,
behind the progress window), puts it next to tierlist.py so it keeps using the same save (T-1), then starts it and
closes this window. When the program there was built from exactly this source, it offers to start that instead.
"""
import os
import time
from tkinter import ttk

import standalone
from errors import show_error
from fonts import font
from problems import STOPPED_MESSAGE
from startup import run_with_progress
from theme import PALETTE
from widgets import StyledDialog

HEADLINE = "Make a standalone program"
INTRO = ("Builds Word Tier List into one program for this computer, with its source code inside it. It keeps using "
         "the same save, and Python is no longer needed to run it. It takes a minute or two; the first time, it "
         "also installs the builder (PyInstaller, about 15 MB).")


class SourceDialog:
    def __init__(self, app, root_dir=None):
        self.app = app
        self.root_dir = root_dir or standalone.ROOT
        self.dlg = dlg = StyledDialog(app.root, "Source & Updates", HEADLINE, INTRO, animator=app.anim, wrap_chars=64)
        path = standalone.program_path(self.root_dir)
        self.fresh = standalone.up_to_date(self.root_dir)
        built = standalone.last_build(self.root_dir)
        where = f"It goes next to tierlist.py:\n{path}"
        if self.fresh:
            when = time.strftime("%d %b %Y, %H:%M", time.localtime(built.get("made", 0)))
            state = f"Nothing has changed since it was built ({when}): it can start straight away."
        elif built and os.path.exists(path):
            state = "The source has changed since the program there was built: it is built again from this source."
        else:
            state = None
        self.where = ttk.Label(dlg.body, text=where, foreground=PALETTE["muted"], wraplength=dlg.wrap, justify="left")
        self.where.pack(anchor="w")
        if state:
            self.state = ttk.Label(dlg.body, text=state, font=font("body"), wraplength=dlg.wrap, justify="left")
            self.state.pack(anchor="w", pady=(10, 0))
        dlg.button("Cancel", dlg.close)
        if self.fresh:
            dlg.button("Build again", self.make)
            dlg.button("Start it", lambda: self.start(path), default=True)
        else:
            dlg.button("Make the program", self.make, default=True)
        dlg.show()

    def make(self):
        """Build behind the progress window, then start the new program and close this one."""
        app = self.app
        self.dlg.close()
        lines = []

        def work(log):
            def keep(text):
                lines.append(str(text))
                log(text)
            return standalone.make_program(self.root_dir, keep)
        try:
            path = run_with_progress(app.root, work, title="Making a standalone program", delay_ms=0,
                                     initial_stage="Getting ready...", intro="Building the program for this computer.")
        except SystemExit as exc:                 # the progress window was closed: carry on here
            if str(exc) != STOPPED_MESSAGE:
                raise
            app.flash("Stopped: no program was made", ms=3000)
            return None
        if not path:
            show_error("Make a standalone program", "The program could not be built. The details below say why; "
                       "your save and the source are unchanged.", details="\n".join(lines[-40:]), parent=app.root,
                       headline="Not built")
            return None
        self.start(path)
        return path

    def start(self, path):
        """Start the program next to tierlist.py and close this window (the save is closed cleanly first)."""
        self.dlg.close()
        standalone.start(path)
        self.app.on_close()

    # ---- for tests ----------------------------------------------------------------------------------------------
    @property
    def buttons(self):
        return self.dlg.buttons

    def alive(self):
        return self.dlg.alive()

    def close(self):
        self.dlg.close()
