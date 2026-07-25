# docs/vdbe — Doc index

Module: [pyturso/vdbe/](../../pyturso/vdbe/README.md) · Rust: `core/vdbe/` ·
Repo guide: `docs/agent-guides/debugging.md` (bytecode comparison)

## Planned documents

### tutorials/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `single-step-your-first-program.md` | 5 | planned | run a compiled SELECT one opcode at a time, watching registers and cursors |

### how-to/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `trace-an-execution.md` | 5 | planned | enable/read the VM trace; correlate with EXPLAIN addresses |
| `port-an-opcode.md` | 5 | planned | checklist: read execute.rs handler, port, corpus case, catalog entry |

### reference/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `opcode-catalog.md` | 5 | planned | **scope ledger**, updated in the same commit as insn/execute changes: operands, semantics, Rust link, corpus coverage |
| `program-format.md` | 5 | planned | Program structure, EXPLAIN listing format |

### explanation/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `vdbe-as-a-tiny-cpu.md` | 5 | planned | registers, cursors, pc; why a bytecode VM instead of tree-walking |
| `resumable-step.md` | 5 | planned | how step() suspends on I/O and re-enters; ties to the io keystone doc |
| `sorting-without-memory.md` | 10 | planned | the sorter: external sort as a cursor |
