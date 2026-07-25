# docs/functions — Doc index

Module: [pyturso/functions/](../../pyturso/functions/README.md) ·
Rust: `core/functions/`, `core/function.rs`

## Planned documents

### tutorials/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `add-a-scalar-function.md` | 6 | planned | implement one function end to end and prove parity with corpus cases |

### how-to/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `hunt-a-function-divergence.md` | 6 | planned | three-way disagreement triage: whose behavior is right, and where in the Rust to look |

### reference/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `function-catalog.md` | 6 | planned | **scope ledger**: every SQL function — supported/planned(phase)/out-of-scope, corpus coverage, Rust file link |
| `null-semantics.md` | 6 | planned | NULL propagation per operator and function; the exceptions (coalesce, count, IS) |
| `datetime-formats.md` | 6 | planned | accepted formats, modifiers, strftime specifiers |

### explanation/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `three-valued-logic.md` | 6 | planned | TRUE/FALSE/NULL through WHERE, AND/OR short-circuit, and the VM's jump-if opcodes |
| `scalar-vs-aggregate.md` | 10 | planned | two calling conventions; step/finalize; why max is two different functions |
