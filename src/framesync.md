# `src/framesync.py`

X11 only (F-53, asked for): a maximized or resized window never shows its old picture in its top-left corner.

- **Uses:** the standard library only
- **Used by:** `app`
- **Tests:** `_selftest_framesync`

The module docstring has the details; this page is the map.

## Public API

- `FrameSync`: The window's part in it: made by `enable`.
  - methods: set_background, after_resize, answer
- `enable`: Turn frame sync on for `root` (before it is first shown); the FrameSync, or None where it cannot be.

## Rules and pitfalls (fixed before: keep them fixed)

- Every Xlib call goes through Tk's own connection (`Tk_Display`, the first field of the main window from `Tk_MainWindow(interpaddr)`), never one of our own: a second connection's requests can reach the X server before Tk's drawing they are meant to follow.
- The page's X window has centre gravity, so the X server moves it by half a size change: `after_resize` must put it back at (0, 0) at every root `<Configure>` (Tk itself only resizes it), or the whole page stays shifted.
- mutter (46) sends `_NET_WM_SYNC_REQUEST` only while an edge is dragged, never for a maximize (its window-x11.c): the maximize is covered by the gravity, not by frame sync. An unanswered request freezes the window for mutter until its timeout, so a request is answered even when no new size follows (60 ms).
- The wrapper's background is the page colour (`set_background`): it shows round the moved picture while the window grows.
- `enable` returns None anywhere it cannot work (not X11, no XSync, a library missing): every caller checks.
- On a window manager without frame sync (openbox), a dragged edge can show the page shifted by half the step for a frame; GNOME and KDE sync drags.
