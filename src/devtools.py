"""Developer tools from the window (DT-1, DT-2): what the bubbles at a dialog's top right start while Settings >
Developer tools is on. Source & Updates has Log and Crash test (and Nightly, which is sources.py's own).

(The review of rude meanings and the tuner, DT-3..DT-7, went with the rudeness rules, OB-14: branch archive/censoring.)
"""
import os

import standalone
from constants import LOG_FILE


class DevTools:
    """The developer tools of one main window (App.devtools)."""

    def __init__(self, app):
        self.app = app

    # ---- Source & Updates: Log, Crash test -------------------------------------------------------------------------
    def open_log(self):
        """The "Log" bubble: tierlist.log next to the save, in the system's text viewer."""
        path = os.path.join(os.path.dirname(os.path.abspath(self.app.store.path)), LOG_FILE)
        try:
            if not os.path.exists(path):
                raise OSError(f"there is no {LOG_FILE} yet")
            standalone.open_folder(path)          # (xdg-open / open / startfile open a file with its own program)
        except OSError as exc:
            self.app.flash(f"Could not open the log: {exc}", kind="warn")
        return path

    def crash_test(self, dlg=None, delay=300):
        """The "Crash test" bubble (was --crash-test): close the dialog, then fail on purpose, to see the error
        dialog and the log entry; the program keeps running."""
        if dlg is not None:
            dlg.close()
        self.app.root.after(delay, lambda: 1 / 0)
