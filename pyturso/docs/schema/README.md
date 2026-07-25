# docs/schema — Doc index

Module: [pyturso/schema/](../../pyturso/schema/README.md) · Rust: `core/schema.rs`

## Planned documents

### tutorials/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `trace-a-create-table.md` | 4 | planned | from CREATE TABLE text to rows in page 1 to a Table object |

### how-to/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `compare-schema-against-sqlite3.md` | 4 | planned | assert object model vs PRAGMA table_info / sqlite_schema queries |

### reference/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `object-model.md` | 4 | planned | Schema/Table/Index/Column fields and invariants |
| `rowid-alias-rules.md` | 4 | planned | exactly when INTEGER PRIMARY KEY aliases rowid, and the storage consequence |

### explanation/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `the-schema-is-just-a-table.md` | 4 | planned | bootstrapping: the engine reads its own catalog with its own cursor and parser |
| `schema-staleness.md` | 4 | planned | schema cookie, when caches invalidate, what Turso's Connection checks |
