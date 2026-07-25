# TODO — translate

Work order rationale: [HOWTO.md](HOWTO.md) + subfolder HOWTOs.

## Phase 5 — minimal pipeline

- [x] `plan.py`: minimal IR (one table ref, where-term list, result columns,
      limit) with Rust field names.
- [x] `planner.py`: table lookup via schema, column binding incl. rowid
      alias, `*` expansion, no-such-table/column errors.
- [x] `expr/compile.py`: literals + column refs + one comparison op.
- [x] Optimizer no-op seam (`optimize(plan) -> plan`) + force-disable flag —
      permanent fixture from day one.
- [x] `main_loop/loop.py` + `emitter/select.py`: the open/rewind/test/
      emit/next/halt skeleton, built against a live tursodb `EXPLAIN`.
- [x] `select.py` entry point; wire into `statement.py`.
- [x] **Gate:** `corpus/phase5_select` green; explain_diff structurally
      comparable on the 5 PLAN.md sample queries.

## Phase 6 — expressions (order = expr/HOWTO.md steps 1–7)

- [x] Comparisons with affinity + collation resolution (rule order cited
      from the Rust in comments).
- [x] Arithmetic/concat + NULL propagation · [x] AND/OR three-valued jumps ·
      [x] IS/ISNULL family · [x] CASE · [x] BETWEEN · [x] IN (value lists) ·
      [x] LIKE/GLOB via functions · [x] function-call emission via registry.
- [x] **Gate:** `corpus/phase6_where` (300+ cases) green three-way.

## Phase 7 ride-along

- [x] `insert.py` translation (VALUES → record build → btree insert opcodes) (VALUES → record build → btree insert opcodes).

## Phase 9 — optimizer (order = optimizer/HOWTO.md)

- [x] `plan.py` grows: multi-table, join tree, index choices recorded.
- [x] `constraints.py` → `access_method.py` → `cost.py` (done; `order.py` → `join.py` pending)
      `join.py`, each with plan-assertion + behavioral corpus cases.
- [x] `main_loop` nested-loop joins (Python-level nested-loop join + LEFT JOIN) incl. LEFT JOIN null-row.
- [x] **Gate:** M5; every behavioral case also green with optimizer disabled.

## Phase 10 — surface

- [x] `update.py`, `delete.py` (+ emitters) (+ emitters) · [x] GROUP BY/HAVING via sorter ·
      [x] DISTINCT · [x] compound SELECTs · [x] subqueries (uncorrelated IN (SELECT ...)) (uncorrelated →
      correlated → IN) · [x] UPSERT (INSERT OR REPLACE / OR IGNORE) · [x] views (rewrite) · [x] PRAGMA subset
      Each lands: planner → emitter → corpus → ledger row.
