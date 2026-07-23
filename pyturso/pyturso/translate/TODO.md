# TODO — translate

Work order rationale: [HOWTO.md](HOWTO.md) + subfolder HOWTOs.

## Phase 5 — minimal pipeline

- [ ] `plan.py`: minimal IR (one table ref, where-term list, result columns,
      limit) with Rust field names.
- [ ] `planner.py`: table lookup via schema, column binding incl. rowid
      alias, `*` expansion, no-such-table/column errors.
- [ ] `expr/compile.py`: literals + column refs + one comparison op.
- [ ] Optimizer no-op seam (`optimize(plan) -> plan`) + force-disable flag —
      permanent fixture from day one.
- [ ] `main_loop/loop.py` + `emitter/select.py`: the open/rewind/test/
      emit/next/halt skeleton, built against a live tursodb `EXPLAIN`.
- [ ] `select.py` entry point; wire into `statement.py`.
- [ ] **Gate:** `corpus/phase5_select` green; explain_diff structurally
      comparable on the 5 PLAN.md sample queries.

## Phase 6 — expressions (order = expr/HOWTO.md steps 1–7)

- [ ] Comparisons with affinity + collation resolution (rule order cited
      from the Rust in comments).
- [ ] Arithmetic/concat + NULL propagation · [ ] AND/OR three-valued jumps ·
      [ ] IS/ISNULL family · [ ] CASE · [ ] BETWEEN · [ ] IN (value lists) ·
      [ ] LIKE/GLOB via functions · [ ] function-call emission via registry.
- [ ] **Gate:** `corpus/phase6_where` (300+ cases) green three-way.

## Phase 7 ride-along

- [ ] `insert.py` translation (VALUES → record build → btree insert opcodes).

## Phase 9 — optimizer (order = optimizer/HOWTO.md)

- [ ] `plan.py` grows: multi-table, join tree, index choices recorded.
- [ ] `constraints.py` → `access_method.py` → `cost.py` → `order.py` →
      `join.py`, each with plan-assertion + behavioral corpus cases.
- [ ] `main_loop` nested-loop joins incl. LEFT JOIN null-row.
- [ ] **Gate:** M5; every behavioral case also green with optimizer disabled.

## Phase 10 — surface

- [ ] `update.py`, `delete.py` (+ emitters) · [ ] GROUP BY/HAVING via sorter ·
      [ ] DISTINCT · [ ] compound SELECTs · [ ] subqueries (uncorrelated →
      correlated → IN) · [ ] UPSERT · [ ] views (rewrite) · [ ] PRAGMA subset.
      Each lands: planner → emitter → corpus → ledger row.
