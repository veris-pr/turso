# TODO — vdbe

Work order rationale: [HOWTO.md](HOWTO.md).

## Phase 5 — the machine

- [ ] `insn.py`: the starter ~15 opcodes as per-opcode dataclasses (Init,
      Transaction, OpenRead, Rewind, Column, Rowid, ResultRow, Next, Halt,
      Integer, Real, String8, Null, Eq/Ne/Lt/Le/Gt/Ge, Goto).
- [ ] `program.py`: instruction list + cursor/register counts + origin SQL.
- [ ] `explain.py`: listing formatted to align with tursodb `EXPLAIN`.
- [ ] `builder.py`: append; `Label`/`resolve()` backpatching (unresolved
      label at finalize = assertion); bump register allocator.
- [ ] Builder unit tests: forward-jump patching, nested labels.
- [ ] `execute.py`: generator dispatch loop (pc, registers, cursor table,
      `yield from` into cursors); handlers for the starter set, each ported
      from its `core/vdbe/execute.rs` arm.
- [ ] Comparison handlers: affinity application per flags + NULL jump
      behavior ported from the Rust, with per-opcode unit programs.
- [ ] `metrics.py` opcode counters wired into the loop.
- [ ] `--trace` hook (register writes + jumps) consumable by
      `tools/trace_fmt.py`.
- [ ] **Gate:** hand-built programs pass unit tests; Phase 5 corpus green
      through the API.

## Phases 6–10 — growth (per-opcode checklist every time)

- [ ] Phase 6 batch: Function, arithmetic ops, concat, If/IfNot, IsNull/
      NotNull, jump-family for CASE/IN/BETWEEN, Like machinery.
- [ ] Phase 7 batch: OpenWrite, NewRowid, MakeRecord, Insert, Delete +
      write-txn opcodes.
- [ ] Phase 9 batch: index opcodes (SeekGE/GT/LE/LT, IdxRowid …) as the
      optimizer starts emitting them.
- [ ] Phase 10: `sorter.py` (cursor-shaped: open/insert/rewind/next) +
      Sorter* opcodes; aggregate step/finalize opcodes; RowSet/Once/subquery
      support opcodes as needed.
- [ ] Standing: every opcode lands with its catalog row + corpus case;
      catalog has no silent gaps.
