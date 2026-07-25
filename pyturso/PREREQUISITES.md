# PREREQUISITES — project-wide

Self-test gate for the whole project. Before Phase 0, you should be able to
check every box; each names where to learn it (short cites resolve in the
[READING.md citation index](READING.md#citation-index)). Module folders have
their own PREREQUISITES.md gates on top of this one.

The test is *explain it out loud, unaided* — not "I've seen it before".

## Python (the port language — must be strong, not passable)

- [ ] Generators as resumable state machines: `yield`, `send()`, `throw()`,
      `close()`, `yield from`, return values via `StopIteration` — the
      project's core idiom rides on these. → Python docs; PEP 342, PEP 380.
- [ ] Dataclasses (incl. `frozen=True`) and `enum` — every AST/insn/plan
      node uses them. → Python docs.
- [ ] Typing: `Protocol`, generics basics, `from __future__ import
      annotations`; running mypy. → mypy docs.
- [ ] Binary data: `bytes` vs `bytearray` vs `memoryview`; `struct`
      pack/unpack with explicit endianness. → Python `struct` docs.
- [ ] pytest basics: fixtures, parametrize, tmp_path. → pytest docs.

## SQL & SQLite (the domain)

- [ ] Comfortable writing joins, GROUP BY, subqueries by hand — you cannot
      port what you cannot predict. → any solid SQL course; sqlite.org
      Language docs (D).
- [ ] Driving the `sqlite3` CLI shell: `.schema`, `.mode`, `.tables`,
      `EXPLAIN`, `PRAGMA integrity_check` — it is your microscope and
      oracle daily. → sqlite.org CLI doc (D).
- [ ] Python stdlib `sqlite3` module basics (connect/execute/fetch,
      exception classes). → Python docs.

## Binary & machine literacy

- [ ] Two's-complement integers at widths 8–64; big vs little endian;
      reading a hexdump without fear. → CS:APP ch. 2 (T).
- [ ] IEEE-754 doubles at "why is 0.1+0.2 != 0.3" depth. → CS:APP ch. 2.

## Reading Rust (comprehension only — fluency comes later, per Level R)

- [ ] Follow a Rust file using: structs/enums + `match`, `Option`/`Result`
      + `?`, traits/impl blocks, iterators. Enough to read `core/`, not to
      write it. → Rust Book chs. on those topics (T).

## Workflow

- [ ] Git: branch, small commits, revert, bisect basics.
- [ ] Running the repo's tursodb: `cargo run -q --bin tursodb -- -q`.

If any box is unchecked, fix that first — READING.md names the exact
chapter; the cost of skipping is paid back with interest in Phase 1.
