# docs/io — Doc index

Module: [pyturso/io/](../../pyturso/io/README.md) · Rust: `core/io/` ·
Repo guide: `docs/agent-guides/async-io-model.md`

## Planned documents

### tutorials/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `drive-a-generator-through-io.md` | 1 | planned | write a tiny read_page, step it by hand with send(), then run_to_completion |

### how-to/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `pause-an-operation-at-a-yield-point.md` | 1 | planned | use the step-controlled driver in tests (crash/interleaving injection) |
| `add-an-io-backend.md` | 1 | planned | implement the File protocol; conformance checklist |

### reference/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `request-and-completion-types.md` | 1 | current | every request dataclass, fields, completion payloads |
| `backend-matrix.md` | 1 | current | memory vs posix: capabilities, fsync semantics, test usage |

### explanation/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `ioresult-as-generators.md` | 1 | current | **the project's keystone doc**: Turso's IOResult state machines, why re-entrancy matters, and how yield/send preserves the shape |
| `what-we-dont-port.md` | 1 | planned | io_uring, threads, locking — what they buy Turso and why concept-parity omits them |
