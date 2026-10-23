# `src/ui_motion.py`

The animation engine (UI-4): easing, colour blending and the `Animator` every animation runs through.

- **Uses:** the standard library only
- **Used by:** `app`, `browser`, `ui_chart`, `widgets`
- **Tests:** `_selftest_chart`, `_selftest_motion`, `_selftest_widgets`, `_selftest_widgets2`

The module docstring has the details; this page is the map.

## Public API

- `ease_out_cubic`: Fast start, gentle landing.
- `lerp_color`: Blend two #RRGGBB colours: t=0 gives c1, t=1 gives c2 (t is clamped).
- `Animator`: Runs short animations on the Tk event loop (about 60 frames a second).
  - methods: busy, run, finish, is_running, hurry, hurry_all, finish_all, cancel_all

## Rules and pitfalls (fixed before: keep them fixed)

- Animations are short (<= 250 ms), ease out, never loop, and nothing runs while idle.
- A key press speeds running animations out of the way (`hurry_all`), never jumps them.
- Reduce motion makes `run` jump to the end; frame callbacks are tiny and never query the database.
- A frame or end callback that finds its widget destroyed is dropped (`_gone`); any other error is raised as before.
