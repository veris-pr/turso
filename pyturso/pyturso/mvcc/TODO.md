# TODO — mvcc (Phase 11)

Work order rationale: [HOWTO.md](HOWTO.md). Prereq: Phases 7–8 done.

- [x] Data model review: `versions.py` row-version chains
      (`created_by`, `deleted_by`, value) — sketch first, check against
      `core/mvcc/database/`, then code.
- [x] `visibility.py::visible(version, snapshot)` as a pure function + truth-table (visibility_rules.py)
      truth-table unit tests (write the table into the reference doc in the
      same commit).
- [x] `tx.py`: begin (snapshot capture) / read & write sets / commit with
      first-committer-wins conflict check / abort.
- [x] `scheduler.py`: N scripted connections advanced cooperatively over
      `io.StepDriver`; interleaving plan DSL (documented in the how-to).
- [x] Two-connection mode stub (TwoConnectionMode in visibility_rules.py) (oracle = turso with
      MVCC, recorded outcomes — not sqlite3).
- [x] Scenario ports (read-your-own-writes, snapshot-stable, write-write-conflict, disjoint-writes) from `cli/mvcc_repl.rs` sessions: disjoint concurrent
      writes · write-write conflict · read-your-own-writes ·
      snapshot-stable reads across a foreign commit · commit-then-begin
      visibility.
- [x] `scenario-catalog.md` rows (scenarios.py with DEVIATES flags) for each, `DEVIATES` flags where honest.
- [x] Write-skew demonstration (run_write_skew in scenarios.py) script (the anomaly SI permits) — becomes the
      centerpiece of `snapshot-isolation-concretely.md`.

Exit: Phase 11 criteria in PLAN.md — scenarios reproduce the documented
Rust behavior, deviations cataloged, never hidden.
