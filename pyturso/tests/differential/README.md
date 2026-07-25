# tests/differential — The three-way parity harness

**Mirrors in spirit:** `scripts/diff.sh` and the `.sqltest` differential
philosophy of `sqlite/conformance/` — every behavioral claim is checked
against real engines, never against hand-written expectations alone.
**Phase:** 0 (exists before the engine does), grows every phase.
**This harness is the project's definition of truth.**

## How it works

```
corpus/<phaseN_topic>/<case>.sql
        │
        ├──► stdlib sqlite3  ──┐
        ├──► tursodb (subproc) ─┼──► normalize ──► three-way compare ──► report
        └──► pyturso ──────────┘
```

- **sqlite3 ≠ tursodb** on a case → the case is wrong or interesting; it gets
  quarantined with a note (this also occasionally finds real turso divergences
  — report those upstream! contribution pipeline, not noise).
- **pyturso ≠ oracle** → a red parity gate for the owning phase.

## Corpus layout & format

```
corpus/
  phase1_read/        # fixtures via tools/mkdb.py + dump comparisons
  phase5_select/      # first SQL-driven cases
  phase6_where/  phase6_functions/
  phase7_writes/  phase8_txn/  phase9_plans/  phase10_surface/
  from_sqltest/       # cases ported from sqlite/conformance/sqlite-sqltests/
    MANIFEST.md       # per-file: ported? partial? why not? — the scope ledger
```

A case is a plain `.sql` script plus optional front-matter comments:

```sql
-- setup: fixture=people.sql        (built by tools/mkdb.py, sqlite3-made)
-- expect-error: OperationalError   (error-class cases)
SELECT name, age FROM people WHERE age >= 30 ORDER BY name;
```

## Normalization rules (the hard-won part — documented as they are earned)

- Row/column rendering unified to a canonical form (pipe-separated, `NULL`
  literal, BLOBs hex-encoded).
- Float formatting: sqlite3's %.15g convention is the canonical rendering.
- Errors compared by **class** (mapped per engine), never message text.
- Unordered queries compared as multisets; ordered queries as sequences —
  a case opts into ordered comparison by having an ORDER BY.

## Engines

| Engine | Invocation | Notes |
|--------|-----------|-------|
| sqlite3 | stdlib `sqlite3` in-process | fast path oracle |
| tursodb | `cargo run -q --bin tursodb -- -q <db>` from repo root | binary located via env `TURSODB_BIN` or built on demand |
| pyturso | in-process | the subject |

File-level checks ride along where a case writes: `PRAGMA integrity_check`
via sqlite3 on the pyturso-written file, and `tools/dbhash` comparison for
logical-twin databases (Phases 7–8).

Phase 11 adds a scripted **two-connection mode** (MVCC scenarios; oracle is
turso, not sqlite3 — see [../../pyturso/mvcc/README.md](../../pyturso/mvcc/README.md)).

## What is deliberately NOT ported from turso's suites

Rust unit/integration tests, simulator/fuzz harnesses, sanitizer runs — they
test the Rust implementation, not SQL behavior. Their *behavioral intent*
arrives here as corpus cases when relevant; the MANIFEST records the mapping.
