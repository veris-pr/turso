# pyturso docs — Diátaxis, per module

Documentation is a first-class deliverable of every phase
([../PLAN.md](../PLAN.md) §5): the end goal of this project is understanding,
and these docs are where that understanding is banked.

## How Diátaxis is applied here

Each module owns a doc tree with four quadrants, distinguished by what the
reader is doing:

|  | **Serves study** | **Serves work** |
|---|---|---|
| **Practical** | `tutorials/` — guided, do-this-see-that, written after the module stabilizes | `how-to/` — recipes for tasks (inspect a page, diff bytecode) |
| **Theoretical** | `explanation/` — why it works this way; the understanding artifacts | `reference/` — formats, catalogs, tables; updated in the same commit as behavior |

House rules:

- Every **explanation** doc ends with an **"In Turso"** section: links to the
  Rust source files, what pyturso ports faithfully, what it simplifies, and
  what the Rust does that pyturso doesn't. This section is the bridge from
  Python understanding to Rust fluency — it is the whole point.
- **Reference** docs are scope ledgers where noted (grammar, opcodes,
  functions, dot-commands): every item is supported / planned(phase) /
  out-of-scope. No silent gaps.
- Quadrant folders are created when their first doc lands; until then each
  module's `README.md` lists the planned docs with status.
- Drawings encouraged; if an explanation can't be drawn, it isn't understood
  yet (see the Phase 7 balancing doc mandate).

## Doc map

| Module tree | Covers | Main phases |
|---|---|---|
| [api/](api/README.md) | Database/Connection/Statement, engine assembly | 5, 12 |
| [types/](types/README.md) | values, serial types, records, affinity | 2 |
| [io/](io/README.md) | completions, generator yield-point convention | 1 |
| [storage/](storage/README.md) | file format, pager, B-tree, WAL | 1, 7, 8 |
| [parser/](parser/README.md) | tokens, grammar, AST | 3 |
| [schema/](schema/README.md) | sqlite_schema, object model | 4 |
| [translate/](translate/README.md) | plans, optimizer, emission | 5, 6, 9, 10 |
| [vdbe/](vdbe/README.md) | opcodes, registers, dispatch | 5, 6, 10 |
| [functions/](functions/README.md) | function library & registry | 6, 10 |
| [mvcc/](mvcc/README.md) | versions, snapshots, conflicts | 11 |
| [cli/](cli/README.md) | REPL, dot-commands | 12 |

Cross-cutting testing methodology is documented where it lives:
[../tests/differential/README.md](../tests/differential/README.md).
