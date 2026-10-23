# `src/store.py`

The save file: every read and write of the SQLite database goes through `Store` (words, tiers, ratings, duels, conflicts, anchors, cached definitions, settings, the undo history, the rude meanings).

- **Uses:** `constants`, `obscene`, `rudeness`
- **Used by:** `browser`, `speed_check`, `tierlist`
- **Tests:** none of its own

The module docstring has the details; this page is the map.

## Public API

- `Store`: All persistence and ranking logic.
  - methods: close, get_meta, meta_number, set_meta, get_def, set_def, count_words, insert_words, add_word, has_word, get_word, next_unplaced, left_out, queue_settings, reshuffle, deal_settings, set_deal, set_censor, set_kinds, save_rude_senses, rude_senses, set_rude, smeared_meanings, obscene_words, censored, kind_counts, tier_counts, stats, shelf_layout, shelf, spine_of, set_frequencies, settled_shares, swap_counts, actions_since, get_anchors, set_anchors, undo, place, unplace, skip, record_comparison, pick_within, pick_boundary, pick_conflict, list_words, export_rows, skipped_words, backup, parse_export, merge

## Rules and pitfalls (fixed before: keep them fixed)

- Every public method that changes data commits before returning; no animation frame may touch the database.
- Anything run per duel or per refresh must stay fast on a million-word save: read the indexes, check `EXPLAIN QUERY PLAN` for "TEMP B-TREE", test a dense and a sparse save.
- Long work (a reshuffle) runs on a worker thread while nothing else writes.
- Settings are text in `meta`; read numbers with `meta_number` (it handles damaged values), not `int(get_meta(...))`.
- Change a word's tier only through Store methods: they keep the running tallies (`tier_counts`, the shelf) with `_tier_moved`, or recount with `_forget_tallies` (a bulk write, a rollback). A write around the Store is not noticed.
- Browse's orders name their index (`INDEXED BY`, `_PLACED_INDEX` / `_UNPLACED_INDEX`): without fresh statistics the planner sorted every row instead (up to 0.9 s in a million). A new sort needs its index there.
- Per-duel and per-refresh work is index-only: `stats()` (the skipped count by `idx_words_skipped`), `_least_dueled` (no `ORDER BY ... RANDOM()` over a whole run), `settled_shares` (counts the smaller side). Test on a 1M save, dense and sparse.

## Changing it

- Schema changes: `SCHEMA`, plus an `ALTER TABLE` in `Store.__init__` that adds a new column to an older save when it opens.
- Merge rules for imports live in `merge` / its helpers: a placed word is never overwritten.
