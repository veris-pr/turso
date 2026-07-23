# HOWTO — translate/optimizer

Ports `core/translate/optimizer/`. **Read `core/translate/optimizer/OPTIMIZER.md`
(the Rust module's own doc) before anything else** — it is the map.

Standing rule: the optimizer is an optimization. Results must be identical
with it force-disabled; the always-seq-scan baseline from Phase 5 is kept
runnable forever (harness flag), and every behavioral corpus case passes both
ways.

Port order (Phase 9):
1. `constraints.py` — which WHERE shapes become index-usable constraints.
2. `access_method.py` — seq scan vs index seek/scan vs covering index.
3. `cost.py` — the cost model; copy the Rust constants and cite them in
   docs/translate/reference/cost-model.md.
4. `order.py` — ORDER BY satisfaction via index (sort elision).
5. `join.py` — join-order search over nested loops.

Each step lands with: behavioral cases + structural EXPLAIN assertions in
corpus/phase9_plans, and its reference doc row.
