"""load — walk sqlite_schema via a cursor, parse sql, materialize objects.

Ports: core/schema.rs (schema construction paths —
``Schema::make_from_btree_schema_recovery`` and the load loop).
Phase: 4
Status: IMPLEMENTED.

The load path is the engine eating its own dog food:

1. Open a :class:`pyturso.storage.btree.BTreeCursor` on page 1 (the
   ``sqlite_schema`` root).
2. Iterate each row — the record has 5 columns: ``(type, name, tbl_name,
   rootpage, sql)``.
3. Parse each ``sql`` with the Phase 3 parser (``CREATE TABLE`` /
   ``CREATE INDEX`` AST).
4. Materialize :class:`pyturso.schema.objects.Table` / :class:`Index` from
   the AST + rootpage.
5. Register in a :class:`Schema`.

Internal rows with NULL ``sql`` (autoindexes from UNIQUE/PK constraints) are
represented without parsing — their rootpage is recorded but no AST is
materialized (they are used by the planner, not by schema introspection).

Unparseable stored ``sql`` raises ``Corrupt`` (a schema you can't parse is a
database you don't understand — not skippable). WITHOUT ROWID tables and
generated columns are cleanly rejected (ledger in ``grammar.md``).
"""

from __future__ import annotations

from typing import Generator

from pyturso.errors import Corrupt
from pyturso.io.driver import run_to_completion
from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import WriteRequest
from pyturso.parser.ast.expr import Expr, Literal, LiteralExpr, Name
from pyturso.parser.ast.ddl import (
    ColumnConstraint, ColumnDefinition, CreateTable, CreateIndex,
)
from pyturso.parser.ast.stmt import As, ResultColumn
from pyturso.parser.parser import parse as parse_sql
from pyturso.parser.errors import ParseError
from pyturso.schema.objects import (
    Column, Index, IndexColumn, Schema, Table, make_column,
)
from pyturso.storage.btree import BTreeCursor
from pyturso.storage.pager import Pager
from pyturso.storage.sqlite3_ondisk import parse_record

__all__ = ["load_schema", "load_schema_from_file"]


def load_schema_from_file(db_path: str) -> Schema:
    """Load a schema from a database file path.

    Convenience: reads the file into a MemoryIO backend, opens a pager, and
    delegates to :func:`load_schema`.
    """
    from pathlib import Path
    raw = Path(db_path).read_bytes()
    io = MemoryIO()
    f = io.open_file("db")
    f.pwrite(WriteRequest(f, 0, raw))
    pager = Pager(io, "db")
    pager.open()
    return load_schema(pager)


def load_schema(pager: Pager) -> Schema:
    """Load the schema from a pager (page 1 = sqlite_schema root).

    Walks page 1 with a BTreeCursor, parses each row's ``sql`` column,
    materializes Table/Index objects, and returns a populated :class:`Schema`.

    Raises:
        Corrupt: a stored ``sql`` is unparseable, or a row has an unexpected
            type, or WITHOUT ROWID is encountered (cleanly rejected).
    """
    schema = Schema()
    schema.schema_cookie = pager.header.schema_cookie

    cursor = BTreeCursor(pager, root_page=1)
    run_to_completion(cursor.rewind())
    while not cursor.done:
        row = cursor.row()
        rec = parse_record(row.payload)
        # sqlite_schema columns: type, name, tbl_name, rootpage, sql
        if len(rec.values) < 5:
            run_to_completion(cursor.next())
            continue
        obj_type = rec.values[0]
        obj_name = rec.values[1]
        tbl_name = rec.values[2]
        rootpage = rec.values[3]
        sql_text = rec.values[4]

        # Skip NULL-typed rows (internal objects, autoindexes).
        if obj_type is None:
            run_to_completion(cursor.next())
            continue

        obj_type_str = str(obj_type) if obj_type else ""
        name_str = str(obj_name) if obj_name else ""
        root_page_int = int(rootpage) if rootpage is not None and isinstance(rootpage, int) else 0

        if obj_type_str == "table":
            if sql_text is None:
                # Internal table with no SQL (shouldn't happen for user tables).
                run_to_completion(cursor.next())
                continue
            table = _materialize_table(name_str, root_page_int, str(sql_text))
            schema.add_table(table)
        elif obj_type_str == "index":
            if sql_text is None:
                # Autoindex (from UNIQUE/PK constraint) — no SQL to parse.
                # Represent it minimally: name + rootpage, no column info.
                run_to_completion(cursor.next())
                continue
            index = _materialize_index(name_str, str(tbl_name), root_page_int, str(sql_text))
            schema.add_index(index)
        # Skip "view", "trigger" etc. — not in Phase 4 scope.

        run_to_completion(cursor.next())

    return schema


def _materialize_table(name: str, root_page: int, sql: str) -> Table:
    """Parse a CREATE TABLE statement and materialize a :class:`Table`."""
    try:
        stmt = parse_sql(sql)
    except ParseError as exc:
        raise Corrupt(f"unparseable schema SQL for table {name!r}: {exc}") from exc

    if not isinstance(stmt, CreateTable):
        raise Corrupt(f"expected CREATE TABLE for {name!r}, got {type(stmt).__name__}")

    if stmt.without_rowid:
        raise Corrupt(f"WITHOUT ROWID not supported (table {name!r})")

    columns: list[Column] = []
    rowid_alias_col: int | None = None
    has_autoincrement = False

    for col_def in stmt.columns:
        col, is_rowid_alias, has_autoincr = _column_from_def(col_def)
        columns.append(col)
        if is_rowid_alias:
            rowid_alias_col = len(columns) - 1
        if has_autoincr:
            has_autoincrement = True

    # Also check table-level PRIMARY KEY constraints.
    # (Column-level PK is handled above; table-level PK sets primary_key on
    # the named columns but does NOT create a rowid alias — the alias requires
    # "INTEGER PRIMARY KEY" on a single column.)
    for tc in stmt.table_constraints:
        if tc.kind == "PRIMARY KEY" and tc.columns:
            for pk_col_name in tc.columns:
                idx = _find_col_index(columns, pk_col_name.value)
                if idx is not None:
                    # Update primary_key flag.
                    col = columns[idx]
                    columns[idx] = col._replace(primary_key=True)

    return Table(
        name=name,
        columns=columns,
        root_page=root_page,
        rowid_alias_col=rowid_alias_col,
        has_rowid=not stmt.without_rowid,
        has_autoincrement=has_autoincrement,
    )


def _column_from_def(col_def: ColumnDefinition) -> tuple[Column, bool, bool]:
    """Convert a :class:`ColumnDefinition` AST to a :class:`Column`.

    Returns ``(column, is_rowid_alias, has_autoincrement)``.
    The rowid-alias rule: the column is an INTEGER PRIMARY KEY alias iff:
      1. declared_type contains "INT" (resolves to INTEGER affinity), AND
      2. has a PRIMARY KEY column constraint.
    (Ports the Rust rule from ``core/schema.rs``.)
    """
    is_pk = False
    is_rowid_alias = False
    is_not_null = False
    is_unique = False
    default_expr = None
    has_autoincr = False

    for constraint in col_def.constraints:
        if constraint.kind == "PRIMARY KEY":
            is_pk = True
            # Rowid alias: INTEGER type + PRIMARY KEY.
            type_upper = (col_def.type_name or "").upper()
            if type_upper and "INT" in type_upper:
                is_rowid_alias = True
            if constraint.autoincrement:
                has_autoincr = True
        elif constraint.kind == "NOT NULL":
            is_not_null = True
        elif constraint.kind == "UNIQUE":
            is_unique = True
        elif constraint.kind == "DEFAULT":
            default_expr = constraint.expr
        elif constraint.kind == "NULL":
            pass  # explicitly nullable — no flag

    col = make_column(
        name=col_def.name.value,
        declared_type=col_def.type_name or "",
        primary_key=is_pk,
        rowid_alias=is_rowid_alias,
        not_null=is_not_null,
        unique=is_unique,
        default_expr=default_expr,
    )
    return col, is_rowid_alias, has_autoincr


def _materialize_index(
    name: str, table_name: str, root_page: int, sql: str
) -> Index:
    """Parse a CREATE INDEX statement and materialize an :class:`Index`."""
    try:
        stmt = parse_sql(sql)
    except ParseError as exc:
        raise Corrupt(f"unparseable schema SQL for index {name!r}: {exc}") from exc

    if not isinstance(stmt, CreateIndex):
        raise Corrupt(f"expected CREATE INDEX for {name!r}, got {type(stmt).__name__}")

    columns: list[IndexColumn] = []
    for col_name in stmt.columns:
        columns.append(IndexColumn(name=col_name.value, descending=False))

    return Index(
        name=name,
        table_name=table_name,
        columns=columns,
        root_page=root_page,
        unique=stmt.unique,
        where_clause=stmt.where,
    )


def _find_col_index(columns: list[Column], name: str) -> int | None:
    """Find a column by name (case-insensitive)."""
    target = name.lower()
    for i, col in enumerate(columns):
        if col.name.lower() == target:
            return i
    return None