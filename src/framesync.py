"""X11 only: a resized window never shows its old picture in the top-left corner (F-53, asked for).

Until Tk lays out and draws a new size, the X server keeps the window's old picture, by default in its top-left
corner: on a maximize it looked as if the window had been in the top left. Two things, both on Tk's own X
connection (ctypes; Tk_Display is the first field of a Tk window, so each request follows Tk's drawing in order):
- the page's X window gets centre gravity: the old picture is moved by half the change instead, so a window in the
  middle of the screen keeps its picture where it was (App._slide_from_here then eases the contents from there),
  and `after_resize` puts the page back in the window's corner once Tk has the new size;
- frame sync (_NET_WM_SYNC_REQUEST): a window manager that asks first (mutter does only while an edge is dragged,
  never for a maximize: its source, 46) shows a new size only once it is drawn.
Anywhere else (Windows, macOS, no XSync extension, no libraries found) `enable` returns None and nothing changes.
"""
import ctypes
import ctypes.util
import sys

STEP = 240      # (the EWMH's: the window manager asks for its last value + 240)


class _Value(ctypes.Structure):
    _fields_ = [("hi", ctypes.c_int), ("lo", ctypes.c_uint)]


def _value(n):
    return _Value(n >> 32, n & 0xFFFFFFFF)


class _Attributes(ctypes.Structure):          # (XSetWindowAttributes)
    _fields_ = [("background_pixmap", ctypes.c_ulong), ("background_pixel", ctypes.c_ulong),
                ("border_pixmap", ctypes.c_ulong), ("border_pixel", ctypes.c_ulong),
                ("bit_gravity", ctypes.c_int), ("win_gravity", ctypes.c_int), ("backing_store", ctypes.c_int),
                ("backing_planes", ctypes.c_ulong), ("backing_pixel", ctypes.c_ulong), ("save_under", ctypes.c_int),
                ("event_mask", ctypes.c_long), ("do_not_propagate_mask", ctypes.c_long),
                ("override_redirect", ctypes.c_int), ("colormap", ctypes.c_ulong), ("cursor", ctypes.c_ulong)]


CW_BACK_PIXEL, CW_WIN_GRAVITY, CENTER_GRAVITY = 1 << 1, 1 << 5, 5


class FrameSync:
    """The window's part in it: made by `enable`."""

    def __init__(self, root, x11, xext, dpy, counter, wrapper):
        self.root, self.x11, self.xext, self.dpy, self.counter = root, x11, xext, dpy, counter
        self.wrapper = wrapper
        self.value = 0
        self.asked = False       # a request came: answered once the next drawing is done
        self._job = None

    def _requested(self):
        self.asked = True
        if self._job is None:    # (answered even if no new size follows)
            self._job = self.root.after(60, self.answer)

    def set_background(self, colour):
        """The colour round the old picture while the window grows (the page's own, for a new look too)."""
        r, g, b = (v >> 8 for v in self.root.winfo_rgb(colour))
        attrs = _Attributes(background_pixel=(r << 16) | (g << 8) | b)
        self.x11.XChangeWindowAttributes(self.dpy, self.wrapper, CW_BACK_PIXEL, ctypes.byref(attrs))

    def after_resize(self):
        """The window has its new size: the page back in the window's corner (the X server moved it by half the
        change: CENTER_GRAVITY), and the window manager answered once the new size is drawn."""
        self.x11.XMoveWindow(self.dpy, self.root.winfo_id(), 0, 0)
        if self.asked:
            if self._job is not None:
                self.root.after_cancel(self._job)
            self._job = self.root.after_idle(self.answer)

    def answer(self):
        """Drawn: tell the window manager (the counter at the value it asked for, its last + STEP)."""
        self._job = None
        if not self.asked:
            return
        self.asked = False
        try:
            self.root.update_idletasks()        # (drawn: Tk draws at idle)
        except Exception:
            return
        self.value += STEP
        self.xext.XSyncSetCounter(self.dpy, self.counter, _value(self.value))
        self.x11.XFlush(self.dpy)


def enable(root):
    """Turn frame sync on for `root` (before it is first shown); the FrameSync, or None where it cannot be."""
    if not sys.platform.startswith("linux") and not sys.platform.startswith("freebsd"):
        return None
    try:
        if root.tk.call("tk", "windowingsystem") != "x11":
            return None
        tk_lib = ctypes.CDLL(ctypes.util.find_library("tk8.6") or "libtk8.6.so")
        x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        xext = ctypes.CDLL(ctypes.util.find_library("Xext") or "libXext.so.6")
        tk_lib.Tk_MainWindow.restype = ctypes.c_void_p
        tk_lib.Tk_MainWindow.argtypes = [ctypes.c_void_p]
        main = tk_lib.Tk_MainWindow(root.tk.interpaddr())
        if not main:
            return None
        dpy = ctypes.c_void_p.from_address(main).value     # (Tk_Display: a Tk window's first field)
        ev, err, major, minor = (ctypes.c_int() for _ in range(4))
        xext.XSyncQueryExtension.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
        xext.XSyncInitialize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
        if not xext.XSyncQueryExtension(dpy, ctypes.byref(ev), ctypes.byref(err)):
            return None
        if not xext.XSyncInitialize(dpy, ctypes.byref(major), ctypes.byref(minor)):
            return None
        xext.XSyncCreateCounter.restype = ctypes.c_ulong
        xext.XSyncCreateCounter.argtypes = [ctypes.c_void_p, _Value]
        xext.XSyncSetCounter.argtypes = [ctypes.c_void_p, ctypes.c_ulong, _Value]
        x11.XInternAtom.restype = ctypes.c_ulong
        x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x11.XChangeProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
        x11.XFlush.argtypes = [ctypes.c_void_p]
        counter = xext.XSyncCreateCounter(dpy, _value(0))
        if not counter:
            return None
        root.update_idletasks()                             # (the window made, not shown)
        wrapper = int(root.wm_frame(), 16)                  # (the window the window manager manages)
        data = (ctypes.c_ulong * 1)(counter)
        atom = x11.XInternAtom(dpy, b"_NET_WM_SYNC_REQUEST_COUNTER", 0)
        x11.XChangeProperty(dpy, wrapper, atom, 6, 32, 0, data, 1)     # (6: CARDINAL; 0: replace)
        x11.XChangeWindowAttributes.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p]
        x11.XMoveWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int]
        attrs = _Attributes(win_gravity=CENTER_GRAVITY)
        x11.XChangeWindowAttributes(dpy, root.winfo_id(), CW_WIN_GRAVITY, ctypes.byref(attrs))
        sync = FrameSync(root, x11, xext, dpy, counter, wrapper)
        root.protocol("_NET_WM_SYNC_REQUEST", sync._requested)
        x11.XFlush(dpy)
        return sync
    except Exception:
        return None
