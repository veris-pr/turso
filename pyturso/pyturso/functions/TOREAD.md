# TOREAD — functions

Levels refer to [../../READING.md](../../READING.md).

## Before starting

- [ ] SQLite [core functions doc](https://sqlite.org/lang_corefunc.html) —
      the behavioral spec, function by function; re-open per function as you
      port it (never port from memory of "what length() obviously does").
- [ ] SQLite [date/time functions doc](https://sqlite.org/lang_datefunc.html)
      — before `datetime.py`; the modifier pipeline is spec'd here.
- [ ] SQLite [aggregate functions doc](https://sqlite.org/lang_aggfunc.html)
      — before Phase 10 work.
- [ ] Prereq from your own docs: `docs/types/reference/affinity-rules.md`
      and `comparison-order.md` — function args coerce by these rules.

## Rust source

- [ ] `core/function.rs` — registry/dispatch shape (before `registry.py`).
- [ ] `core/functions/string.rs` / `math.rs` / `datetime.rs` / `printf.rs`
      — per function, as ported; where the Rust and the SQLite doc disagree,
      **the Rust wins** and the catalog documents it.
- [ ] Aggregate paths in `core/vdbe/execute.rs` (Phase 10).

## While building

- [ ] READING L6: skim SQLite's "How SQLite Is Tested" §on anomaly testing —
      the mindset for the per-function edge hunting this module demands.

## Docs you will write

`function-catalog.md` (the ledger — grows every commit here) ·
`null-semantics.md` · `datetime-formats.md` · `three-valued-logic.md` ·
Phase 10: `scalar-vs-aggregate.md` · `add-a-scalar-function.md` tutorial ·
`hunt-a-function-divergence.md` how-to. Status: `docs/functions/README.md`.
