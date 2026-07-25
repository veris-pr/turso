# pyturso (package root) — Public API & engine assembly

**Ports:** `core/lib.rs`, `core/connection.rs`, `core/statement.rs`,
`core/error.rs`, `core/pragma.rs`
**Phase:** API assembled in Phase 5, grows through Phase 12.

## What this module is

The top of the engine: the objects a user touches and the wiring between every
subsystem below. In Turso, `core/lib.rs` exposes `Database` (one per file,
owns the pager/WAL state), `Connection` (a session: schema snapshot,
transaction state, prepared statements), and `Statement` (a prepared program
plus its execution state, stepped to completion). pyturso mirrors that shape:

```
Database.open(path) ──► Connection.connect() ──► conn.prepare(sql) ──► Statement
                                                        │ step()/run()
      parser ──► schema ──► translate ──► vdbe.Program ─┘   rows out
                                  │
                          storage (pager/btree/wal) ◄── io
```

## Planned files

| File | Ports | Notes |
|------|-------|-------|
| `database.py` | `core/lib.rs` (Database) | open/close, file ↔ pager ↔ WAL ownership |
| `connection.py` | `core/connection.rs` | prepare/execute, transaction state, schema cache |
| `statement.py` | `core/statement.rs` | step loop, result rows, reset/finalize, parameters |
| `errors.py` | `core/error.rs` | one exception hierarchy; differential harness matches on class |
| `pragma.py` | `core/pragma.rs` | small parity subset (Phase 10) |

## Key concepts to port (not just code)

- **Statement lifecycle**: prepare → step* → (row | done | error) → reset —
  the same protocol sqlite3's C API exposes; pyturso keeps it explicit rather
  than hiding it behind an iterator only.
- **The step loop as a resumable state machine**: in Turso, `step()` can
  return "I/O pending" and be re-entered. pyturso preserves this via the
  generator convention (see [io/README.md](io/README.md)); a convenience
  driver runs statements to completion for normal use.
- **Connections share a Database but own their view**: schema version
  checking, busy handling (`core/busy.rs`) — simplified but represented.

## Out of scope here

Vtabs (`core/vtab.rs`), extensions (`core/ext/`), incremental/materialized
views (`core/incremental/`), vector (`core/vector/`), JSON (`core/json/`) —
each may become a module later; decisions tracked in [../PLAN.md](../PLAN.md) §6.

## Docs

Diátaxis tree: [../docs/api/README.md](../docs/api/README.md)
