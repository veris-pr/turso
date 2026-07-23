# TOREAD — tests/differential

Levels refer to [../../READING.md](../../READING.md).

## Before building (Phase 0)

- [ ] READING L6 anchor: [How SQLite Is Tested](https://sqlite.org/testing.html)
      — sets the bar and the vocabulary; the harness you are building is a
      tiny cousin of what it describes.
- [ ] Repo: `scripts/diff.sh` (the pattern, 50 lines) and a browse of
      `sqlite/conformance/sqlite-sqltests/` `.sqltest` files (the behavioral
      test mindset; your corpus format is its spiritual sibling).
- [ ] Repo guide: `docs/agent-guides/testing.md` — turso's own taxonomy of
      test types and when each is used.
- [ ] Python stdlib `sqlite3` module docs — connection/cursor behavior,
      `executescript` semantics, exception classes (your oracle adapter and
      your error-class mapping both live on this page).

## Watch (once, early — shapes the whole project)

- [ ] Will Wilson, *Testing Distributed Systems with Deterministic
      Simulation* (Strange Loop 2014) — why determinism + injected failure
      beats flaky integration tests; the philosophy behind StepDriver,
      crash injection, and Phase 11's scheduler.

## Later slices

- [ ] Phase 7: repo `tools/dbhash` source (what logical equality means).
- [ ] Phase 11: `cli/mvcc_repl.rs` + mvcc TOREAD (the two-connection mode's
      spec source).
