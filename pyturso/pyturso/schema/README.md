# pyturso.schema — Schema objects

**Ports:** `core/schema.rs`, plus `core/translate/schema.rs` interplay
**Phase:** 4

## What this module is

The bridge between "the database file" and "the SQL compiler": an in-memory
model of tables, indexes, columns, and root pages, materialized from the
`sqlite_schema` table.

The load path is a beautiful demonstration of the engine eating its own dog
food, and it is why this module needs Phases 1 *and* 3 first:

```
page 1 ──(storage.btree cursor)──► rows of sqlite_schema
  each row: (type, name, tbl_name, rootpage, sql)
        │                            │
        │                            └─(parser)── CREATE TABLE/INDEX AST
        ▼
  Table / Index / Column objects, keyed by name, holding rootpage numbers
```

The schema *is a table*, read with the same B-tree cursor as user data, and
its `sql` column is re-parsed with the same parser as user queries.

## Planned files

| File | Ports | Notes |
|------|-------|-------|
| `objects.py` | `core/schema.rs` types | `Schema`, `Table`, `Index`, `Column`, affinity per column |
| `load.py` | schema construction paths | walk `sqlite_schema` via a cursor, parse `sql`, materialize |

## Key concepts to port

- **Rowid alias detection**: `INTEGER PRIMARY KEY` makes the column an alias
  for the rowid — changes both storage (value stored as NULL in the record)
  and translation. Classic parity trap; corpus cases required.
- **Root pages move**: schema objects hold `rootpage`, and later phases
  (vacuum, balance on page 1) may relocate trees — schema must be a cache
  with an invalidation story (schema cookie / `schema_version`), mirrored
  from how `Connection` checks staleness in Rust.
- **WITHOUT ROWID and generated columns**: representation decided when their
  phases arrive; the object model leaves room, the ledger records the status.

## Docs

Diátaxis tree: [../../docs/schema/README.md](../../docs/schema/README.md)
