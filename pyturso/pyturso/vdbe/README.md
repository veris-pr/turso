# pyturso.vdbe — The virtual machine

**Ports:** `core/vdbe/` — `insn.rs`, `builder.rs`, `execute.rs` (12k LOC,
ported opcode-by-opcode), `explain.rs`, `sorter.rs`, `value.rs` (lives in
`types/`), plus `hash_table.rs`/`rowset.rs`/`bloom_filter.rs` as their
opcodes arrive
**Phases:** 5 (skeleton) · 6 (expression opcodes) · 9–10 (joins, sorting,
aggregation opcodes)

## What this module is

The engine's CPU. Turso, like SQLite, compiles every statement into a program
for a register-based virtual machine (the VDBE — Virtual DataBase Engine),
then executes it with a dispatch loop. A program is a list of instructions:

```
addr  opcode        p1    p2    p3    p4          comment
0     Init          0     7     0                 Start at 7
1     OpenRead      0     2     0                 root=2; cursor 0 on table t
2     Rewind        0     6     0                 to first row, or jump to 6
3       Column      0     1     1                 r[1] = t.col1
4       ResultRow   1     1     0                 emit r[1]
5     Next          0     3     0                 next row, loop to 3
6     Halt          0     0     0
7     Transaction   0     0     0                 then jump back to 1
```

The machine state: a register file (`Value` slots), open cursors (over B-trees,
sorters, or pseudo-tables), and a program counter. Control flow is jumps;
data flow is registers; tables are reached only through cursors.

## Planned files

| File | Ports | Notes |
|------|-------|-------|
| `insn.py` | `insn.rs` | opcode enum + operand dataclasses, Rust/SQLite names kept verbatim |
| `builder.py` | `builder.rs` | `ProgramBuilder`: append insns, labels + backpatching, register allocation |
| `program.py` | program repr | the compiled artifact `translate/` produces |
| `execute.py` | `execute.rs` | the dispatch loop + one handler per opcode; grows for 5+ phases |
| `explain.py` | `explain.rs` | EXPLAIN-format listing, diffable against tursodb |
| `sorter.py` | `sorter.rs` | external-sort cursor backing ORDER BY/GROUP BY (Phase 10) |
| `metrics.py` | `metrics.rs` | opcode counters — cheap, and great for understanding |

## Key concepts to port

- **step() is resumable.** The Rust dispatch loop returns on `IOResult::IO`
  and re-enters at the same pc. pyturso's `execute` is a generator over the
  io layer (see [io/README.md](../io/README.md)), so the same program can run
  synchronously or under a step-controlled test driver.
- **The instruction set is the contract** between compiler and machine —
  the opcode reference doc is maintained in the same commit as any
  `insn.py`/`execute.py` change (Diátaxis reference discipline).
- **Cursors are the only view of storage.** No opcode touches pages;
  everything goes through `storage.btree.BTreeCursor` — keeping the layer
  boundary as strict as the Rust does.

## Parity notes

- Opcode semantics come from `core/vdbe/execute.rs` first, SQLite's opcode
  documentation second (Turso is the source of truth when they diverge).
- Register-level tracing (`--trace` on the pyturso CLI, later) mirrors the
  debugging workflow in `docs/agent-guides/debugging.md`.

## Docs

Diátaxis tree: [../../docs/vdbe/README.md](../../docs/vdbe/README.md)
