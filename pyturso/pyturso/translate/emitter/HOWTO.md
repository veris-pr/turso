# HOWTO — translate/emitter

Ports `core/translate/emitter/`. Emitters turn a *decided* plan into opcodes —
they hold no policy. If you find yourself choosing an access path here, the
code belongs in `optimizer/`; if evaluating an expression, in `expr/`.

The work:
1. Phase 5: `select.py` — the open/loop/close skeleton: Init/Transaction,
   OpenRead, Rewind..Next loop, Column/ResultRow, Halt. Port it by reading
   `emitter/select.rs` and `main_loop/` side by side with an actual
   `EXPLAIN SELECT ...` from tursodb on the screen.
2. Register allocation and label patching go through `vdbe.builder` only —
   never hand-number a register or address.
3. Phase 10: `delete.py`, `update.py` (mirroring the Rust file set).

Done when: emitted programs run green in the phase corpus and explain_diff
shows the same structural skeleton as tursodb.
