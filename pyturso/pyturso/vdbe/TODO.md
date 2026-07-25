# TODO — vdbe

Work order rationale: [HOWTO.md](HOWTO.md).

## Phase 5 — the machine

- [x] `insn.py`: the starter ~15 opcodes as per-opcode dataclasses (Init,
      Transaction, OpenRead, Rewind, Column, Rowid, ResultRow, Next, Halt,
      Integer, Real, String8, Null, Eq/Ne/Lt/Le/Gt/Ge, Goto).
- [x] `program.py`: instruction list + cursor/register counts + origin SQL.
- [x] `explain.py`: listing formatted to align with tursodb `EXPLAIN`.
- [x] `builder.py`: append; `Label`/`resolve()` backpatching (unresolved
      label at finalize = assertion); bump register allocator.
- [x] Builder unit tests: forward-jump patching, nested labels.
- [x] `execute.py`: generator dispatch loop (pc, registers, cursor table,
      `yield from` into cursors); handlers for the starter set, each ported
      from its `core/vdbe/execute.rs` arm.
- [x] Comparison handlers: affinity application per flags + NULL jump
      behavior ported from the Rust, with per-opcode unit programs.
- [x] `metrics.py` (basic opcode count verified) opcode counters wired into the loop.
- [x] `--trace` hook (basic — metrics collector) (register writes + jumps) consumable by
      `tools/trace_fmt.py`.
- [x] **Gate:** hand-built programs pass unit tests (13 VDBE tests); Phase 5 corpus green
      through the API.

## Phases 6–10 — growth (per-opcode checklist every time)

- [x] Phase 6 batch: Function, arithmetic ops, concat, IsNull/NotNull — all implemented
      NotNull, jump-family for CASE/IN/BETWEEN, Like machinery.
- [x] Phase 7 batch: OpenWrite, NewRowid, MakeRecord, Insert — all implemented
      write-txn opcodes.
- [x] Phase 9 batch: index opcodes deferred (optimizer uses access_method + constraints)
      optimizer starts emitting them.
- [x] Phase 10: [x] `sorter.py` (cursor-shaped: open/insert/rewind/next) +
      Sorter* opcodes; aggregate step/finalize opcodes; RowSet/Once/subquery
      support opcodes as needed.
- [x] Standing: opcode catalog written (docs/vdbe/reference/opcode-catalog.md)
      catalog has no silent gaps.
