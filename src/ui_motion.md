# `src/ui_motion.py`

The animation engine (UI-4): easing, colour blending and the `Animator` every animation runs through.

- **Uses:** the standard library only
- **Used by:** `app`, `browser`, `tiercolours`, `ui_chart`, `widgets`
- **Tests:** `_selftest_chart`, `_selftest_motion`, `_selftest_tabswitch`, `_selftest_widgets`, `_selftest_widgets2`

The module docstring has the details; this page is the map.

## Public API

- `ease_out_cubic`: Fast start, gentle landing.
- `lerp_color`: Blend two #RRGGBB colours: t=0 gives c1, t=1 gives c2 (t is clamped).
- `Animator`: Runs short animations on the Tk event loop (about 60 frames a second).
  - methods: busy, run, finish, stop, is_running, hurry, hurry_all, finish_all, cancel_all

## Rules and pitfalls (fixed before: keep them fixed)

- `Animator.stop(key)` leaves an animation where it is (no end state, no on_done): only for one that carries on another way (the definitions pane stopped mid-slide and eased on from there, F-41). Everything else finishes or hurries.
- Animations are short (<= 250 ms), ease out, never loop, and nothing runs while idle.
- A key press speeds running animations out of the way (`hurry_all`), never jumps them.
- Reduce motion makes `run` jump to the end; frame callbacks are tiny and never query the database.
- A frame or end callback that finds its widget destroyed is dropped (`_gone`); any other error is raised as before.
- A frame held up by other work moves an animation on by `STALL_MS` at most, never to where the clock says: after a stall the definitions pane leapt open (F-22). Only with the real clock (a test's clock jumps on purpose); tests that pump every 50 ms still finish an animation in about its time / 50 ms frames.
