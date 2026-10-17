"""Friendly error dialogs and the program-wide safety net (ST-2).

    show_error(title, message, details=None, parent=None)
        a small styled dialog: plain-language message, an optional "Show details" area and a
        "Copy details" button. With no window system it prints to stderr instead.
    install_handlers(root, log_path, save_path)
        Tk callbacks, the main thread and worker threads that raise an unexpected error write the
        traceback to the error log and (for the window's own errors) show one dialog saying the
        progress is safe. The program keeps running; repeats of one error do not pile up dialogs.
    run_guarded(fn, log_path, save_path)
        runs the whole program: a SetupError or sys.exit("message") becomes a dialog, a crash
        becomes a dialog plus a log entry, and a deliberate stop (STOPPED_MESSAGE) is silent.

The plain-language text itself comes from problems.py (no tkinter there).
"""
import sys
import threading
import time
import tkinter as tk
import traceback
from tkinter import ttk

from fonts import font, init_fonts
from problems import STOPPED_MESSAGE, SetupError, append_log, describe
from theme import PALETTE
from ui_style import apply_ttk_style

APP_TITLE = "Word Tier List"
REPEAT_SECONDS = 5      # the same error again within this time only goes to the log
_state = {"open": False, "last_key": None, "last_time": 0.0}


def _stderr(text):
    if sys.stderr is not None:
        print(text, file=sys.stderr)


def show_error(title, message, details=None, parent=None, headline=None):
    """Show a modal error dialog and wait for it to close (stderr if no window can be made).

    `headline` is the short bold line; `message` the explanation; `details` (optional) the technical
    text kept behind "Show details" and copied by "Copy details".
    """
    own_root = None
    try:
        if parent is None:
            own_root = parent = tk.Tk()
            own_root.withdraw()
            init_fonts(own_root)
            apply_ttk_style(own_root)
        _dialog(parent, title, headline or title, message, details)
    except Exception:
        _stderr(f"{title}: {headline or ''} {message}\n{details or ''}")
    finally:
        if own_root is not None:
            try:
                own_root.destroy()
            except tk.TclError:
                pass


def ask_yes_no(title, headline, message, yes="OK", no="Cancel", parent=None):
    """A small styled question dialog. Returns True for the `yes` button, False for `no`, Escape or close.

    Falls back to False (the safe answer) when no window can be shown."""
    own_root = None
    answer = {"yes": False}
    try:
        if parent is None:
            own_root = parent = tk.Tk()
            own_root.withdraw()
            init_fonts(own_root)
            apply_ttk_style(own_root)
        _dialog(parent, title, headline, message, None, buttons=((yes, True), (no, False)), answer=answer)
    except Exception:
        _stderr(f"{title}: {headline} {message}")
    finally:
        if own_root is not None:
            try:
                own_root.destroy()
            except tk.TclError:
                pass
    return answer["yes"]


def ask_choices(title, headline, message, choices, yes="OK", no="Cancel", parent=None):
    """A styled question with one tick box per choice (ST-4: each package is its own choice).

    `choices` are (key, label, detail, ticked[, required]) tuples; the detail is a muted line under the
    label, and a required choice gets a red asterisk after its label.
    Returns the set of ticked keys for the `yes` button, or None for `no`, Escape or closing (also when
    no window can be shown)."""
    answer = {"yes": False}
    try:
        _dialog(parent, title, headline, message, None, buttons=((yes, True), (no, False)), answer=answer,
                choices=choices)
    except Exception:
        _stderr(f"{title}: {headline} {message}")
        return None
    return answer.get("chosen") if answer["yes"] else None


def show_exception(title, exc, parent, context):
    """Dialog for an error the program caught itself (a failed export, say): what we were doing, why, what to try."""
    headline, advice = describe(exc)
    show_error(title, f"{context}\n\n{advice}", details=f"{type(exc).__name__}: {exc}", parent=parent,
               headline=headline)


def _dialog(parent, title, headline, message, details, buttons=None, answer=None, choices=None):
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=PALETTE["bg"])
    dlg.resizable(False, False)
    try:
        if parent.winfo_viewable():
            dlg.transient(parent)
    except tk.TclError:
        pass
    wrap = max(380, font("body").measure("n") * 44)
    box = ttk.Frame(dlg, padding=(26, 22))
    box.pack(fill="both", expand=True)
    ttk.Label(box, text=headline, font=font("head"), wraplength=wrap, justify="left").pack(anchor="w")
    ttk.Label(box, text=message, wraplength=wrap, justify="left",
              foreground=PALETTE["muted"]).pack(anchor="w", pady=(10, 0))
    ticks = []
    if choices:                      # one tick box per choice, each with a muted line saying what it is for
        cbox = ttk.Frame(box)
        cbox.pack(fill="x", pady=(12, 0))
        for key, label, detail, ticked, *rest in choices:
            var = tk.BooleanVar(value=ticked)
            line = ttk.Frame(cbox)
            line.pack(anchor="w", pady=(6, 0))
            ttk.Checkbutton(line, text=label, variable=var, takefocus=1).pack(side="left")
            if rest and rest[0]:             # required: the classic red asterisk
                ttk.Label(line, text="*", foreground=PALETTE["required"], font=font("head")).pack(side="left")
            if detail:
                ttk.Label(cbox, text=detail, wraplength=wrap - 30, justify="left",
                          foreground=PALETTE["muted"]).pack(anchor="w", padx=(26, 0))
            ticks.append((key, var))
    txt = tk.Text(box, height=9, width=1, wrap="word", font=font("body"), relief="flat",
                  bg=PALETTE["surface"], fg=PALETTE["text"], padx=8, pady=6)
    if details:
        txt.insert("1.0", details)
    txt.config(state="disabled")
    shown = tk.BooleanVar(value=False)
    row = ttk.Frame(box)
    row.pack(fill="x", pady=(16, 0))

    def toggle():
        shown.set(not shown.get())
        if shown.get():
            txt.pack(fill="x", pady=(12, 0), before=row)
            toggle_btn.config(text="Hide details")
        else:
            txt.pack_forget()
            toggle_btn.config(text="Show details")
        dlg.update_idletasks()
        dlg.geometry("")

    def copy():
        dlg.clipboard_clear()
        dlg.clipboard_append(f"{headline}\n{message}\n\n{details or ''}")
        copy_btn.config(text="Copied")

    if buttons:                      # a question: (label, value) pairs, the first is the default
        def choose(value):
            answer["yes"] = value
            answer["chosen"] = {k for k, v in ticks if v.get()}
            dlg.destroy()
        for i, (label, value) in enumerate(buttons):     # the first is what Enter presses: drawn as the default
            ttk.Button(row, text=label, command=lambda v=value: choose(v), default="active" if i == 0 else "normal",
                       style="Default.TButton" if i == 0 else "TButton").pack(side="right", padx=(8, 0) if i else 0)
        dlg.bind("<Return>", lambda e: choose(buttons[0][1]))
        dlg.bind("<Escape>", lambda e: choose(False))
        dlg.protocol("WM_DELETE_WINDOW", lambda: choose(False))
    else:
        ttk.Button(row, text="OK", command=dlg.destroy).pack(side="right")
    if details:
        copy_btn = ttk.Button(row, text="Copy details", command=copy)
        copy_btn.pack(side="right", padx=(0, 8))
        toggle_btn = ttk.Button(row, text="Show details", command=toggle)
        toggle_btn.pack(side="left")
    if not buttons:
        dlg.bind("<Return>", lambda e: dlg.destroy())
        dlg.bind("<Escape>", lambda e: dlg.destroy())
    dlg.update_idletasks()
    # centre over the parent (or the screen when the parent is hidden)
    w, h = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
    if parent.winfo_viewable():
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 3
    else:
        x, y = (dlg.winfo_screenwidth() - w) // 2, (dlg.winfo_screenheight() - h) // 3
    dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    dlg.grab_set()
    dlg.focus_force()
    dlg.wait_window()


def _report(exc, tb_text, log_path, save_path, parent):
    """Log an unexpected error and (when `parent` is a window) tell the user, once."""
    append_log(log_path, f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n{tb_text}")
    _stderr(tb_text)
    if parent is None:
        return
    key = (type(exc).__name__, str(exc)[:200])
    now = time.time()
    if _state["open"] or (key == _state["last_key"] and now - _state["last_time"] < REPEAT_SECONDS):
        return
    _state.update(open=True, last_key=key, last_time=now)
    try:
        headline, advice = describe(exc)
        saved = f"Your progress is saved{' in ' + save_path if save_path else ''}: every action is written as you go."
        show_error(APP_TITLE, f"{advice}\n\n{saved}", details=f"{tb_text}\nLog file: {log_path}",
                   parent=parent, headline=headline)
    finally:
        _state["open"] = False


def install_handlers(root, log_path, save_path=None):
    """Route every unexpected error to the log (and, for the window's own errors, a friendly dialog)."""
    def fmt(et, ev, tb):
        return "".join(traceback.format_exception(et, ev, tb))

    def on_tk(et, ev, tb):                 # an error inside a button, key or timer callback
        _report(ev, fmt(et, ev, tb), log_path, save_path, root)

    def on_main(et, ev, tb):               # reached only when nothing else caught it
        if not issubclass(et, (KeyboardInterrupt, SystemExit)):
            _report(ev, fmt(et, ev, tb), log_path, save_path, None)

    def on_thread(args):                   # worker threads must not touch Tk: log only
        if not issubclass(args.exc_type, SystemExit):
            _report(args.exc_value, fmt(args.exc_type, args.exc_value, args.exc_traceback),
                    log_path, save_path, None)

    root.report_callback_exception = on_tk
    sys.excepthook = on_main
    threading.excepthook = on_thread


def run_guarded(fn, log_path, save_path=None):
    """Call fn() so that no failure is silent, whether or not there is a console to read.

    A deliberate stop (the progress window was closed) exits quietly. A SetupError or a message passed
    to sys.exit("...") is shown in a dialog; any other exception is logged and shown as "something
    unexpected went wrong". The program then exits (the exception is not re-raised as a traceback).
    """
    try:
        fn()
    except SystemExit as exc:
        if isinstance(exc.code, str) and exc.code != STOPPED_MESSAGE:
            append_log(log_path, exc.code)
            _stderr(exc.code)
            show_error(APP_TITLE, exc.code, headline="The program can't start yet")
        raise
    except Exception as exc:
        tb_text = traceback.format_exc()
        append_log(log_path, f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n{tb_text}")
        _stderr(tb_text)
        headline, advice = describe(exc)
        if isinstance(exc, SetupError):
            show_error(APP_TITLE, advice, headline=headline)
        else:
            saved = f"\n\nYour progress is saved{' in ' + save_path if save_path else ''}."
            show_error(APP_TITLE, f"{advice}{saved}", details=f"{tb_text}\nLog file: {log_path}",
                       headline=headline)
        raise SystemExit(1)
