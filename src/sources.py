"""File > Source & Updates... (T-6, T-7): one menu item, one dialog, whose action fits the form you are running.

    SourceDialog(app)       from source: make a standalone program; in the built program: unpack its source

From source (T-6), "Make the program" builds a one-file program for this computer from the source as it is now
(src/standalone.py, behind the progress window), puts it next to tierlist.py so it keeps using the same save (T-1),
then starts it and closes this window. When the program there was built from exactly this source, it offers to
start that instead.

In the built program (T-7), "Unpack" writes the source it carries into a folder (beside the program unless you pick
another), in the same layout as the repository (R-1). Into a folder that already has it, it syncs rather than copies:
changed files are updated, new ones added, and ones the program no longer has removed; only the program's own files
are ever touched, and a file you edited there is kept as name.bak first. What it will do is shown before it does
it. Then it opens the folder and offers to start tierlist.py from it (that needs a Python on this computer).
"""
import os
import subprocess
import time
from tkinter import filedialog, ttk

import standalone
from errors import ask_yes_no, show_error, show_message
from filepicker import browse, use_themed
from fonts import font
from problems import STOPPED_MESSAGE
from saves import is_frozen
from startup import run_with_progress
from theme import PALETTE
from widgets import StyledDialog

HEADLINE = "Make a standalone program"
INTRO = ("Builds Word Tier List into one program for this computer, with its source code inside it. It keeps using "
         "the same save, and Python is no longer needed to run it. It takes a minute or two; the first time, it "
         "also installs the builder (PyInstaller, about 15 MB).")
UNPACK_HEADLINE = "Unpack the source code"
UNPACK_INTRO = ("Writes the source code this program was built from into a folder: the program files, the tests and "
                "the notes, exactly as they were. Into a folder that already has them it brings them up to date, "
                "changing only the program's own files; anything you edited there is kept as a .bak copy first.")


class SourceDialog:
    def __init__(self, app, root_dir=None, source=None, frozen=None):
        """`root_dir`: the project (from source); `source`: the source the program carries, and `frozen`: which
        side to show (tests pass them; the program finds them itself)."""
        self.app = app
        self.frozen = is_frozen() if frozen is None else frozen
        if self.frozen:
            self.source = source or standalone.bundled_source()
            self._unpack_page()
        else:
            self.root_dir = root_dir or standalone.ROOT
            self._make_page()
        self.dlg.show()

    # ---- from source: make the program (T-6) --------------------------------------------------------------------
    def _make_page(self):
        self.dlg = dlg = StyledDialog(self.app.root, "Source & Updates", HEADLINE, INTRO, animator=self.app.anim,
                                      wrap_chars=64)
        path = standalone.program_path(self.root_dir)
        self.fresh = standalone.up_to_date(self.root_dir)
        built = standalone.last_build(self.root_dir)
        if self.fresh:
            when = time.strftime("%d %b %Y, %H:%M", time.localtime(built.get("made", 0)))
            state = f"Nothing has changed since it was built ({when}): it can start straight away."
        elif built and os.path.exists(path):
            state = "The source has changed since the program there was built: it is built again from this source."
        else:
            state = None
        self.where = ttk.Label(dlg.body, text=f"It goes next to tierlist.py:\n{path}", foreground=PALETTE["muted"],
                               wraplength=dlg.wrap, justify="left")
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

    # ---- in the built program: unpack its source (T-7) ----------------------------------------------------------
    def _unpack_page(self):
        self.dlg = dlg = StyledDialog(self.app.root, "Source & Updates", UNPACK_HEADLINE, UNPACK_INTRO,
                                      animator=self.app.anim, wrap_chars=64)
        if not self.source:
            ttk.Label(dlg.body, text="This program was built without its source code inside it, so there is "
                      "nothing to unpack.", wraplength=dlg.wrap, justify="left").pack(anchor="w")
            dlg.button("Close", dlg.close, default=True)
            return
        self.target = standalone.default_source_folder()
        row = ttk.Frame(dlg.body)
        row.pack(fill="x", anchor="w")
        self.where = ttk.Label(row, text="", foreground=PALETTE["muted"], wraplength=dlg.wrap - 140, justify="left")
        self.where.pack(side="left", anchor="w")
        self.state = ttk.Label(dlg.body, text="", font=font("body"), wraplength=dlg.wrap, justify="left")
        self.state.pack(anchor="w", pady=(10, 0))
        dlg.button("Change folder...", self.change_folder, side="left")
        dlg.button("Cancel", dlg.close)
        dlg.button("Unpack", self.unpack, default=True)
        self._show_plan()

    def _show_plan(self):
        """Say where it goes and what it would do there."""
        self.plan = standalone.plan_unpack(self.source, self.target)
        fresh = not os.path.exists(self.target) or not os.listdir(self.target)
        self.where.config(text=f"Into:\n{self.target}")
        self.state.config(text="A new folder: every file is added." if fresh else
                          "That folder already has files: " + standalone.summary(self.plan)[0].lower()
                          + standalone.summary(self.plan)[1:])
        self.dlg.refit()

    def change_folder(self):
        start = self.target if os.path.isdir(self.target) else os.path.dirname(self.target)
        if use_themed(self.app.root):
            folder = browse(self.dlg.win, "Unpack the source code into", start, mode="folder", animator=self.app.anim,
                            note="Pick a new or empty folder, or one you unpacked into before to bring it up to date.")
        else:
            folder = filedialog.askdirectory(parent=self.dlg.win, initialdir=start, title="Unpack the source code into")
        if folder:
            self.target = folder
            self._show_plan()

    def unpack(self):
        """Unpack (or sync), then open the folder and offer to start tierlist.py from it."""
        try:
            plan = standalone.unpack(self.source, self.target, self.plan)
        except OSError as exc:
            show_error("Unpack the source code", f"The source could not be written to {self.target}:\n{exc}",
                       parent=self.dlg.win, headline="Not unpacked")
            return None
        self.dlg.close()
        try:
            standalone.open_folder(self.target)
        except OSError:
            pass                                  # (no file manager: the message below says where it is)
        done = standalone.summary(plan)
        python = standalone.python_for_source()
        script = os.path.join(self.target, "tierlist.py")
        if python and ask_yes_no("Unpack the source code", "Source unpacked",
                                 f"{done}\n\nIt is in {self.target}. Start tierlist.py from there now? It uses the "
                                 "same save as this program.", yes="Start it", no="Not now", parent=self.app.root,
                                 wrap_chars=60):
            subprocess.Popen([python, script], cwd=self.target, start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif not python:
            show_message("Unpack the source code", "Source unpacked",
                         f"{done}\n\nIt is in {self.target}. To run it, install Python 3 (python.org), then start "
                         "tierlist.py there.", parent=self.app.root)
        return plan

    # ---- for tests ----------------------------------------------------------------------------------------------
    @property
    def buttons(self):
        return self.dlg.buttons

    def alive(self):
        return self.dlg.alive()

    def close(self):
        self.dlg.close()
