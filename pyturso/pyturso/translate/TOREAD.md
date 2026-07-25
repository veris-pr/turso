# TOREAD — translate

Levels refer to [../../READING.md](../../READING.md).

## Before Phase 5

- [ ] SQLite [Architecture doc](https://sqlite.org/arch.html) — where
      translation sits; 10 minutes, orients everything.
- [ ] READING L3: 15-445 query-execution lecture (processing models) — know
      what a Volcano iterator is so you can see SQLite/Turso *not* doing it
      (compiled bytecode instead) and why.
- [ ] Prereqs from your own docs: `docs/vdbe/reference/opcode-catalog.md`
      (grows in lockstep) and `docs/schema/reference/object-model.md`.
- [ ] Rust: `core/translate/plan.rs` → `planner.rs` → `emitter/select.rs` +
      `main_loop/` — in that order, tracking one query through all three.

## Before Phase 6

- [ ] SQLite Datatypes doc §"Comparison Expressions" — the
      affinity-in-comparisons rules; the module's hardest parity surface.
- [ ] Rust: `core/translate/expr/` (per-operator as you port),
      `core/translate/collate.rs` (now for real).

## Before Phase 9

- [ ] **`core/translate/optimizer/OPTIMIZER.md`** — the Rust module's own
      design doc; the assigned reading for the phase.
- [ ] SQLite [Query Optimizer Overview](https://sqlite.org/optoverview.html)
      and [Next-Gen Query Planner](https://sqlite.org/queryplanner-ng.html).
- [ ] READING L3/L4: 15-445 query-optimization lectures; *Use The Index,
      Luke* (whole site — quick, high-yield).
- [ ] Rust: optimizer files in the TODO's port order, one per sitting.

## Before Phase 10

- [ ] 15-445 sorting/aggregation + join-algorithms lectures.
- [ ] Rust: `core/translate/{group_by,aggregation,compound_select,subquery}.rs`
      per feature as ported.

## Docs you will write

`plan-ir.md` · `emission-skeletons.md` · `three-stage-compilation.md` ·
`diff-bytecode-against-tursodb.md` how-to · Phase 9: constraint/cost
references + both planner explanations · Phase 10: per-feature shorts.
Status: `docs/translate/README.md`.
