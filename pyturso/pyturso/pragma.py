"""pragma — PRAGMA subset for Phase 10+.

Ports: core/pragma.rs.
Phase: 10+
Status: IMPLEMENTED (read-only subset: table_info, index_list, page_count,
journal_mode, schema_version).

PRAGMAs are special SQL commands that inspect or control database settings.
pyturso implements a small read-only subset — these are useful for the CLI
and the differential harness.
"""

from __future__ import annotations

from pyturso.schema.objects import Schema
from pyturso.storage.pager import Pager
from pyturso.types.value import Value

__all__ = ["execute_pragma"]


def execute_pragma(name: str, arg: str, schema: Schema, pager: Pager) -> list[tuple[Value, ...]]:
    """Execute a read-only PRAGMA.

    Returns result rows (like a SELECT). Write pragmas are not supported.
    """
    name_lower = name.lower()

    if name_lower == "table_info":
        return _pragma_table_info(schema, arg)
    if name_lower == "index_list":
        return _pragma_index_list(schema, arg)
    if name_lower == "page_count":
        return [(Value.integer(pager.num_pages),)]
    if name_lower == "journal_mode":
        return [(Value.text("memory"),)]  # pyturso uses in-memory by default
    if name_lower == "schema_version":
        return [(Value.integer(schema.schema_cookie),)]
    if name_lower == "user_version":
        return [(Value.integer(0),)]
    if name_lower == "application_id":
        return [(Value.integer(0),)]

    # Unknown pragma — return empty (SQLite convention).
    return []


def _pragma_table_info(schema: Schema, table_name: str) -> list[tuple[Value, ...]]:
    """PRAGMA table_info(t) — one row per column.

    Columns: cid, name, type, notnull, dflt_value, pk
    """
    table = schema.get_table(table_name)
    if table is None:
        return []
    rows: list[tuple[Value, ...]] = []
    for i, col in enumerate(table.columns):
        dflt = Value.null()
        if col.default_expr is not None:
            from pyturso.parser.ast.expr import LiteralExpr, Literal
            if isinstance(col.default_expr, LiteralExpr):
                dflt = Value.text(col.default_expr.value)
        rows.append((
            Value.integer(i),       # cid
            Value.text(col.name),    # name
            Value.text(col.declared_type),  # type
            Value.integer(1 if col.not_null else 0),  # notnull
            dflt,                     # dflt_value
            Value.integer(1 if col.primary_key else 0),  # pk
        ))
    return rows


def _pragma_index_list(schema: Schema, table_name: str) -> list[tuple[Value, ...]]:
    """PRAGMA index_list(t) — one row per index.

    Columns: seq, name, unique, origin, partial
    """
    indexes = schema.indexes_on(table_name)
    rows: list[tuple[Value, ...]] = []
    for i, idx in enumerate(indexes):
        rows.append((
            Value.integer(i),          # seq
            Value.text(idx.name),      # name
            Value.integer(1 if idx.unique else 0),  # unique
            Value.text("c"),           # origin (created by CREATE INDEX)
            Value.integer(1 if idx.where_clause is not None else 0),  # partial
        ))
    return rows