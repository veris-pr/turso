# pyturso.functions — Scalar & aggregate SQL functions

**Ports:** `core/functions/` (`string.rs`, `math.rs`, `datetime.rs`,
`printf.rs`), `core/function.rs` (registry/dispatch), aggregate paths in
`core/vdbe/execute.rs`
**Phases:** 6 (scalar core) · 10 (aggregates, breadth)

## What this module is

The SQL function library and its registry — how a name+arity in SQL resolves
to executable behavior in the VM.

- **`registry.py`** (`core/function.rs`) — name/arity → function descriptor;
  scalar vs aggregate kinds; deterministic flag (matters to the optimizer).
- **`string.py`** — `length`, `upper`/`lower`, `substr`, `trim` family,
  `replace`, `instr`, `hex`/`unhex`, `quote`, `char`, `unicode`, LIKE/GLOB
  pattern matching (used by the `Like` operator too).
- **`math.py`** — `abs`, `round`, `ceil`/`floor`, `random`, math extensions;
  overflow/domain behavior must match, not just happy paths.
- **`datetime.py`** — `date`, `time`, `datetime`, `julianday`, `strftime`,
  modifiers; time comes from `io.clock` so tests are deterministic.
- **`printf.py`** — `printf`/`format` subset.
- **`aggregate.py`** — `count`, `sum`/`total`, `avg`, `min`/`max`,
  `group_concat`: step/finalize protocol driven by the VM's aggregation
  opcodes (Phase 10).

## Parity notes — this module is a parity minefield, which is the point

- `sum` returns INTEGER until overflow then REAL; `total` always REAL.
- `max(NULL, 1)` (scalar) vs `max(col)` (aggregate) are different functions.
- `round(2.5)`, negative `substr` indexes, `length` of BLOB vs TEXT,
  `strftime` edge modifiers — every rule verified three-way, and functions
  Turso implements differently from SQLite (if any are found) get documented
  in the function-catalog reference with a link to the Rust.
- The **function catalog reference doc** is the scope ledger: every function
  is green / planned(phase) / out-of-scope, with corpus coverage noted.

## Docs

Diátaxis tree: [../../docs/functions/README.md](../../docs/functions/README.md)
