# TODO — package root (API & assembly)

Work order rationale: [HOWTO.md](HOWTO.md).

## Phase 0

- [x] `errors.py`: hierarchy ported from `core/error.rs` variants
      (`TursoError` base; `Corrupt`, `ParseErr`-mapping, `Constraint`,
      `Busy`, `NotSupported`, …) + mapping table used by the differential
      harness (error → comparison class).

## Phase 5

- [x] `database.py`: `Database.open(path)` / `open_memory()`; owns io
      backend + pager; `connect()`.
- [x] `connection.py`: schema load (+ cache), `prepare(sql)`,
      `execute(sql)` convenience, `close()` semantics.
- [x] `statement.py`: `step()` generator over the VM (row / done),
      iteration + `run()` drivers on top, `reset()`, `finalize()`,
      use-after-finalize errors; positional parameter binding (`?`, `?N`).
- [x] Lifecycle unit tests: step-reset-restep, iterator equivalence,
      finalize errors, two independent statements on one connection.
- [x] `docs/api/reference/public-api.md` + `error-hierarchy.md` current.
- [x] Start `docs/api/explanation/anatomy-of-a-query.md` (capstone) (capstone; grows
      every later phase — schedule a paragraph per phase close).

## Phase 8

- [x] Transaction state on connection: autocommit flag, BEGIN/COMMIT/
      ROLLBACK statements routed; write-txn exclusivity vs a second
      connection (single-process rules; document the simplification).
- [x] Schema-cookie staleness check on prepare (wires `schema.is_stale`).

## Phase 10+

- [x] `pragma.py`: `table_info`, `index_list`, `page_count`, `journal_mode`
      (read), ledgered in docs.
- [x] Named parameter binding (`:name`) (`:name`) when the corpus first needs it.

## Phase 12 ride-alongs

- [x] Non-interactive exec helper (cli/exec.py) for the CLI; `.schema` support queries.
