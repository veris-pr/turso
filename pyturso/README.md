# pyturso

A Python port of the Turso database engine, built module-by-module with the Rust
code in this repository as the source of truth.

This is **not a toy**. It is a serious, parity-targeting port whose purpose is
understanding: by re-implementing each subsystem in Python and continuously
verifying it against `sqlite3` and `tursodb`, the architecture, data flow, and
invariants of the Rust engine become legible to a reader who is not yet a
systems programmer.

## Doctrine

1. **Rust is the source of truth.** Every pyturso module names the Rust files it
   ports. When behavior is ambiguous, read the Rust, not the SQLite docs first.
2. **Parity is the target.** Same SQL in → same rows out. Files written by
   pyturso must be readable by `sqlite3` and `tursodb` (and vice versa).
3. **Concept over mechanism.** Where Rust idioms don't translate (ownership,
   `unsafe`, io_uring), we port the *state machine and data flow*, not the
   syntax. The one deliberate analog: Turso's `IOResult::IO` yield points are
   modeled with Python **generators** (`yield` = "I/O pending, resume me").
4. **Everything is verified differentially.** The oracle is three-way:
   Python's stdlib `sqlite3`, the `tursodb` CLI from this repo, and pyturso.
   See [tests/differential/README.md](tests/differential/README.md).
5. **Every module is documented with Diátaxis.** Tutorials, how-to guides,
   reference, explanation — per module, under [docs/](docs/README.md).

## Layout

| Path | Ports | Rust source of truth |
|------|-------|----------------------|
| [pyturso/](pyturso/README.md) | Public API: Database, Connection, Statement | `core/lib.rs`, `core/connection.rs`, `core/statement.rs` |
| [pyturso/types/](pyturso/types/README.md) | Values, serial types, records, affinity, numerics | `core/types.rs`, `core/vdbe/value.rs`, `core/vdbe/affinity.rs`, `core/numeric/` |
| [pyturso/io/](pyturso/io/README.md) | I/O abstraction, completions, memory/posix backends | `core/io/` |
| [pyturso/storage/](pyturso/storage/README.md) | On-disk format, pager, page cache, B-tree, WAL | `core/storage/` |
| [pyturso/parser/](pyturso/parser/README.md) | Tokenizer, lexer, AST, recursive-descent parser | `sqlite/parser/src/` |
| [pyturso/schema/](pyturso/schema/README.md) | Schema objects, `sqlite_schema` interpretation | `core/schema.rs` |
| [pyturso/translate/](pyturso/translate/README.md) | AST → plan → optimizer → bytecode emission | `core/translate/` |
| [pyturso/vdbe/](pyturso/vdbe/README.md) | Bytecode instruction set, program builder, interpreter | `core/vdbe/` |
| [pyturso/functions/](pyturso/functions/README.md) | Scalar/aggregate SQL functions | `core/functions/`, `core/function.rs` |
| [pyturso/mvcc/](pyturso/mvcc/README.md) | Multi-version concurrency (late-phase, concept port) | `core/mvcc/` |
| [cli/](cli/README.md) | REPL mirroring `tursodb` | `cli/` (repo root) |
| [tools/](tools/README.md) | Inspection & diffing tools (page hexdump, explain-diff…) | `tools/`, `scripts/diff.sh` |
| [tests/](tests/README.md) | Unit tests and the three-way differential harness | `sqlite/conformance/`, `tests/` |
| [docs/](docs/README.md) | Diátaxis documentation, one tree per module | `docs/agent-guides/` |

## Build order

The project is built in phases, storage-first (most concrete, verifiable
against real database files from day one), pipeline later. The complete,
followable plan — phase goals, Rust reading lists, exit criteria, verification
gates, documentation deliverables — is in **[PLAN.md](PLAN.md)**.

## Quickstart (once Phase 0 lands)

```bash
cd pyturso
python -m pytest tests/unit                 # unit tests
python -m tests.differential.run corpus/    # three-way differential run
python -m tools.dbdump path/to/file.db      # walk a real database file
```

Requirements: Python ≥ 3.11, stdlib only (no third-party runtime deps;
`pytest` for tests). The differential harness additionally shells out to
`sqlite3` and `cargo run -q --bin tursodb` from the repo root.

## What parity means here

- **Tier 1 — behavioral parity (hard requirement):** identical result rows,
  identical error *class* (not necessarily message text), for every statement
  in the differential corpus.
- **Tier 2 — file-format parity (hard requirement for the write path):**
  database files written by pyturso pass `PRAGMA integrity_check` in sqlite3,
  open in `tursodb`, and hash-match via the repo's `tools/dbhash` when the
  same logical content is written.
- **Tier 3 — bytecode parity (advisory):** `EXPLAIN` output is compared
  against tursodb as a *debugging and understanding tool*; opcode-for-opcode
  equality is a stretch goal, not a gate.

## What is explicitly out of scope

- Performance. Clarity beats speed in every trade-off.
- Threads, io_uring, and platform-specific I/O (modeled, not replicated).
- Extensions/vtabs, vector search, sync/CDC, encryption — until core parity
  is achieved (each gets a placeholder decision in PLAN.md).
