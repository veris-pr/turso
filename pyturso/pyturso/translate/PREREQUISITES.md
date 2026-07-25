# PREREQUISITES — translate

Gate before [TODO.md](TODO.md), split by phase. Cites resolve in
[READING.md](../../READING.md#citation-index).

## Before Phase 5

- [ ] The compilation pipeline shape: front-end (AST) → IR (plan) →
      back-end (code emission), and why stages are separated. → any
      compiler intro; *Crafting Interpreters* gives enough.
- [ ] Logical vs physical: "what rows" (plan) vs "how to get them"
      (access method, opcodes). → CMU 15-445 query processing lecture (C).
- [ ] Name resolution/binding: how `SELECT a FROM t` turns into "column 0
      of cursor 0", incl. the rowid-alias wrinkle. → 15-445; your own
      `docs/schema/` outputs.
- [ ] Execution models: Volcano/iterator vs compiled-bytecode — SQLite/
      Turso use the latter; know what you're *not* building. → 15-445
      processing-models segment.
- [ ] Working prereqs green: parser (Phase 3), schema (Phase 4), vdbe
      skeleton concepts ([../vdbe/PREREQUISITES.md](../vdbe/PREREQUISITES.md)
      — read together; the two modules co-evolve).

## Before Phase 6

- [ ] Affinity in comparisons: which operand coerces, when, per the
      Datatypes doc §comparison expressions — the phase's entire risk is
      this section. → SQLite Datatypes doc (D).
- [ ] Three-valued logic: NULL through AND/OR/NOT and comparison operators.

## Before Phase 9

- [ ] Index access paths: seek vs scan vs covering; why an index on
      `(a,b)` serves `WHERE a=? AND b>?` but not `WHERE b>?`. → *Use The
      Index, Luke* (T, free).
- [ ] Selectivity & cost estimation, roughly: why the planner needs
      numbers at all. → 15-445 optimization lectures (C).
- [ ] Join algorithms: nested loop (what you'll build) vs hash/merge (what
      you won't — know why). → 15-445 joins lecture.
- [ ] The standing rule and its reason: correctness never depends on the
      optimizer (seq-scan baseline must produce identical results).
