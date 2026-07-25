# HOWTO — translate/main_loop

Ports `core/translate/main_loop/` — the shared scaffolding that opens cursors,
drives the row loop(s), applies WHERE terms, and closes up. Every statement
kind funnels through here; per-statement emitters fill in the middle.

The work:
1. Phase 5: single-table loop (open, rewind, test terms, inner body, next).
2. Phase 9: nested-loop joins — loop nesting order comes from the optimizer's
   chosen join order; left-join NULL-row handling gets its own corpus cases.
3. Keep the seam with `emitter/` clean: main_loop owns loop structure,
   emitters own what happens per row.

Read `core/translate/main_loop/` alongside an EXPLAIN of a two-table join
from tursodb to see the shape you are porting toward.
