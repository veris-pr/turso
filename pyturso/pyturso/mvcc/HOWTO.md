# HOWTO — mvcc

What the module is: [README.md](README.md). Phase 11, strictly after Phases
7–8. This is a **concept port**: model parity with Turso's MVCC behavior, not
mechanism parity ([../../PLAN.md](../../PLAN.md) §2).

## Before writing code

Read, in order: `docs/agent-guides/mvcc.md` (repo root — including the
limitations list; it doubles as this phase's checklist),
`cli/mvcc_repl.rs` (the scenarios it enables are your target behaviors),
then `core/mvcc/database/` and `core/mvcc/cursor.rs` for the visibility and
commit logic. Log unanswerable questions as explanation-doc stubs, per the
standard loop.

## Work order

1. **`versions.py`** — row-version chains: `(created_by_tx, deleted_by_tx,
   value)` records keyed by rowid. Get the data model reviewed against the
   Rust before building on it — everything else sits on this.
2. **`visibility.py`** — the snapshot predicate as one pure function
   `visible(version, snapshot) -> bool`. Pure function = truth-table
   unit tests; write the table into
   `docs/mvcc/reference/visibility-rules.md` as you write the tests.
3. **`tx.py`** — begin (snapshot capture), read/write sets, first-committer-
   wins conflict detection at commit, abort. Mirror the Rust's terminology.
4. **`scheduler.py`** — the cooperative driver: takes N scripted connections
   and an interleaving plan, advances each via the `io.StepDriver` machinery.
   This file is pyturso-specific; its DSL is documented in
   `docs/mvcc/how-to/script-an-interleaving.md`.

## Verify

- Port scenarios from `cli/mvcc_repl.rs` sessions into
  `docs/mvcc/reference/scenario-catalog.md` + scripted tests: concurrent
  disjoint writes, write-write conflict, read-your-own-writes,
  snapshot-stable reads while another tx commits.
- Oracle is **turso with MVCC enabled** (drive `tursodb`/`mvcc_repl`
  scenarios manually and record outcomes) — sqlite3 has nothing to say here.
- Behavior gaps vs the Rust are recorded per-scenario in the catalog, flagged
  `DEVIATES`, never hidden.
