# HOWTO — schema

What the module is: [README.md](README.md). Phase 4. Prerequisites: Phase 1
(cursor over page 1) and Phase 3 (parse CREATE statements).

## Work order

1. **`objects.py`** — read `core/schema.rs` for the shapes, then define
   `Schema`, `Table`, `Column`, `Index` as plain dataclasses: names, column
   affinities (via `types.affinity`), rootpage numbers, index column lists +
   collations/order, and the **rowid-alias flag**.
2. **`load.py`** — open a `BTreeCursor` on page 1, iterate `sqlite_schema`
   rows `(type, name, tbl_name, rootpage, sql)`, parse each `sql` with the
   Phase 3 parser, materialize objects. Handle: internal objects with NULL
   `sql` (autoindexes) — represent, don't choke.
3. **Rowid alias** — port the exact rule from the Rust (INTEGER PRIMARY KEY,
   spelled how, in which constraint positions). Wrong flag here silently
   corrupts Phase 5 column reads (aliased column is stored as NULL in the
   record and must be served from the rowid) — write the unit tests before
   the code.
4. **Staleness hook** — store the schema cookie from the header; expose
   `is_stale()`. Full invalidation wiring waits for Phase 8's transactions;
   leave the seam, document it in `docs/schema/explanation/schema-staleness.md`.

## Verify

- Fixtures with: quoted identifiers, mixed-case names, multi-column indexes
  with DESC, INTEGER PRIMARY KEY in several spellings, autoindexes.
- Cross-check against sqlite3: `PRAGMA table_info(t)`, `PRAGMA index_list(t)`,
  and raw `SELECT * FROM sqlite_schema` — pyturso's objects must agree
  field-for-field on the covered attributes.

## Rules

Parse errors on stored `sql` are fatal (`Corrupt`-class), not skippable — a
schema you can't parse is a database you don't understand. WITHOUT ROWID and
generated columns: reject cleanly, ledger them, revisit per PLAN.md.
