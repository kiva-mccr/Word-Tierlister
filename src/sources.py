"""File > Source & Updates... (T-6, T-7, U-1; U-4 made them one panel): everything about versions, source and
program in one dialog, whose actions fit the form you are running.

    SourceDialog(app)       Updates on top; below, from source: make a standalone program; in the program: unpack
                            its source

Updates (U-1): the dialog asks GitHub for the newest release in the background (standalone.latest_release) and says
what it found, and why when it could not ask (standalone.describe_fetch_error: a private repository answers "Not
Found"). With a newer version out, "Update" updates the form you are running: the program replaces itself with the
release's program for this computer (update_program); a source folder is brought up to date (update_source: git
pull in a git checkout, otherwise the release's source synced in, shown first, nothing built). Either way it starts
again on the same save. Such a source folder is never offered to be cleaned up behind (standalone.came_from_program).

From source (T-6), "Make the program" builds a one-file program for this computer from the source as it is now
(src/standalone.py, behind the progress window), puts it next to tierlist.py so it keeps using the same save (T-1),
then starts it and closes this window. When the program there was built from exactly this source, it offers to
start that instead.

In the built program (T-7), "Unpack" writes the source it carries into a folder (beside the program unless you pick
another), in the same layout as the repository (R-1). Into a folder that already has it, it syncs rather than copies:
changed files are updated, new ones added, and ones the program no longer has removed; only the program's own files
are ever touched, and a file you edited there is kept as name.bak first. What it will do is shown before it does
it. Then it opens the folder and offers to start tierlist.py from it (that needs a Python on this computer).

Nightly (U-9, for testing): the check also asks for main as it is now (standalone.latest_main) and, only when its
files differ from this source's, shows "Update to nightly": from source the folder is brought up to main
(update_source: git pull from main, or main's source synced in); in the program main's source goes into the source
folder beside it, which then builds the program in this one's place (update_nightly_program, --build-nightly).
The nightly section shows only with Settings > Developer tools ticked and its "Nightly" bubble lit (a switch at the
top right, lit to start with; it says so while main is the same); main is not even asked for otherwise. Beside it: "Log" (tierlist.log, App.devtools.open_log) and "Crash test"
(App.devtools.crash_test, was --crash-test).

Either way a tick box, "Update to the newest version first" (T-8), ticked to start with and usable once a newer
version is found: "Make the program" then downloads that version's source and builds from it, and "Unpack" downloads
it and shows what unpacking it would change before it does it. The first start of either form offers the other once
(T-9: App._offer_other_form), and a yes does it straight away (go=True), from the version you have.
"""
import os
import shutil
import sys
import tempfile
import time
import tkinter as tk
from tkinter import filedialog, ttk

import deps
import errors
import standalone
from errors import ask_buttons, ask_yes_no, show_error, show_message
from filepicker import browse, use_themed
from fonts import font
from problems import STOPPED_MESSAGE, SetupError
from saves import is_frozen, remember_save
from startup import ensure_packages, offer_system_install, run_with_progress
from theme import PALETTE
from background import Task
from dialogs import StyledDialog
from constants import REPO_PAGE, VERSION

TITLE = "Source & Updates"
HEADLINE = "Make a standalone program"
UPDATE = "Update"
NIGHTLY = "Update to nightly"
INTRO = ("Builds Word Tierlister into one program for this computer, with its source code inside it. It keeps using "
         "the same save, and Python is no longer needed to run it. It takes a minute or two; the first time, it "
         "asks to install the builder (PyInstaller, about 15 MB) and anything else the program needs.")
UNPACK_HEADLINE = "Unpack the source code"
UNPACK_INTRO = ("Writes the source code this program was built from into a folder: the program files, the tests and "
                "the notes, exactly as they were. Into a folder that already has them it brings them up to date, "
                "changing only the program's own files; anything you edited there is kept as a .bak copy first.")
CHECKING = "Checking GitHub for a newer version..."


class SourceDialog:
    """File > Source & Updates... (U-4: one panel for what were two menu items). At the top, Updates: GitHub is asked
    for the newest release and, with a newer one out, "Update" updates the form you are running (update_program /
    update_source; either way it starts again on the same save). Below it, the other form: from source, make the
    program; in the program, unpack its source; with the "Update to the newest version first" tick (T-8)."""

    def __init__(self, app, root_dir=None, source=None, frozen=None, check=None, go=False, platform=None,
                 nightly=None, target=None):
        """`root_dir`: the project (from source); `source`: the source the program carries, and `frozen`: which
        side to show; `check() -> release or None`: how to find the newest release (tests pass them; the program
        finds them itself). `go`: do it straight away, without showing the page (T-9's "yes": make the program,
        or unpack beside it, from the version you have); if unpacking fails, the page shows to try elsewhere.
        `platform`: which applications menu to offer (tests). `nightly() -> main or None`: how to find main as it
        is now (standalone.latest_main; tests pass their own). `target`: from source with `go`, the program to build
        in place of (a nightly update of the program: tierlist.py --build-nightly)."""
        self.app = app
        self.platform = platform or sys.platform
        self.menu = deps.menu_name(self.platform)      # (None: macOS, nothing to add to)
        self.frozen = is_frozen() if frozen is None else frozen
        self.root_dir = root_dir or standalone.ROOT
        self.check = check or standalone.latest_release
        self.nightly_check = nightly or standalone.latest_main
        self.target = None
        self.build_target = target
        self.release = None                       # the newest release, once the check has found one
        self.nightly = None                       # main as it is now, once found, when it differs from this source
        self.nightly_files = []                   # the files that differ
        self.checked = False
        self.fetched = None                       # (unpacking) the newer version's source, once downloaded
        self.download_dir = None                  # the temporary folder it was downloaded into
        form = ("the program, built for this computer" if self.frozen else
                f"the source code (tierlist.py, in {self.root_dir})")
        self.dlg = StyledDialog(app.root, TITLE, f"Word Tierlister {VERSION}", f"You are running {form}.",
                                animator=app.anim, wrap_chars=64)
        self.dlg.win.bind("<Destroy>", lambda e: e.widget is self.dlg.win and self._drop_fetched(), add="+")
        self.nightly_always = (tk.BooleanVar(value=app.store.get_meta("nightly_always", "1") == "1")
                               if getattr(app, "dev_tools", False) else None)
        self.main_now = None                      # main as it is now, once found (the Nightly bubble shows it the same)
        if self.nightly_always is not None:       # (Settings > Developer tools: the dialog's bubbles)
            self.bubbles = self.dlg.dev_bubbles((("Nightly", self._toggle_nightly, self.nightly_always),
                                                 ("Log", app.devtools.open_log),
                                                 ("Crash test", lambda: app.devtools.crash_test(self.dlg))))
        self._updates_section()
        if self.menu and self.frozen and not deps.in_menu(self.platform):   # (asked for: only in the program, and
            self._menu_section()                                            # only until it is in the menu)
        self.source = (source or standalone.bundled_source()) if self.frozen else None
        self.here = self.source if self.frozen else self.root_dir     # (what main is compared with)
        if self.frozen:
            self._unpack_page()
        else:
            self._make_page()
        if go and "Unpack" in self.dlg.buttons:
            self.unpack()
            if not self.dlg.alive():
                return
        elif go and not self.frozen:
            self.make()
            return
        self._start_check()
        self.dlg.show()

    def _heading(self, text, top=18):
        ttk.Label(self.dlg.body, text=text, font=font("head")).pack(anchor="w", pady=(top, 4))

    # ---- Updates (U-1, U-4): the form you are running -----------------------------------------------------------
    def _updates_section(self):
        self._heading("Updates", top=0)
        self.line = self.dlg.text(CHECKING)
        self.how = self.dlg.text("", muted=True, pady=(4, 0))
        self.update_buttons = tk.Frame(self.dlg.body, bg=PALETTE["bg"])
        self.update_buttons.pack(anchor="w", pady=(8, 0))
        self.nightly_box = tk.Frame(self.dlg.body, bg=PALETTE["bg"])     # (only while main differs: _show_nightly)
        self.nightly_box.pack(anchor="w", fill="x")

    def _start_check(self):
        """Ask GitHub on a worker thread (it never touches the window): the newest release, then main as it is now
        and which files differ from this source (nightly). The answer is collected every 100 ms."""
        def ask():
            release = self.check()
            main = self.nightly_check() if self.here and self.nightly_always is not None else None
            return release, main, standalone.nightly_changes(main, self.here) if main else []

        def collect(answer):
            if not self.dlg.alive():
                return
            self.release, main, files = answer
            self.checked = True
            self.main_now = main
            self.nightly, self.nightly_files = (main, files) if files else (None, [])
            self._show_check()
        def failed(exc):                  # (said like GitHub not answering, never "Checking..." for good)
            standalone.last_error = str(exc) or type(exc).__name__
            collect((None, None, []))
        Task(self.dlg.win, ask, done=collect, failed=failed)

    def again(self):
        """"Try again": ask GitHub once more."""
        self.checked, self.release, self.nightly, self.nightly_files = False, None, None, []
        self.main_now = None
        self._clear_update_buttons()
        self.line.config(text=CHECKING)
        self.how.config(text="")
        self._show_update()
        self._start_check()

    def _clear_update_buttons(self):
        for w in self.update_buttons.winfo_children() + self.nightly_box.winfo_children():
            for name, b in list(self.dlg.buttons.items()):
                if b is w:
                    del self.dlg.buttons[name]
            w.destroy()
        if self.main in self.dlg.buttons:
            self.dlg.make_default(self.dlg.buttons[self.main])

    def _show_check(self):
        """Say what GitHub answered, with the buttons that fit it."""
        r, dlg, row = self.release, self.dlg, self.update_buttons
        self._clear_update_buttons()
        how = ""
        if not r:
            text = "Could not check for a newer version."
            how = standalone.last_error or "GitHub could not be reached."
            dlg.button("Try again", self.again, row=row)
        elif not standalone.newer(r):
            text = f"Version {VERSION} is the newest there is."
        else:
            text = f"Version {r['version']} is out (you have {VERSION})."
            asset = standalone.program_download(r) if self.frozen else None
            if self.frozen and not asset:
                how = "It has no program for this computer: the release page has what there is."
                dlg.button("Open the release page", lambda: errors.open_link(r.get("page") or REPO_PAGE), row=row)
            else:
                if r.get("page"):
                    dlg.button("What's new", lambda: errors.open_link(r["page"]), row=row)
                if self.frozen:
                    size = f" (about {asset['size'] / 1e6:.0f} MB)" if asset.get("size") else ""
                    how = (f'"{UPDATE}" downloads the new program{size}, puts it in place of this one and starts '
                           "it, with the same save.")
                    dlg.button(UPDATE, lambda: update_program(self.app, r, dlg), default=True, row=row)
                else:
                    how = (f'"{UPDATE}" brings this folder up to date with git pull, then starts again with the same '
                           "save." if standalone.git_checkout(self.root_dir) else
                           f'"{UPDATE}" downloads the new source and shows what it changes in this folder before it '
                           "does it (only the program's own files; your save stays), then starts again with the "
                           "same save. Nothing is built.")
                    dlg.button(UPDATE, self.update_source, default=True, row=row)
        self.line.config(text=text)
        self.how.config(text=how)
        if how:                                   # (an empty line left a gap above the nightly build)
            self.how.pack(anchor="w", pady=(4, 0), after=self.line)
        else:
            self.how.pack_forget()
        self._show_nightly()
        self._show_update()

    # ---- nightly (asked for, for testing): main as it is now, shown only when it differs ---------------------------
    def _toggle_nightly(self):
        """The "Nightly" bubble (a switch, lit to start with): the nightly section shown even while main is the same
        as this source. Saved."""
        self.app.store.set_meta("nightly_always", int(self.nightly_always.get()))
        if self.checked:
            for w in self.nightly_box.winfo_children():
                for name, b in list(self.dlg.buttons.items()):
                    if b is w or str(b).startswith(str(w) + "."):
                        del self.dlg.buttons[name]
                w.destroy()
            self._show_nightly()
            self.dlg.refit()

    def _nightly_on(self):
        """The nightly section shows only while Settings > Developer tools is on and the Nightly bubble is lit (asked
        for: it showed to everyone whenever main was ahead)."""
        return self.nightly_always is not None and bool(self.nightly_always.get())

    def _show_nightly(self):
        """Only while _nightly_on: when main on GitHub differs from this source (or the source this program was built
        from), a line saying so and "Update to nightly"; otherwise a line saying this is main as it is now, or that
        main could not be checked. Nothing at all while Developer tools is off or the Nightly bubble is not lit."""
        n, box = self.nightly, self.nightly_box
        if not self._nightly_on():                # (only for developers: never offered with the bubble off, reported)
            return
        if not n:
            if self.here:
                m = self.main_now
                self.dlg.text(f"Nightly build: you have main as it is now (commit {m['short']}, {ago(m['when'])})."
                              if m else "Nightly build: main on GitHub could not be checked.", parent=box,
                              pady=(10, 0))
            return
        files = len(self.nightly_files)
        msg = f': "{n["message"]}"' if n.get("message") else ""
        what = ("it downloads main's source into the source folder beside this program and builds a new program "
                "from it there, in place of this one (needs Python; a few minutes)" if self.frozen else
                "it updates this folder with git pull from main" if standalone.git_checkout(self.root_dir) else
                "it downloads main's source and shows what it changes in this folder first")
        self.dlg.text(f"Nightly build: main has {files:,} changed file{'s' if files != 1 else ''} "
                      f"(commit {n['short']}, {ago(n['when'])}{msg}).", parent=box, pady=(10, 0))
        self.dlg.text(f"For testing: it may be broken. {what[0].upper() + what[1:]}; your save is kept.",
                      muted=True, parent=box, pady=(2, 0))
        row = tk.Frame(box, bg=PALETTE["bg"])
        row.pack(anchor="w", pady=(8, 0))
        self.dlg.button("What's changed", lambda: errors.open_link(n["page"]), row=row)
        self.dlg.button(NIGHTLY, self.update_nightly, row=row)

    def update_nightly(self, fetch=None):
        """"Update to nightly": from source, this folder brought up to main (update_source); in the program, its
        source folder, which then builds the program in place of this one (update_nightly_program)."""
        if self.frozen:
            return update_nightly_program(self.app, self.nightly, self.dlg, fetch=fetch)
        return update_source(self.app, self.nightly, self.root_dir, self.dlg, fetch)

    def update_source(self, fetch=None):
        """"Update" from source: update_source below, for this folder."""
        return update_source(self.app, self.release, self.root_dir, self.dlg, fetch)

    # ---- the applications menu / Start menu (ST-5, ST-10; in the panel since U-5) --------------------------------
    def _menu_section(self):
        quiet = "a console window" if self.platform.startswith("win") else "a terminal"
        self._heading(self.menu[0].upper() + self.menu[1:])
        self.menu_line = self.dlg.text(f"Puts Word Tierlister in your {self.menu}, so it opens like any other "
                                       f"program, without {quiet}.")
        self.menu_row = tk.Frame(self.dlg.body, bg=PALETTE["bg"])
        self.menu_row.pack(anchor="w", pady=(8, 0))
        self.menu_button = f"Add to {self.menu}"
        self.dlg.button(self.menu_button, self.add_to_menu, row=self.menu_row)

    def add_to_menu(self):
        """"Add to applications menu" / "Add to Start menu" (in the program only): this program (App.add_launcher).
        Once added the button goes, and the section is not shown again."""
        path = self.app.add_launcher(self.platform)
        if path:
            self.dlg.buttons.pop(self.menu_button).destroy()
            self.menu_row.pack_forget()
            self.menu_line.config(text=f"Word Tierlister is in your {self.menu} now.")
            self.dlg.refit()
        return path

    def _menu_for(self, program):
        """Making the program: point the menu at the new program before it starts, when it is in the menu already
        (a launcher left on the source would break once the source is cleaned up behind) or the tick asks for it."""
        if self.menu and (self.was_in_menu or self.menu_var.get()):
            self.app.add_launcher(self.platform, program=program, quiet=True)

    # ---- "Update to the newest version first" (T-8) -------------------------------------------------------------
    def _update_row(self):
        """The tick box and the line under it saying what ticking it does (once the check has answered)."""
        dlg = self.dlg
        self.update_var = tk.BooleanVar(value=True)
        self.tick = ttk.Checkbutton(dlg.body, text="Update to the newest version first", variable=self.update_var,
                                    command=self._show_update, takefocus=1)
        self.tick.pack(anchor="w", pady=(12, 0))
        self.update_line = dlg.text("", muted=True, padx=(24, 0))
        self._show_update()

    def wants_update(self):
        """True if ticked and the newest release is newer than this version (and not downloaded yet)."""
        return self.update_var.get() and standalone.newer(self.release) and not self.fetched

    def _show_update(self):
        if not hasattr(self, "update_var"):
            return
        r = self.release
        newer = self.checked and standalone.newer(r)
        self.tick.state(["!disabled"] if newer and not self.fetched else ["disabled"])
        if not self.checked:
            text = "Waiting for GitHub's answer (above)."
        elif self.fetched:
            text = f"Version {r['version']} downloaded: above is what unpacking it changes."
        elif not newer:
            text = f"Nothing newer to update to: version {VERSION}, the one you have, is used."
        elif self.update_var.get():
            what = "builds the program from it" if not self.frozen else "downloads it and shows what it changes"
            text = f'Version {r["version"]}: "{self.main}" {what}.'
        else:
            text = f"Unticked: version {VERSION}, the one you have, is used."
        self.update_line.config(text=text)
        self.dlg.refit()

    # ---- from source: make the program (T-6) --------------------------------------------------------------------
    def _make_page(self):
        dlg = self.dlg
        self._heading(HEADLINE)
        dlg.text(INTRO, muted=True)
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
        self.where = dlg.text(f"It goes next to tierlist.py:\n{path}", muted=True, pady=(8, 0))
        if state:
            self.state = dlg.text(state, pady=(10, 0))
        self.main = "Make the program"
        dlg.button("Close", dlg.close)
        if self.fresh:
            self.main = "Start it"
            dlg.button("Build again", self.make)
            dlg.button("Start it", lambda: (self._menu_for(path), self.start(path)), default=True)
        else:
            dlg.button("Make the program", self.make, default=True)
        self._update_row()
        self.was_in_menu = bool(self.menu) and deps.in_menu(self.platform)    # (then it moves to the program anyway)
        self.menu_var = tk.BooleanVar(value=True)  # (asked for: ticked to start with)
        if self.menu and not self.was_in_menu:    # (asked for: offered only until it is in the menu)
            ttk.Checkbutton(dlg.body, text=f"Add the program to the {self.menu}", variable=self.menu_var,
                            takefocus=1).pack(anchor="w", pady=(6, 0))
    def make(self):
        """Build behind the progress window, then start the new program and close this one."""
        app = self.app
        self.dlg.close()
        if not self.packages_ready():
            return None
        lines = []
        target = self.build_target                # (a nightly update of the program: in its place, nothing asked)
        place = None if target else standalone.cleanup_place(self.root_dir)    # (where the source is: T-12, T-14)
        self.behind = None
        if place:
            self.behind = self.ask_behind(place)
            if self.behind is None:
                return None                       # (closed the question: nothing made)
            if self.behind == "keep":
                place = None                      # (the program goes next to tierlist.py, as always)
        release = self.release if self.wants_update() else None

        def work(log):
            def keep(text):
                lines.append(str(text))
                log(text)
            kw = {"place": place} if place else {"target": target} if target else {}
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
        if target:                                # (the program it replaced: same save, nothing else changes)
            app.store.set_meta(UPDATED_FROM, standalone.NIGHTLY + (app.store.get_meta(PENDING) or "main"))
            standalone.start(path, args=["--db", app.store.path])
            app.on_close()
            return path
        self._menu_for(path)
        if place:
            self.start_cleaned(path, place, zip_it=self.behind == "zip")
        else:
            self.start(path)
        return path

    def ask_behind(self, place):
        """"Clean up behind?" (asked for, every time the program is made): "keep", "zip" or "remove", or None when
        the question is closed. Keeping is the default (Enter)."""
        git = os.path.isdir(os.path.join(self.root_dir, ".git"))
        knows = standalone.knows_changes(self.root_dir)       # (F-47: your edits told from the source as it came)
        here = os.path.realpath(place) == os.path.realpath(self.root_dir)
        where = ("The program goes in this folder, where the source is, and the source's own files can be removed "
                 "from it (or packed into a zip here first). Your save stays here, beside the program."
                 if here else f"The program can replace the one beside this source folder, in {place}, and the "
                 "folder be removed (or packed into a zip there first). Your save moves next to the program first.")
        return ask_buttons(
            HEADLINE, "Clean up behind?",
            where + " The program carries its source inside it, and can unpack it again any time. Only the source's "
            + ("own files are removed, and only as they came: anything you added or changed stays (and so does the "
               "folder then)." if knows else
               "own files are removed, even ones you edited (Zip it keeps a copy); anything you added stays.")
            + " Its Python environment (.venv) and caches go too."
            + (" This folder is a git checkout: its history (.git) stays"
               + (", and so do changes not yet committed." if knows else ".") if git else "")
            + "\n\nKeep the source: the program goes next to tierlist.py, and nothing else changes.",
            (("Keep the source", "keep"), ("Zip it", "zip"), ("Remove it", "remove")), parent=self.app.root,
            wrap_chars=62)

    def start_cleaned(self, path, place, zip_it=False):
        """Clean up behind (T-12, T-14): close this window and its save, move the save next to the new program if it
        is inside the source folder and the program went elsewhere (it is the one used from now on), pack the source
        into a zip beside the program if asked (`zip_it`), then start the program, which removes the source's files
        as it starts (only those written down for it: mark_for_removal; the folder goes only if nothing else is left
        in it). The save is marked as having given out its source, so the program does not unpack it again."""
        store = self.app.store
        store.set_meta("offered_source", "1")
        save = store.path
        self.dlg.close()
        self.app.on_close()
        if os.path.realpath(save).startswith(os.path.realpath(self.root_dir) + os.sep) and \
                os.path.realpath(place) != os.path.realpath(self.root_dir):
            save = standalone.move_save(save, place)
        remember_save(save)
        if zip_it:
            standalone.zip_source(self.root_dir, place)
        standalone.mark_for_removal(self.root_dir)
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
        dlg = self.dlg
        self._heading(UNPACK_HEADLINE)
        dlg.text(UNPACK_INTRO, muted=True)
        self.main = "Unpack"
        if not self.source:
            dlg.text("This program was built without its source code inside it, so there is nothing to unpack.",
                     pady=(8, 0))
            dlg.button("Close", dlg.close, default=True)
            return
        self.target = standalone.default_source_folder()
        self.where = dlg.text("", muted=True, pady=(8, 0))
        self.state = dlg.text("", pady=(10, 0))
        dlg.button("Change folder...", self.change_folder, side="left")
        dlg.button("Close", dlg.close)
        dlg.button("Unpack", self.unpack, default=True)
        self._update_row()
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
        self.download_dir = folder                # (removed once unpacked or the dialog closes: _drop_fetched)
        try:
            folder = run_with_progress(self.app.root, lambda log: standalone.fetch_source(release, folder, log),
                              title="Downloading the newest version", delay_ms=0, initial_stage="Connecting...",
                              intro=f"Version {release['version']}, from GitHub.")
        except SystemExit as exc:
            self._drop_fetched()
            if str(exc) != STOPPED_MESSAGE:
                raise
            return False
        except OSError as exc:
            self._drop_fetched()
            show_error("Unpack the source code", f"The newest version could not be downloaded:\n{exc}\n\nUntick "
                       "the update to unpack the version you have.", parent=self.dlg.win, headline="Not downloaded")
            return False
        self.fetched = self.source = folder
        self._show_plan()
        self._show_update()
        return True

    def _drop_fetched(self):
        """Remove the newer version's downloaded source from the temporary folder (F-47: it was left there for
        good), once it is unpacked or the dialog closes."""
        if self.download_dir:
            shutil.rmtree(self.download_dir, ignore_errors=True)
            self.download_dir = None

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
        self._drop_fetched()
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


# ---- U-1: updating the form you are running ------------------------------------------------------------------------------------
PENDING = "nightly_pending"           # meta: the nightly commit the program's source is building (the toast after)
UPDATED_FROM = "updated_from"        # meta: the version an update was made from (the new one says so, then forgets)


def ago(when, now=None):
    """"3 hours ago" for a time (seconds since 1970)."""
    s = max(0, (time.time() if now is None else now) - when)
    for size, unit in ((86400, "day"), (3600, "hour"), (60, "minute")):
        if s >= size:
            n = int(s // size)
            return f"{n} {unit}{'s' if n != 1 else ''} ago"
    return "just now"


def _named(release):
    name = standalone.named(release)
    return name[0].upper() + name[1:]


def _download(app, title, release, work):
    """Run `work(log)` (a download) behind the progress window: its result, or None if it was stopped."""
    try:
        return run_with_progress(app.root, work, title=title, delay_ms=0, initial_stage="Connecting...",
                                 intro=f"{_named(release)}, from GitHub.")
    except SystemExit as exc:
        if str(exc) != STOPPED_MESSAGE:
            raise
        return None


def update_source(app, release, root_dir, dlg, fetch=None, git=None):
    """Bring the source in `root_dir` up to `release`, then start again from it with the same save (this window
    closes). A git checkout (with git installed) is updated with git pull, which never touches your own changes;
    any other folder downloads the release's source and syncs it in: what it changes is shown first, only the
    program's own files change (an edited one is kept as .bak first), and the folder is not marked as unpacked from
    the program (so it is never offered to be cleaned up behind). `release` may be main as it is now (nightly:
    standalone.latest_main): git pulls main then, and only on main. `dlg`: the dialog asking; `fetch` / `git`:
    tests."""
    nightly = release.get("nightly")
    if standalone.git_checkout(root_dir) if git is None else git:
        on = standalone.git_branch(root_dir) if nightly else None
        if nightly and on != standalone.MAIN:
            show_error(TITLE, f"This git checkout is on {'branch ' + on if on and on != 'HEAD' else 'no branch'}, "
                       f"not {standalone.MAIN}: switch it to {standalone.MAIN} (git switch {standalone.MAIN}) to take "
                       "the nightly build. Nothing was changed.", parent=dlg.win, headline="Not updated")
            return None
        if not ask_yes_no(TITLE, f"Update the source to {standalone.named(release)}?",
                          f"This folder is a git checkout, so it is updated with git pull"
                          f"{' from ' + standalone.MAIN if nightly else ''}, which never touches "
                          f"your own changes.\n\nIn {root_dir}. Word Tierlister then starts again from the new "
                          "source, with the same save.", yes="Update", no="Cancel", parent=dlg.win, wrap_chars=60):
            return None
        ok, said = standalone.git_pull(root_dir, branch=standalone.MAIN) if nightly else standalone.git_pull(root_dir)
        if not ok:
            show_error(TITLE, "git pull did not update this folder. What git said is below; nothing "
                       "was changed.", details=said, parent=dlg.win, headline="Not updated")
            return None
        plan = said
    else:
        get = fetch or standalone.fetch_source
        folder = tempfile.mkdtemp(prefix="wtl-release-")
        try:                                  # (F-47: the download is removed afterwards, whatever happens)
            try:
                got = _download(app, "Downloading the newest version", release, lambda log: get(release, folder, log))
            except OSError as exc:
                show_error(TITLE, f"{_named(release)} could not be downloaded:\n{exc}", parent=dlg.win,
                           headline="Not updated")
                return None
            if got is None:
                return None
            plan = standalone.plan_unpack(got, root_dir)
            if not ask_yes_no(TITLE, f"Update the source to {standalone.named(release)}?",
                              f"{standalone.summary(plan)}\n\nIn {root_dir}. Only the program's own files change; "
                              "your save and anything else there stay as they are. Word Tierlister then starts again "
                              "from the new source, with the same save.", yes="Update", no="Cancel", parent=dlg.win,
                              wrap_chars=60):
                return None
            try:
                standalone.unpack(got, root_dir, plan, from_program=False)
            except OSError as exc:
                show_error(TITLE, f"The source could not be updated in {root_dir}:\n{exc}", parent=dlg.win,
                           headline="Not updated")
                return None
        finally:
            shutil.rmtree(folder, ignore_errors=True)
    dlg.close()
    app.store.set_meta(UPDATED_FROM, standalone.NIGHTLY + release["short"] if nightly else VERSION)
    standalone.start_source(root_dir, sys.executable, args=["--db", app.store.path])
    app.on_close()                            # (one at a time on a save: the new source takes over)
    return plan


def update_program(app, release, dlg, program=None, fetch=None):
    """Download this computer's program from `release` beside the running one, put it in its place (the old one is
    kept as .old until the new one removes it as it starts) and start it with the same save; this window closes.
    `program`: the running program (tests); `fetch(release, folder, log) -> path`: tests."""
    program = program or standalone.running_program()
    try:
        folder = standalone.update_folder(program)
    except OSError as exc:
        show_error(TITLE, f"This program's folder cannot be written to, so the update cannot replace "
                   f"it:\n{exc}\n\nThe release page has the new program to download by hand.", parent=dlg.win,
                   headline="Not updated")
        return None
    try:
        new = _download(app, "Downloading the newest version", release,
                        lambda log: (fetch or standalone.fetch_program)(release, folder, log))
    except OSError as exc:
        new = None
        show_error(TITLE, f"The new program could not be downloaded:\n{exc}", parent=dlg.win,
                   headline="Not updated")
    try:
        if new is not None:
            standalone.replace_program(new, program)
    except OSError as exc:
        new = None
        show_error(TITLE, f"The new program could not be put in place of this one:\n{exc}\n\nThis "
                   "one is unchanged.", parent=dlg.win, headline="Not updated")
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if new is None:
        return None
    dlg.close()
    app.store.set_meta(UPDATED_FROM, VERSION)
    standalone.start(program, args=["--db", app.store.path])
    app.on_close()
    return program


def update_nightly_program(app, nightly, dlg, program=None, fetch=None, folder=None):
    """In the program, "Update to nightly" (asked for: from main's source, built here): main's source goes into the
    source folder beside the program (standalone.existing_source, or the one it unpacks into; synced as unpacking
    is, shown first: only the program's own files, an edited one kept as .bak; a git checkout pulls main), which then
    starts with --build-nightly: it builds the program from that source (asking for the builder, PyInstaller, if
    it is missing) in place of this one, and starts it with the same save. This window closes first. Needs a
    Python on this computer (offered if there is none). `program`, `fetch`, `folder`: tests."""
    program = program or standalone.running_program()
    folder = folder or standalone.existing_source() or standalone.default_source_folder()
    python = standalone.python_for_source()
    if not python and offer_system_install(app.root, "python", "Building the nightly program needs Python on this "
                                           "computer, which it does not have yet."):
        python = standalone.python_for_source()
    if not python:
        show_message(TITLE, "Not updated", "Building the nightly program needs Python 3 on this computer "
                     "(python.org). Nothing was changed.", parent=dlg.win)
        return None
    then = (f"Then Word Tierlister starts from that source and builds a new program from it (a few minutes; the "
            f"first time it may ask to install the builder, PyInstaller), which replaces this one in "
            f"{os.path.dirname(program)} and starts with the same save.")
    if standalone.git_checkout(folder):
        on = standalone.git_branch(folder)
        if on != standalone.MAIN:
            show_error(TITLE, f"The source beside this program ({folder}) is a git checkout on "
                       f"{'branch ' + on if on and on != 'HEAD' else 'no branch'}, not {standalone.MAIN}: switch it "
                       f"to {standalone.MAIN} to take the nightly build. Nothing was changed.", parent=dlg.win,
                       headline="Not updated")
            return None
        if not ask_yes_no(TITLE, f"Update to {standalone.named(nightly)}?",
                          f"It is {standalone.MAIN} as it is now on GitHub, for testing: it may be broken. The source "
                          f"in {folder} is a git checkout, so it is updated with git pull, which never touches your "
                          f"own changes.\n\n{then}", yes="Update", no="Cancel", parent=dlg.win, wrap_chars=60):
            return None
        ok, said = standalone.git_pull(folder, branch=standalone.MAIN)
        if not ok:
            show_error(TITLE, "git pull did not update the source. What git said is below; nothing was changed.",
                       details=said, parent=dlg.win, headline="Not updated")
            return None
    else:
        down = tempfile.mkdtemp(prefix="wtl-nightly-")
        try:
            try:
                got = _download(app, "Downloading the nightly build", nightly,
                                lambda log: (fetch or standalone.fetch_source)(nightly, down, log))
            except OSError as exc:
                show_error(TITLE, f"{_named(nightly)} could not be downloaded:\n{exc}", parent=dlg.win,
                           headline="Not updated")
                return None
            if got is None:
                return None
            plan = standalone.plan_unpack(got, folder)
            if not ask_yes_no(TITLE, f"Update to {standalone.named(nightly)}?",
                              f"It is {standalone.MAIN} as it is now on GitHub, for testing: it may be broken. "
                              f"Its source goes into {folder}: {standalone.summary(plan)[0].lower()}"
                              f"{standalone.summary(plan)[1:]} Only the program's own files change.\n\n{then}",
                              yes="Update", no="Cancel", parent=dlg.win, wrap_chars=60):
                return None
            try:
                standalone.unpack(got, folder, plan, from_program=False)
            except OSError as exc:
                show_error(TITLE, f"The source could not be written to {folder}:\n{exc}", parent=dlg.win,
                           headline="Not updated")
                return None
        finally:
            shutil.rmtree(down, ignore_errors=True)
    dlg.close()
    app.store.set_meta("offered_program", "1")      # (that source is not asked to make a program: it is making one)
    app.store.set_meta(PENDING, nightly["short"])     # (the new program then says it is the nightly build)
    standalone.start_source(folder, python, args=["--db", app.store.path, standalone.BUILD_NIGHTLY, program])
    app.on_close()                                  # (one at a time on a save: the source takes over)
    return folder
