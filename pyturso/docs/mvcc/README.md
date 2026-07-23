# docs/mvcc — Doc index

Module: [pyturso/mvcc/](../../pyturso/mvcc/README.md) · Rust: `core/mvcc/` ·
Repo guide: `docs/agent-guides/mvcc.md`

## Planned documents

### tutorials/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `two-transactions-one-row.md` | 11 | planned | script an interleaving with the cooperative scheduler; watch versions and visibility |

### how-to/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `reproduce-a-write-write-conflict.md` | 11 | planned | minimal conflict scenario; compare outcome with turso's mvcc_repl |
| `script-an-interleaving.md` | 11 | planned | the scheduler DSL; pinning yield points |

### reference/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `visibility-rules.md` | 11 | planned | the snapshot predicate, precisely, with truth-table examples |
| `scenario-catalog.md` | 11 | planned | ported mvcc_repl scenarios and their expected outcomes; deviations flagged |

### explanation/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `snapshot-isolation-concretely.md` | 11 | planned | versions instead of locks; what anomalies remain; how commit decides winners |
| `mechanism-we-dont-port.md` | 11 | planned | what the Rust does for real concurrency (and the experimental limitations list) that the concept port abstracts away |
