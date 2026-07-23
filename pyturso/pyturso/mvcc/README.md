# pyturso.mvcc — Multi-version concurrency (concept port)

**Ports (conceptually):** `core/mvcc/` — `database/`, `cursor.rs`,
`persistent_storage/`, visibility/commit logic
**Phase:** 11 (late; requires Phases 7–8 done)

## What this module is

A *concept port* of Turso's experimental MVCC: the one module where we
explicitly do not chase mechanism parity, because the Rust implementation is
itself experimental and concurrency mechanism doesn't translate to
single-threaded Python. What we port is the **model**:

- **Row versions**: each logical row as a chain of versions stamped with
  creating/deleting transaction ids.
- **Snapshots**: a transaction sees the database as of its begin timestamp —
  visibility rules decide which version of each row is in view.
- **Write-write conflicts**: two transactions touching the same row — first
  committer wins, the other aborts; no locks held across user code.
- **Commit & GC**: making versions durable and pruning versions no snapshot
  can see.

"Concurrency" is modeled with multiple `Connection` objects driven
cooperatively by a scripted scheduler (the generator yield points from
[io/](../io/README.md) are the interleaving hooks) — the same idea as Turso's
deterministic simulator and `cli/mvcc_repl.rs`, which is the behavioral
reference: scenarios scripted there should reproduce in pyturso.

## Planned files

| File | Ports (conceptually) |
|------|----------------------|
| `versions.py` | row-version chains, tx id stamping |
| `visibility.py` | snapshot visibility rules |
| `tx.py` | begin/commit/abort, conflict detection |
| `scheduler.py` | scripted cooperative interleaving driver (pyturso-specific) |

## Parity notes

- Oracle for this module is **turso itself** (MVCC enabled), not sqlite3 —
  sqlite has no MVCC. The differential harness grows a two-connection
  scripted mode for this phase.
- Deviations from Rust behavior are recorded per-scenario in the docs;
  `docs/agent-guides/mvcc.md` limitations list is the checklist.

## Docs

Diátaxis tree: [../../docs/mvcc/README.md](../../docs/mvcc/README.md)
