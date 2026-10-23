# `src/ui_chart.py`

The tier chart (six bars), each tab's own view in that spot (Refine's settled chart, the conflicts card) and the progress shelf of book spines (UI-13, UI-14, UI-31).

- **Uses:** `constants`, `smooth`, `theme`, `ui_motion`
- **Used by:** `app`
- **Tests:** `_selftest_chart`

The module docstring has the details; this page is the map.

## Public API

- `compact`: 1,234 -> '1,234'; 12,345 -> '12.3K'; 1,234,567 -> '1.2M' (the cap labels stay short).
- `DistributionChart`: Six bars, one per tier, with the letter under each and the count on top.
  - methods: set, pulse, bar_top, bars_top, shown, show, refresh
- `SettledChart`: Refine within tier (UI-31): how settled each tier's order is.
  - methods: set
- `ConflictCard`: Resolve conflicts (UI-31): not a chart, one number on a soft card, "3 / to look at", or "None / nicely consistent" once the last one is resolved.
  - methods: set, show, refresh
- `format_share`: A segment's share placed, short: '100%' only when complete, '97%', '0.3%', '0%' when none.
- `format_coverage`: The coverage text (UI-14): the share of running text made of placed words, "95% of text", with as many decimals as it takes to keep moving near 100% (93%, 99.4%,...
- `soft_median`: Where the middle placed word falls, as a position on the tier scale 0 (S) ..
- `leaning`: The tier most over-represented in `tiers` compared with the whole list (`overall`, per-tier counts), or None when nothing is placed.
- `mark_color`: A shelf mark's colour: its word's tier pastel, deepened so a small triangle still shows on the page (M-4); the lilac for a word with no tier.
- `Bookshelf`: The progress shelf (UI-14): a shelf of book spines on a log scale of commonness, split into zones named for how often you would meet such a word (page, chapter, book,...
  - methods: hover, set, mark, spine_at, note, refresh

## Rules and pitfalls (fixed before: keep them fixed)

- The bookshelf design is a settled decision (zones, heights, blended colours, hover note): ask before changing it.
- Bars ease with `DistributionChart._ease`; nothing animates while idle.
