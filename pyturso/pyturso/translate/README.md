# pyturso.translate — AST → plan → optimized plan → bytecode

**Ports:** `core/translate/` — `planner.rs`, `plan.rs`, `optimizer/`,
`emitter/`, `expr/`, `main_loop/`, and the per-statement translators
(`select.rs`, `insert.rs`, `update.rs`, `delete.rs`, `group_by.rs`,
`aggregation.rs`, `order_by.rs`, `compound_select.rs`, `subquery.rs`, …)
**Phases:** 5 (minimal SELECT) · 6 (expressions) · 9 (optimizer) · 10 (surface)

## What this module is

The compiler middle-end and back-end. The parser produced *what the user
said*; this module decides *how to execute it* and emits a `vdbe.Program`:

```
AST ──► planner.py ──► plan.py (logical plan: tables, joins,     ──► optimizer/ ──► emitter/ ──► vdbe.Program
        (name res.,     where terms, result columns, order/limit)    (access paths,   (opcode
         validation)                                                  join order,      emission,
                                                                      constraint       main loop,
                                                                      extraction)      registers/labels)
```

- **`plan.py`** (`plan.rs`) — the central IR: source-table operators, WHERE
  terms as a constraint list, result columns, ORDER BY/LIMIT. Understanding
  this one type is understanding half the compiler.
- **`planner.py`** (`planner.rs`) — AST → plan: name resolution against the
  schema, column binding, star-expansion, validity errors.
- **`optimizer/`** (`optimizer/` — start with its `OPTIMIZER.md`) — Phase 9:
  constraint extraction (`constraints.rs`), access-method choice
  (`access_method.rs`), cost model (`cost.rs`), join ordering (`join.rs`),
  ORDER BY satisfaction via index (`order.rs`). Until Phase 9, a pass-through
  "always seq-scan" optimizer keeps the pipeline honest — and stays forever
  as the correctness baseline (results must be identical with the optimizer
  disabled).
- **`emitter/`** + **`main_loop/`** — plan → opcodes: the open-loop-body-close
  skeleton every query shares, register allocation, label patching, and
  per-statement emitters (`emitter/select.rs`, `emitter/delete.rs`, …).
- **`expr/`** — expression compilation, shared by everything: literals,
  column refs, operators with affinity/collation resolution, function calls,
  CASE/IN/BETWEEN/LIKE. Phase 5 starts it; Phase 6 completes it.

## Porting order inside the module (matches PLAN.md)

1. Phase 5: `plan.py` + `planner.py` + `emitter/select.py` + minimal `expr/`
   for one-table `SELECT … WHERE … LIMIT`.
2. Phase 6: `expr/` completed (the bulk of `core/translate/expr/`).
3. Phase 9: `optimizer/` for real; `main_loop` grows joins.
4. Phase 10: per-statement translators, one file per feature, mirroring the
   Rust file list above.

## Parity notes

- `EXPLAIN` diffing against tursodb (`tools/explain_diff.py`) is the primary
  understanding tool here — structural similarity is expected, opcode-exact
  equality is not a gate ([../../PLAN.md](../../PLAN.md) parity Tier 3).
- Translation must be *rejecting*: unsupported constructs raise a clean
  "not supported by pyturso (phase N)" error, keeping the scope ledger honest.

## Docs

Diátaxis tree: [../../docs/translate/README.md](../../docs/translate/README.md)
