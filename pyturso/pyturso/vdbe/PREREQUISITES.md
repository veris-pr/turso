# PREREQUISITES — vdbe

Gate before [TODO.md](TODO.md). Cites resolve in
[READING.md](../../READING.md#citation-index).

- [ ] Virtual machines: bytecode, dispatch loop, program counter; register
      machines vs stack machines (this is a *register* VM — Nystrom's VM
      chapters teach a stack VM; know the difference going in).
      → *Crafting Interpreters* part III concepts (T); CS:APP ch. 3 for
      the assembly mindset.
- [ ] Jumps as control flow: conditionals/loops compiled to conditional
      jumps + addresses; why forward jumps need label backpatching.
- [ ] Cursors as the only storage interface: an opcode never touches a
      page; it moves a cursor. → your own `docs/storage/` Phase 1 docs.
- [ ] Read an `EXPLAIN` listing cold: take five queries into the sqlite3
      shell, and for each, narrate the program row by row before checking
      your story. This exercise *is* the gate. → SQLite VDBE opcode doc (D).
- [ ] Resumability: why `step()` must be able to suspend mid-program (the
      io convention again). → `docs/io/explanation/ioresult-as-generators.md`.
- [ ] Working prereqs green: Phase 1 cursors; types module for `Value`
      semantics in comparison opcodes.
