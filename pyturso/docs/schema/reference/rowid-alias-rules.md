# Rowid alias rules — reference

**Status:** current · **Phase:** 4 · **Cites:** `pyturso/schema/load.py`,
`pyturso/schema/objects.py`; Rust: `core/schema.rs`.

## The rule

A column is a **rowid alias** iff:

1. Its declared type contains `INT` (resolves to `INTEGER` affinity), **AND**
2. It has a column-level `PRIMARY KEY` constraint.

When a column is a rowid alias:
- Its value is **stored as NULL** in the record (serial type 0).
- The actual value is the cell's **rowid varint**.
- At read time, the engine must substitute the rowid for the NULL record value.

This is the classic parity trap: if the engine reads the record literally
(without substituting the rowid), the PRIMARY KEY column appears as NULL.

## What is NOT a rowid alias

| Pattern | Rowid alias? | Reason |
|---|---|---|
| `id INTEGER PRIMARY KEY` | ✅ | INT type + PK |
| `id INTEGER PRIMARY KEY AUTOINCREMENT` | ✅ | Same, with autoincrement |
| `id INT PRIMARY KEY` | ✅ | "INT" contains "INT" → INTEGER affinity |
| `id PRIMARY KEY` | ❌ | No declared type → BLOB affinity |
| `id TEXT PRIMARY KEY` | ❌ | TEXT affinity, not INTEGER |
| `id REAL PRIMARY KEY` | ❌ | REAL affinity, not INTEGER |
| `PRIMARY KEY (id)` (table-level) | ❌ | Table-level PK does not create an alias |
| `id BIGINT PRIMARY KEY` | ✅ | "BIGINT" contains "INT" |

## Table-level PRIMARY KEY

A table-level `PRIMARY KEY (col)` constraint sets the `primary_key` flag on
the named column(s) but does **NOT** create a rowid alias. Only column-level
`INTEGER PRIMARY KEY` creates the alias. This is a deliberate SQLite design:
table-level PK on a single INTEGER column behaves the same as column-level
PK (it IS an alias), but the Rust code checks the constraint position, not
just the type — pyturso mirrors this.