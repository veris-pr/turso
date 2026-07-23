# docs/parser — Doc index

Module: [pyturso/parser/](../../pyturso/parser/README.md) ·
Rust: `sqlite/parser/src/`

## Planned documents

### tutorials/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `from-sql-text-to-ast.md` | 3 | planned | tokenize and parse one SELECT by hand alongside the code |

### how-to/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `add-a-statement-type.md` | 3 | planned | token→AST→parser checklist, with snapshot tests |
| `debug-a-misparse.md` | 3 | planned | token stream dump, entry-point tracing, comparing against the Rust parser's path |

### reference/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `grammar.md` | 3 | planned | **scope ledger**: every construct supported/planned(phase)/out-of-scope |
| `ast-nodes.md` | 3 | planned | node catalog with Rust enum counterparts |
| `tokens-and-literals.md` | 3 | planned | token kinds, keyword table, quoting, literal forms |
| `operator-precedence.md` | 3 | planned | precedence/associativity table incl. COLLATE and unary edge cases |

### explanation/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `why-recursive-descent.md` | 3 | planned | vs generated parsers (which Turso migrated away from); error recovery; context-sensitive keywords |
