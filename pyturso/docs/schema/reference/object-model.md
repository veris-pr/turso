# Schema object model — reference

**Status:** current · **Phase:** 4 · **Cites:** `pyturso/schema/objects.py`;
Rust: `core/schema.rs` (`BTreeTable`, `Column`, `ColDef`, `Index`, `Schema`).

## Objects

### `Column`
A column definition in a table. NamedTuple (immutable).

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Column name (case preserved) |
| `declared_type` | `str` | Type-name string from CREATE TABLE (e.g. "INTEGER") |
| `affinity` | `Affinity` | Resolved affinity (via `types.affinity`) |
| `primary_key` | `bool` | Part of a PRIMARY KEY constraint |
| `rowid_alias` | `bool` | INTEGER PRIMARY KEY rowid alias |
| `not_null` | `bool` | NOT NULL constraint |
| `unique` | `bool` | UNIQUE constraint |
| `default_expr` | `Expr \| None` | DEFAULT expression AST |
| `hidden` | `bool` | Hidden column (not in SELECT *) |

### `Table`
A table in the schema. Dataclass.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Table name (case preserved) |
| `columns` | `list[Column]` | Ordered column definitions |
| `root_page` | `int` | B-tree root page number (1-based) |
| `rowid_alias_col` | `int \| None` | Index of the rowid-alias column, or None |
| `has_rowid` | `bool` | Whether the table has a rowid |
| `has_autoincrement` | `bool` | Whether AUTOINCREMENT is present |

### `Index`
An index in the schema. Dataclass.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Index name |
| `table_name` | `str` | Table this index is on |
| `columns` | `list[IndexColumn]` | Ordered index columns (name + descending) |
| `root_page` | `int` | B-tree root page number |
| `unique` | `bool` | UNIQUE index |
| `where_clause` | `Expr \| None` | Partial-index WHERE expression |

### `Schema`
The in-memory schema: tables + indexes keyed by name. Dataclass.

| Field | Type | Description |
|---|---|---|
| `tables` | `dict[str, Table]` | Lowercased name → Table |
| `indexes` | `dict[str, Index]` | Lowercased name → Index |
| `schema_cookie` | `int` | Schema cookie from the header at load time |

## Case-insensitivity
All lookups (`get_table`, `get_index`, `column_index`) are case-insensitive —
SQLite identifiers are case-folded. Keys in the dicts are lowercased.

## Staleness
`Schema.is_stale(current_cookie)` compares the stored cookie with the header's
current cookie. Full invalidation wiring is deferred to Phase 8 (transactions).