# TOREAD — vdbe

Levels refer to [../../READING.md](../../READING.md).

## Before Phase 5

- [ ] SQLite [VDBE opcode doc](https://sqlite.org/opcode.html) — intro
      sections + the opcodes in the starter set (reference, keep open).
- [ ] SQLite [query-execution intro](https://sqlite.org/arch.html) VDBE
      section; run `EXPLAIN` on ten queries in the sqlite3 shell and read
      the listings until they feel like assembly you know.
- [ ] READING L1: CS:APP ch. 3 background pays off here — a register VM is
      a friendly ISA; if ch. 3 is unread, now is the moment.
- [ ] Repo guide: `docs/agent-guides/debugging.md` (bytecode comparison
      workflow — you are about to live it).
- [ ] Prereq from your own docs: `docs/io/explanation/ioresult-as-generators.md`
      — execute() is the biggest consumer of the convention.

## Rust source

- [ ] `core/vdbe/insn.rs` — the instruction vocabulary (skim all, port some).
- [ ] `core/vdbe/builder.rs` — labels/registers.
- [ ] `core/vdbe/execute.rs` — **per-opcode arms only, as ported**; the
      12k-LOC file is the project's best-commented reference manual.
- [ ] `core/vdbe/explain.rs` — listing format.

## Before Phase 10 (sorter & aggregates)

- [ ] READING L3: 15-445 sorting lecture (external merge sort) — the
      algorithm `sorter.py` implements small.
- [ ] Rust: `core/vdbe/sorter.rs`; aggregate paths in `execute.rs`.

## Docs you will write

`opcode-catalog.md` (ledger, every commit) · `program-format.md` ·
`vdbe-as-a-tiny-cpu.md` · `resumable-step.md` · `port-an-opcode.md` how-to ·
`single-step-your-first-program.md` tutorial · Phase 10:
`sorting-without-memory.md`. Status: `docs/vdbe/README.md`.
