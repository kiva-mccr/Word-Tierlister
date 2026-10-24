"""Friendly error dialogs and the program-wide safety net (ST-2).

    show_error(title, message, details=None, parent=None)  /  show_message(title, headline, message)
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
import contextlib
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import traceback
import webbrowser
from tkinter import ttk

from fonts import font, init_fonts
from problems import STOPPED_MESSAGE, SetupError, append_log, describe
from theme import PALETTE
from ui_style import apply_ttk_style
from widgets import StyledDialog

APP_TITLE = "Word Tier List"
open_link = webbrowser.open     # how a link in a dialog opens its page (tests replace it)
REPEAT_SECONDS = 5      # the same error again within this time only goes to the log
_state = {"open": False, "last_key": None, "last_time": 0.0}


def _stderr(text):
    if sys.stderr is not None:
        print(text, file=sys.stderr)


@contextlib.contextmanager
def _window_for(parent):
    """`parent`, or (when None) a hidden, styled window of our own for a dialog, destroyed afterwards."""
    own_root = None
    if parent is None:
        own_root = parent = tk.Tk()
        own_root.withdraw()
        init_fonts(own_root)
        apply_ttk_style(own_root)
    try:
        yield parent
    finally:
        if own_root is not None:
            try:
                own_root.destroy()
            except tk.TclError:
                pass


def show_error(title, message, details=None, parent=None, headline=None):
    """Show a modal error dialog and wait for it to close (stderr if no window can be made).

    `headline` is the short bold line; `message` the explanation; `details` (optional) the technical
    text kept behind "Show details" and copied by "Copy details".
    """
    try:
        with _window_for(parent) as win:
            _dialog(win, title, headline or title, message, details)
    except Exception:
        _stderr(f"{title}: {headline or ''} {message}\n{details or ''}")


def show_message(title, headline, message, parent=None):
    """A plain styled message with an OK button (no error look, no details): a merge result, say."""
    show_error(title, message, parent=parent, headline=headline)


def ask_yes_no(title, headline, message, yes="OK", no="Cancel", parent=None, wrap_chars=44):
    """A small styled question dialog. Returns True for the `yes` button, False for `no`, Escape or close.

    Falls back to False (the safe answer) when no window can be shown."""
    answer = {"yes": False}
    try:
        with _window_for(parent) as win:
            _dialog(win, title, headline, message, None, buttons=((yes, True), (no, False)), answer=answer,
                    wrap_chars=wrap_chars)
    except Exception:
        _stderr(f"{title}: {headline} {message}")
    return answer["yes"]


def ask_choices(title, headline, message, choices, yes="OK", no="Cancel", parent=None):
    """A styled question with one tick box per choice (ST-4: each package is its own choice).

    `choices` are (key, label, detail, ticked[, required[, (link text, url)]]) tuples; the detail is a muted
    line under the label, a required choice gets a red asterisk after its label, and a link (UI-30) is shown
    between the tick box and the label as a quiet underlined word that opens its page in the browser.
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


def _dialog(parent, title, headline, message, details, buttons=None, answer=None, choices=None, wrap_chars=44):
    """Every dialog here, on the shared StyledDialog (UI-24). `buttons` are (label, value) pairs, the first
    is the default (drawn rightmost, pressed by Enter); without them there is one OK button."""
    dlg = StyledDialog(parent, title, headline, message, wrap_chars=wrap_chars)
    box, wrap = dlg.body, dlg.wrap
    ticks = []
    if choices:                      # one tick box per choice, each with a muted line saying what it is for
        for key, label, detail, ticked, *rest in choices:
            var = tk.BooleanVar(value=ticked)
            line = ttk.Frame(box)
            line.pack(anchor="w", pady=(6, 0))
            link = rest[1] if len(rest) > 1 and rest[1] and rest[1][1] else None
            tick = ttk.Checkbutton(line, text="" if link else label, variable=var, takefocus=1)
            tick.pack(side="left")
            if link:                         # the tick box, the name as a link, then the rest of the label
                _link_label(line, *link).pack(side="left")
                rest_lbl = ttk.Label(line, text=label)
                rest_lbl.pack(side="left")
                rest_lbl.bind("<Button-1>", lambda e, t=tick: t.invoke())     # still toggles, like the box's text
            if rest and rest[0]:             # required: the classic red asterisk
                ttk.Label(line, text="*", foreground=PALETTE["required"], font=font("head")).pack(side="left")
            if detail:
                ttk.Label(box, text=detail, wraplength=wrap - 30, justify="left",
                          foreground=PALETTE["muted"]).pack(anchor="w", padx=(26, 0))
            ticks.append((key, var))
    txt = tk.Text(box, height=9, width=1, wrap="word", font=font("body"), relief="flat",
                  bg=PALETTE["surface"], fg=PALETTE["text"], padx=8, pady=6)
    if details:
        txt.insert("1.0", details)
    txt.config(state="disabled")
    shown = tk.BooleanVar(value=False)

    def toggle():
        shown.set(not shown.get())
        if shown.get():
            txt.pack(fill="x", pady=(12, 0))
            toggle_btn.config(text="Hide details")
        else:
            txt.pack_forget()
            toggle_btn.config(text="Show details")
        dlg.refit()

    def copy():
        dlg.win.clipboard_clear()
        dlg.win.clipboard_append(f"{headline}\n{message}\n\n{details or ''}")
        copy_btn.config(text="Copied")

    if details:
        toggle_btn = dlg.button("Show details", toggle, side="left")
        copy_btn = dlg.button("Copy details", copy)
    if buttons:                      # a question
        def choose(value):
            answer["yes"] = value
            answer["chosen"] = {k for k, v in ticks if v.get()}
            dlg.close()
        for i, (label, value) in reversed(list(enumerate(buttons))):
            dlg.button(label, lambda v=value: choose(v), default=(i == 0))
        dlg.on_cancel = lambda: choose(False)
    else:
        dlg.button("OK", dlg.close, default=True)
    dlg.show(wait=True)


def _link_label(parent, text, url):
    """A quiet link: muted and underlined, darker on hover; a click opens `url` in the browser (UI-30)."""
    f = tkfont.Font(font=font("body"))
    f.configure(underline=True)
    lbl = tk.Label(parent, text=text, font=f, fg=PALETTE["muted"], bg=PALETTE["bg"], cursor="hand2", padx=0, bd=0)
    lbl.font = f                                          # keep a reference (tk does not)
    lbl.url = url
    lbl.bind("<Enter>", lambda e: lbl.config(fg=PALETTE["text"]))
    lbl.bind("<Leave>", lambda e: lbl.config(fg=PALETTE["muted"]))
    lbl.bind("<Button-1>", lambda e: open_link(url))
    return lbl


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


FREEZE_SECONDS = 10                   # the window not answering this long is written in the log (asked for)
_watch = {"root": None, "beat": 0.0, "paused": True, "log": None, "limit": FREEZE_SECONDS, "reported": False,
          "longest": 0.0, "thread": None}


def watch_freezes(root, log_path, every_ms=500, limit=FREEZE_SECONDS):
    """Write in the log when the window stops answering (asked for: freezes too, not only errors). The window's
    event loop ticks every `every_ms`; a worker thread (which never touches Tk) checks the ticks, and when there
    has been none for `limit` seconds it writes what every thread was doing then (faulthandler's stacks: where it
    is stuck), and a line again when the window answers once more. One thread for the program; a new window (a new
    look) takes over the ticking, and a closed one stops it."""
    w = _watch
    w.update(root=root, log=log_path, limit=limit, beat=time.monotonic(), paused=False)

    job = [None]

    def tick():
        if w["root"] is root:
            w["beat"] = time.monotonic()
            try:
                job[0] = root.after(every_ms, tick)
            except tk.TclError:
                pass

    def closed(e):
        if e.widget is not root:
            return
        if w["root"] is root:
            w["paused"] = True
        try:                                   # (a tick left waiting would fire into the closed window: an error)
            root.tk.call("after", "cancel", job[0])
        except tk.TclError:
            pass
    job[0] = root.after(every_ms, tick)
    root.bind("<Destroy>", closed, add="+")
    if w["thread"] is None:
        w["thread"] = threading.Thread(target=_watch_loop, daemon=True)
        w["thread"].start()


def _watch_loop(check_every=1.0):
    import faulthandler
    w = _watch
    while True:
        time.sleep(check_every)
        if w["paused"]:
            w["reported"] = False
            continue
        stalled = time.monotonic() - w["beat"]
        if stalled >= w["limit"] and not w["reported"]:
            w["reported"], w["longest"] = True, stalled
            append_log(w["log"], f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\nThe window has not responded for "
                                 f"{stalled:.0f} s. What each part of the program was doing then:")
            try:
                with open(w["log"], "a", encoding="utf-8", errors="replace") as f:
                    faulthandler.dump_traceback(file=f, all_threads=True)
            except (OSError, ValueError):
                pass
        elif w["reported"]:
            w["longest"] = max(w["longest"], stalled)
            if stalled < 2 * check_every:
                w["reported"] = False
                append_log(w["log"], f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\nThe window responds again (it "
                                     f"did not for about {w['longest']:.0f} s).")


def install_handlers(root, log_path, save_path=None):
    """Route every unexpected error to the log (and, for the window's own errors, a friendly dialog), and note
    freezes there too (watch_freezes)."""
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
    watch_freezes(root, log_path)


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
