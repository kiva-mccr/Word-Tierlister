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

The first start of either form offers the other once (T-9: App._offer_other_form), and a yes does it straight
away (go=True). Either way a tick box, ticked to start with, says "Update to the newest version first" (T-8): the dialog asks
GitHub for the newest release in the background (standalone.latest_release) and says in a line what it found.
Ticked and newer, "Make the program" downloads that version's source and builds from it, and "Unpack" downloads
it and shows what unpacking it would change before it does it; offline, or with no newer version, it says so and
uses the version you have. From source, a newer version also shows "Update the source only" (asked for): it
downloads that version and brings this folder up to date with it (the same sync as unpacking, shown first), without
making the program, then starts again from it with the same save. Such a folder is never offered to be cleaned up
behind (standalone.came_from_program).
"""
import os
import queue
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk

import deps
import standalone
from errors import ask_yes_no, show_error, show_message
from filepicker import browse, use_themed
from problems import STOPPED_MESSAGE, SetupError
from saves import is_frozen, remember_save
from startup import ensure_packages, offer_system_install, run_with_progress
from widgets import StyledDialog
from constants import VERSION

HEADLINE = "Make a standalone program"
UPDATE_SOURCE = "Update the source only"
INTRO = ("Builds Word Tier List into one program for this computer, with its source code inside it. It keeps using "
         "the same save, and Python is no longer needed to run it. It takes a minute or two; the first time, it "
         "asks to install the builder (PyInstaller, about 15 MB) and anything else the program needs.")
UNPACK_HEADLINE = "Unpack the source code"
UNPACK_INTRO = ("Writes the source code this program was built from into a folder: the program files, the tests and "
                "the notes, exactly as they were. Into a folder that already has them it brings them up to date, "
                "changing only the program's own files; anything you edited there is kept as a .bak copy first.")


class SourceDialog:
    def __init__(self, app, root_dir=None, source=None, frozen=None, check=None, go=False):
        """`root_dir`: the project (from source); `source`: the source the program carries, and `frozen`: which
        side to show; `check() -> release or None`: how to find the newest release (tests pass them; the program
        finds them itself). `go`: do it straight away, without showing the page (T-9's "yes": make the program,
        or unpack beside it, from the version you have); if unpacking fails, the page shows to try elsewhere."""
        self.app = app
        self.frozen = is_frozen() if frozen is None else frozen
        self.release = None                       # the newest release, once the check has found one
        self.fetched = None                       # (unpacking) the newer version's source, once downloaded
        if self.frozen:
            self.source = source or standalone.bundled_source()
            self._unpack_page()
        else:
            self.root_dir = root_dir or standalone.ROOT
            self._make_page()
        if go and "Unpack" in self.dlg.buttons:
            self.unpack()
            if self.dlg.alive():                 # (it could not: the page, to pick another folder)
                self.dlg.show()
            return
        if go and not self.frozen:
            self.make()
            return
        if hasattr(self, "update_var"):
            self._start_check(check or standalone.latest_release)
        self.dlg.show()

    # ---- "Update to the newest version first" (T-8) -------------------------------------------------------------
    def _update_row(self):
        """The tick box and the line under it saying what the check found."""
        dlg = self.dlg
        self.update_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dlg.body, text="Update to the newest version first", variable=self.update_var,
                        command=self._show_update, takefocus=1).pack(anchor="w", pady=(12, 0))
        self.update_line = dlg.text(f"Version {VERSION}. Checking GitHub for a newer one...", muted=True,
                                    padx=(24, 0))
        self.checked = False

    def _start_check(self, check):
        """Ask GitHub on a worker thread (it never touches the window); the answer is collected every 100 ms."""
        answer = queue.Queue()
        threading.Thread(target=lambda: answer.put(check()), daemon=True).start()

        def collect():
            if not self.dlg.alive():
                return
            try:
                self.release = answer.get_nowait()
            except queue.Empty:
                self.dlg.win.after(100, collect)
                return
            self.checked = True
            self._show_update()
            if not self.frozen and standalone.newer(self.release) and UPDATE_SOURCE not in self.dlg.buttons:
                self.dlg.button(UPDATE_SOURCE, self.update_source, side="left")      # (asked for: no build)
                self.dlg.refit()
        collect()

    def wants_update(self):
        """True if ticked and the newest release is newer than this version (and not downloaded yet)."""
        return self.update_var.get() and standalone.newer(self.release) and not self.fetched

    def _show_update(self):
        if not self.checked:
            return
        r = self.release
        if self.fetched:
            text = f"Version {r['version']} downloaded: above is what unpacking it changes."
        elif not r:
            text = f"Version {VERSION}. GitHub could not be reached (or has no release yet): using the version you have."
        elif not standalone.newer(r):
            text = f"Version {VERSION}: the newest there is."
        elif self.update_var.get():
            what = "builds the program from it" if not self.frozen else "downloads it and shows what it changes"
            text = f"Version {r['version']} is out (you have {VERSION}): {self._action()} {what}."
        else:
            text = f"Version {r['version']} is out (you have {VERSION}); unticked, yours is used."
        if not self.frozen and standalone.newer(r):
            text += f' "{UPDATE_SOURCE}" brings this folder up to date without making the program.'
        self.update_line.config(text=text)
        self.dlg.refit()

    def _action(self):
        names = [n for n in self.dlg.buttons if n not in ("Cancel", "Change folder...", "Start it", UPDATE_SOURCE)]
        return f'"{names[0]}"' if names else "it"

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
        self.where = dlg.text(f"It goes next to tierlist.py:\n{path}", muted=True)
        if state:
            self.state = dlg.text(state, pady=(10, 0))
        self._update_row()
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
        if not self.packages_ready():
            return None
        lines = []
        place = standalone.cleanup_place(self.root_dir)       # (an unpacked source with no program beside it: T-12)
        if place and not ask_yes_no(HEADLINE, "Clean up behind?",
                                    "This source was unpacked from the program. Put the new program beside its folder, "
                                    f"in {place}, and then remove the source folder? Your save moves next to the "
                                    "program first; only the program's own files are removed, anything you added "
                                    "there stays.", yes="Clean up", no="Keep the source", parent=app.root,
                                    wrap_chars=62):
            place = None                          # (no: the program goes next to tierlist.py, as always)
        release = self.release if self.wants_update() else None

        def work(log):
            def keep(text):
                lines.append(str(text))
                log(text)
            kw = {"place": place} if place else {}
            if release:
                return standalone.make_program(self.root_dir, keep, release=release, **kw)
            return standalone.make_program(self.root_dir, keep, **kw)
        try:
            path = run_with_progress(app.root, work, title="Making a standalone program", delay_ms=0,
                                     initial_stage="Getting ready...", intro="Building the program for this computer.")
        except SystemExit as exc:                 # the progress window was closed: carry on here
            if str(exc) != STOPPED_MESSAGE:
                raise
            app.flash("Stopped: no program was made", ms=3000)
            return None
        except OSError as exc:                    # the newer version could not be downloaded
            lines.append(str(exc))
            path = None
        if not path:
            show_error("Make a standalone program", "The program could not be built. The details below say why; "
                       "your save and the source are unchanged.", details="\n".join(lines[-40:]), parent=app.root,
                       headline="Not built")
            return None
        if place:
            self.start_cleaned(path, place)
        else:
            self.start(path)
        return path

    def update_source(self, fetch=None):
        """"Update the source only" (asked for): download the newest version's source and bring this folder up to
        date with it, without making the program, then start again from it with the same save. What it changes is
        shown first; only the program's own files change (an edited one is kept as .bak first), and the folder is
        not marked as unpacked from the program (so it is never offered to be cleaned up behind). `fetch`: tests."""
        app, release = self.app, self.release
        folder = tempfile.mkdtemp(prefix="wtl-release-")
        try:
            folder = run_with_progress(app.root, lambda log: (fetch or standalone.fetch_source)(release, folder, log),
                                       title="Downloading the newest version", delay_ms=0,
                                       initial_stage="Connecting...", intro=f"Version {release['version']}, from GitHub.")
        except SystemExit as exc:
            if str(exc) != STOPPED_MESSAGE:
                raise
            return None
        except OSError as exc:
            show_error(HEADLINE, f"The newest version could not be downloaded:\n{exc}", parent=self.dlg.win,
                       headline="Not updated")
            return None
        plan = standalone.plan_unpack(folder, self.root_dir)
        git = os.path.isdir(os.path.join(self.root_dir, ".git"))
        if not ask_yes_no("Source & Updates", f"Update the source to version {release['version']}?",
                          f"{standalone.summary(plan)}\n\nIn {self.root_dir}. Only the program's own files change; "
                          "your save and anything else there stay as they are. Word Tier List then starts again from "
                          "the new source, with the same save."
                          + ("\n\nThis folder is a git checkout: git pull is the usual way to update it." if git else ""),
                          yes="Update", no="Cancel", parent=self.dlg.win, wrap_chars=60):
            return None
        try:
            standalone.unpack(folder, self.root_dir, plan, from_program=False)
        except OSError as exc:
            show_error(HEADLINE, f"The source could not be updated in {self.root_dir}:\n{exc}", parent=self.dlg.win,
                       headline="Not updated")
            return None
        self.dlg.close()
        standalone.start_source(self.root_dir, sys.executable, args=["--db", app.store.path])
        app.on_close()                            # (one at a time on a save: the new source takes over)
        return plan

    def start_cleaned(self, path, place):
        """Clean up behind (T-12): close this window and its save, move the save next to the new program if it is
        inside the source folder (it is the one used from now on), then start the program, which removes this
        source folder as it starts. The save is marked as having given out its source, so the program does not
        unpack it again."""
        store = self.app.store
        store.set_meta("offered_source", "1")
        save = store.path
        self.dlg.close()
        self.app.on_close()
        if os.path.realpath(save).startswith(os.path.realpath(self.root_dir) + os.sep):
            save = standalone.move_save(save, place)
        remember_save(save)
        standalone.start(path, args=["--remove-source", self.root_dir])

    def packages_ready(self, ensure=None):
        """Before a build: what goes into the program (wordfreq, and nltk if wanted) and the builder (PyInstaller)
        must be installed. Anything missing is offered in one dialog, a tick box each, as on the first start
        (startup.ensure_packages: required ones marked, so "all" or "only what is needed" is a tick away); an
        optional one said no to at the first start is offered again (a program is built once, without it for
        good). True when the build can go ahead; otherwise it says why. `ensure`: tests pass their own."""
        try:
            ok = (ensure or ensure_packages)(self.app.root, deps.REQUIRED + list(deps.BUILD_PACKAGES),
                                             optional=deps.OPTIONAL)
        except SetupError as exc:
            show_error(HEADLINE, str(exc), parent=self.app.root, headline="Could not install what the build needs")
            return False
        if not ok:
            gone = deps.missing(deps.REQUIRED + list(deps.BUILD_PACKAGES))
            show_message(HEADLINE, "Not made", f"The program needs {' and '.join(gone)} to be built, and "
                         f"{'they were' if len(gone) > 1 else 'it was'} not installed. Your save and the source are "
                         "unchanged.", parent=self.app.root)
        return ok

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
            dlg.text("This program was built without its source code inside it, so there is nothing to unpack.")
            dlg.button("Close", dlg.close, default=True)
            return
        self.target = standalone.default_source_folder()
        row = ttk.Frame(dlg.body)
        row.pack(fill="x", anchor="w")
        self.where = dlg.text("", muted=True, parent=row, room=140, side="left")
        self.state = dlg.text("", pady=(10, 0))
        self._update_row()
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

    def fetch(self):
        """Download the newer version's source behind the progress window, then show what unpacking it changes
        (the next "Unpack" does it). Returns True if it was downloaded."""
        release, folder = self.release, tempfile.mkdtemp(prefix="wtl-release-")
        try:
            folder = run_with_progress(self.app.root, lambda log: standalone.fetch_source(release, folder, log),
                              title="Downloading the newest version", delay_ms=0, initial_stage="Connecting...",
                              intro=f"Version {release['version']}, from GitHub.")
        except SystemExit as exc:
            if str(exc) != STOPPED_MESSAGE:
                raise
            return False
        except OSError as exc:
            show_error("Unpack the source code", f"The newest version could not be downloaded:\n{exc}\n\nUntick "
                       "the update to unpack the version you have.", parent=self.dlg.win, headline="Not downloaded")
            return False
        self.fetched = self.source = folder
        self._show_plan()
        self._show_update()
        return True

    def unpack(self):
        """Unpack (or sync), then open the folder and offer to start tierlist.py from it. Ticked to update and a
        newer version out: download it first and show what it changes instead (fetch)."""
        if self.wants_update():
            self.fetch()
            return None
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
        if not python and offer_system_install(self.app.root, "python", "Running the unpacked source needs Python "
                                               "on this computer, which it does not have yet."):
            python = standalone.python_for_source()      # (on Windows a new install may need a new session first)
        if python and ask_yes_no("Unpack the source code", "Source unpacked",
                                 f"{done}\n\nIt is in {self.target}. Start tierlist.py from there now? It uses the "
                                 "same save as this program, which then closes.", yes="Start it", no="Not now",
                                 parent=self.app.root, wrap_chars=60):
            standalone.start_source(self.target, python)
            self.app.on_close()                   # (asked for: one of them at a time, never two on one save)
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
