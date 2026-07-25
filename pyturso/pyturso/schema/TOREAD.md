# TOREAD — schema

Levels refer to [../../READING.md](../../READING.md).

## Before starting

- [ ] SQLite File Format doc, §"Storage Of The SQL Database Schema" — the
      `sqlite_schema` contract, incl. what rootpage means per object type.
- [ ] SQLite docs: [`lang_createtable`](https://sqlite.org/lang_createtable.html)
      — specifically the **ROWIDs and the INTEGER PRIMARY KEY** section;
      this single section prevents the module's worst bug.
- [ ] READING L3: 15-445 system-catalog segment — every engine bootstraps
      its catalog from itself; see the general pattern before the SQLite
      instance of it.

## Prereqs from your own earlier docs

- [ ] `docs/storage/reference/page-and-cell-layout.md` (you read page 1
      with it).
- [ ] `docs/parser/reference/grammar.md` — confirm CREATE TABLE/INDEX
      coverage is green before starting; this module consumes it.

## Rust source

- [ ] `core/schema.rs` — the object model and construction; the rowid-alias
      logic is the part to port verbatim.
- [ ] `core/translate/schema.rs` — how translation consumes schema (read for
      the interface you must serve, not to port yet).

## Docs you will write

`object-model.md` · `rowid-alias-rules.md` ·
`the-schema-is-just-a-table.md` (the bootstrapping explanation — a joy to
write) · `schema-staleness.md` · `trace-a-create-table.md` tutorial.
Status: `docs/schema/README.md`.
