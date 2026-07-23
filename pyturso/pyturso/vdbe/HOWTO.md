# HOWTO — vdbe

What the module is: [README.md](README.md). Phase 5 builds the machine;
opcodes accumulate through Phase 10.

## Phase 5 — the machine

1. **`insn.py`** — only the opcodes the phase needs (~15). Names verbatim
   from `core/vdbe/insn.rs`. One dataclass per opcode beats a generic
   5-operand struct: field names document semantics.
2. **`program.py` + `explain.py`** — the program container and its EXPLAIN
   listing (addr, opcode, p1..p4, comment) formatted like tursodb's so
   `tools/explain_diff.py` can align them.
3. **`builder.py`** — append, `Label` allocation + `resolve()` backpatching,
   register allocation (bump allocator first; port the Rust's reuse scheme
   only when register counts start diverging wildly in explain_diff).
4. **`execute.py`** — the dispatch loop: `pc`, register file, cursor table.
   A generator (I/O flows through cursors' yields via `yield from`). Port
   each opcode handler by reading its arm in `core/vdbe/execute.rs` — the
   handler comments there are the spec. Start: Init, Transaction, OpenRead,
   Rewind, Column, ResultRow, Next, Halt, Integer, String8, and the
   comparison jumps.
5. **`metrics.py`** — opcode counter dict; wire into the loop now while it's
   one line.

## Growing the machine (Phases 6–10)

Follow the port-an-opcode checklist every time:
read the `execute.rs` arm → port handler + insn → corpus case that executes
it → row in `docs/vdbe/reference/opcode-catalog.md` (same commit) →
explain_diff spot-check. The catalog is the scope ledger; an opcode without a
catalog row doesn't exist.

Phase 10 adds **`sorter.py`** (read `core/vdbe/sorter.rs`): implement as a
cursor-shaped object (open/insert/rewind/next) so ORDER BY/GROUP BY emission
stays symmetric with table cursors.

## Gotchas

- Comparison opcodes apply affinity per p4/flags — take the rules from
  `execute.rs`, not from intuition; this is where wrong-rows bugs hide.
- NULL jump behavior differs per opcode (jump-if-null flags) — port flags,
  don't approximate.
- Halt vs error paths: errors carry the error class the harness compares on.

## Verify

Unit: builder label/patching, single-opcode handler tests (hand-built
programs, no SQL). Integration: corpus via the API; `--trace` (via
`tools/trace_fmt.py`) when a case diverges — trace the first register that
differs from your mental execution, then read that opcode's Rust arm again.
