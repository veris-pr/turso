"""objects — Schema/Table/Index/Column model, rootpages, rowid-alias flag.

Ports: core/schema.rs (``BTreeTable``, ``Column``, ``ColDef``, ``Index``,
``Schema``, ``IndexColumn``).
Phase: 4
Status: IMPLEMENTED.

The in-memory model materialized from ``sqlite_schema``: tables keyed by name,
each holding column definitions (name, declared type, affinity via
:mod:`pyturso.types.affinity`), root page numbers, and the critical
**rowid-alias flag** (which column, if any, is an ``INTEGER PRIMARY KEY``
alias for the rowid — that column's value is stored as NULL in the record
and served from the cell's rowid varint).

WITHOUT ROWID tables and generated columns are cleanly rejected for now
(the TODO item for clean rejection is next); the object model leaves room.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

from pyturso.types.affinity import Affinity, affinity_from_type_name

__all__ = ["Column", "Table", "IndexColumn", "Index", "Schema"]


class Column(NamedTuple):
    """A column definition. Ports ``core::schema::Column`` + ``ColDef``.

    Fields:
        name: column name (as declared, case preserved).
        declared_type: the type-name string from CREATE TABLE (e.g. "INTEGER",
            "VARCHAR(255)"). Empty string if no type was declared.
        affinity: the resolved affinity (from :mod:`pyturso.types.affinity`).
        primary_key: whether this column is part of a PRIMARY KEY constraint.
        rowid_alias: whether this column is an INTEGER PRIMARY KEY rowid alias.
        not_null: whether this column has a NOT NULL constraint.
        unique: whether this column has a UNIQUE constraint.
        default_expr: the DEFAULT expression (as an AST Expr or None).
        hidden: whether this is a hidden column (not in SELECT *).
    """

    name: str
    declared_type: str
    affinity: Affinity
    primary_key: bool
    rowid_alias: bool
    not_null: bool
    unique: bool
    default_expr: object | None  # Expr or None — kept as object to avoid circular import
    hidden: bool


@dataclass
class Table:
    """A table in the schema. Ports ``core::schema::BTreeTable``.

    Attributes:
        name: table name (as declared, case preserved).
        columns: ordered list of :class:`Column` definitions.
        root_page: the B-tree root page number (1-based).
        rowid_alias_col: index of the rowid-alias column in ``columns``, or
            ``None`` if no INTEGER PRIMARY KEY alias. This is the critical flag:
            that column's value is stored as NULL in the record (serial type 0)
            and must be served from the cell's rowid varint at read time.
        has_rowid: whether the table has a rowid (False for WITHOUT ROWID —
            currently rejected, but the field is here for forward compat).
        has_autoincrement: whether the table has an AUTOINCREMENT column.
    """

    name: str
    columns: list[Column]
    root_page: int
    rowid_alias_col: int | None = None
    has_rowid: bool = True
    has_autoincrement: bool = False

    @property
    def num_columns(self) -> int:
        """Number of columns (ports ``BTreeTable::columns().len()``)."""
        return len(self.columns)

    def column_index(self, name: str) -> int | None:
        """Return the 0-based index of column ``name``, or ``None``.

        SQLite identifiers are case-insensitive (folded to lowercase for
        comparison).
        """
        target = name.lower()
        for i, col in enumerate(self.columns):
            if col.name.lower() == target:
                return i
        return None

    def column_by_name(self, name: str) -> Column | None:
        """Return the :class:`Column` named ``name``, or ``None``."""
        idx = self.column_index(name)
        return self.columns[idx] if idx is not None else None


class IndexColumn(NamedTuple):
    """A column in an index: name + sort order. Ports ``IndexColumn``."""

    name: str
    descending: bool  # True for DESC


@dataclass
class Index:
    """An index in the schema. Ports ``core::schema::Index``.

    Attributes:
        name: index name.
        table_name: the table this index is on.
        columns: ordered list of :class:`IndexColumn` (name + sort order).
        root_page: the B-tree root page number.
        unique: whether this is a UNIQUE index.
        where_clause: the partial-index WHERE expression (AST or None).
    """

    name: str
    table_name: str
    columns: list[IndexColumn]
    root_page: int
    unique: bool = False
    where_clause: object | None = None  # Expr or None


@dataclass
class Schema:
    """The in-memory schema: tables + indexes keyed by name.

    Ports ``core::schema::Schema``. Stores the schema cookie from the
    database header for staleness checking (the ``is_stale()`` seam — full
    wiring deferred to Phase 8).

    Attributes:
        tables: name → :class:`Table` (case-insensitive keys, lowercased).
        indexes: name → :class:`Index` (case-insensitive keys, lowercased).
        schema_cookie: the schema cookie from the header at load time.
    """

    tables: dict[str, Table] = field(default_factory=dict)
    indexes: dict[str, Index] = field(default_factory=dict)
    schema_cookie: int = 0

    def add_table(self, table: Table) -> None:
        """Register a table (keyed by lowercased name)."""
        self.tables[table.name.lower()] = table

    def add_index(self, index: Index) -> None:
        """Register an index (keyed by lowercased name)."""
        self.indexes[index.name.lower()] = index

    def get_table(self, name: str) -> Table | None:
        """Look up a table by name (case-insensitive)."""
        return self.tables.get(name.lower())

    def get_index(self, name: str) -> Index | None:
        """Look up an index by name (case-insensitive)."""
        return self.indexes.get(name.lower())

    def indexes_on(self, table_name: str) -> list[Index]:
        """Return all indexes on the given table."""
        target = table_name.lower()
        return [idx for idx in self.indexes.values()
                if idx.table_name.lower() == target]

    def is_stale(self, current_cookie: int) -> bool:
        """Whether the schema is stale relative to the current header cookie.

        The seam for Phase 8's invalidation wiring: the connection checks this
        on prepare and reloads if stale. For now, a simple cookie comparison.
        """
        return current_cookie != self.schema_cookie


def make_column(
    name: str,
    declared_type: str = "",
    *,
    primary_key: bool = False,
    rowid_alias: bool = False,
    not_null: bool = False,
    unique: bool = False,
    default_expr: object | None = None,
    hidden: bool = False,
) -> Column:
    """Construct a :class:`Column` with affinity resolved from the type name.

    Convenience factory used by :mod:`pyturso.schema.load` when materializing
    from parsed CREATE TABLE AST.
    """
    affinity = affinity_from_type_name(declared_type) if declared_type else Affinity.BLOB
    return Column(
        name=name,
        declared_type=declared_type,
        affinity=affinity,
        primary_key=primary_key,
        rowid_alias=rowid_alias,
        not_null=not_null,
        unique=unique,
        default_expr=default_expr,
        hidden=hidden,
    )