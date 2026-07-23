# docs/api — Doc index

Module: [pyturso/ package root](../../pyturso/README.md) ·
Rust: `core/lib.rs`, `core/connection.rs`, `core/statement.rs`, `core/error.rs`

## Planned documents

### tutorials/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `open-query-close.md` | 5 | planned | the minimal end-to-end user session, then the same thing again with every layer's role annotated |

### how-to/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `use-the-statement-lifecycle-directly.md` | 5 | planned | prepare/step/reset by hand; when you'd want to |

### reference/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `public-api.md` | 5 | planned | Database/Connection/Statement surface, kept small deliberately |
| `error-hierarchy.md` | 5 | planned | exception classes ↔ core/error.rs variants ↔ differential error classes |

### explanation/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `anatomy-of-a-query.md` | 5 | planned | **the capstone doc**: one SELECT traversing every module, with a diagram; grows as phases add layers |
| `who-owns-what.md` | 8 | planned | Database vs Connection vs Statement state; transactions and schema caches |
