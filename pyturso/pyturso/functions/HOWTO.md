# HOWTO — functions

What the module is: [README.md](README.md). Phase 6 (scalars), Phase 10
(aggregates). This module is a long tail of small parity battles — the
per-function loop below keeps each one contained.

## Work order

1. **`registry.py`** — name (case-insensitive) + arity → descriptor
   (callable, kind, deterministic flag). Read `core/function.rs` for how
   lookup handles variadic arities (`substr/2` and `/3`, `-1` conventions).
   Wire the VM's function-call opcode to it once, then never touch dispatch
   again.
2. **Scalars, in dependency order:** `string.py` first (LIKE/GLOB matching
   lives here and the `Like` operator needs it), then `math.py`, then
   `datetime.py` (all time via `io.clock` — no `time.time()` anywhere),
   then `printf.py`.
3. **Phase 10 — `aggregate.py`:** step/finalize objects driven by the VM's
   aggregation opcodes; land together with the vdbe side and the GROUP BY
   emitter, not before.

## The per-function loop (do not batch functions!)

1. Read the function's Rust implementation in `core/functions/`.
2. Port it. 3. Corpus cases: happy path, **every-arg-NULL**, a
   type-coercion case, and the function's known edges (from the Rust code
   and its tests). 4. Add its row to
   `docs/functions/reference/function-catalog.md` (the scope ledger) with
   corpus coverage noted. 5. Commit — one function (or one tight family) per
   commit keeps divergence bisectable.

## Gotchas already known (each needs its corpus case)

- `sum` (INTEGER until overflow → REAL; NULL on empty) vs `total`
  (always REAL; 0.0 on empty).
- 2-arg scalar `max(a, b)` vs 1-arg aggregate `max(col)` — the registry must
  hold both.
- `substr` negative/zero indexes; `length()` on BLOB (bytes) vs TEXT (chars);
  `round` half-away behavior via C formatting, not Python's bankers'
  rounding; `printf` `%d` on REAL truncates toward zero.
- If Turso deliberately diverges from SQLite anywhere here, Turso wins
  (source of truth) — document the case in the catalog with the Rust link.

## Verify

Corpus `phase6_functions` (three-way) is the gate; unit tests only for pure
helpers (pattern compiler for LIKE/GLOB, strftime format parser).
