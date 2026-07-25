"""planner — AST → plan: name resolution, column binding, star expansion, validation.

Ports: core/translate/planner.rs.
Phase: 5
Status: IMPLEMENTED (Phase 5 subset: single-table SELECT, column binding,
star expansion, WHERE terms, ORDER BY, LIMIT/OFFSET).

The planner resolves names against the schema: finds the table, binds column
references to physical column indices, expands ``*`` into the full column
list, and validates. All "no such table/column" errors originate here, never
in the emitter. The rowid-alias column is handled: if a column ref points to
the INTEGER PRIMARY KEY alias, its ``col_index`` is still the record position,
but the emitter uses ``Rowid`` instead of ``Column`` for it.
"""

from __future__ import annotations

from pyturso.errors import NotSupported, TursoError
from pyturso.parser.ast.expr import (
    BinaryExpr, Expr, IdExpr, Literal, LiteralExpr, QualifiedExpr,
)
from pyturso.parser.ast.stmt import (
    ResultColumn, Select, SelectBody, SortedColumn,
)
from pyturso.schema.objects import Schema, Table
from pyturso.translate.plan import Plan, ResultSetColumn, SourceTable, WhereTerm

__all__ = ["plan_select"]


def plan_select(ast: Select, schema: Schema) -> Plan:
    """Build a :class:`Plan` from a parsed SELECT AST.

    Raises:
        TursoError: no such table, no such column, or unsupported construct.
    """
    one = ast.body.select

    # --- FROM clause ---
    source: SourceTable | None = None
    if one.from_clause is not None and one.from_clause.table is not None:
        st = one.from_clause.table
        tname = st.alias.value if st.alias else (st.name.value if st.name else "")
        if not tname:
            raise TursoError("no table name in FROM clause")
        # Resolve the table via schema (look up by alias first, then name).
        real_name = st.name.value if st.name else ""
        table = schema.get_table(real_name)
        if table is None:
            raise TursoError(f"no such table: {real_name}")
        source = SourceTable(table=table, alias=tname)

    if source is None:
        raise NotSupported("SELECT without FROM (scalar queries) — not yet supported")

    # --- result columns (expand *) ---
    result_columns: list[ResultSetColumn] = []
    for rc in one.columns:
        if rc.star:
            # Expand to all columns of the source table.
            for i, col in enumerate(source.table.columns):
                result_columns.append(ResultSetColumn(
                    expr=None, name=col.name, col_index=i,
                ))
        elif rc.table_star:
            raise NotSupported("table.* expansion — not yet supported")
        else:
            assert rc.expr is not None
            col_index = _resolve_column_index(rc.expr, source)
            name = rc.alias.name.value if rc.alias else _derive_column_name(rc.expr)
            result_columns.append(ResultSetColumn(
                expr=rc.expr, name=name, col_index=col_index,
            ))

    # --- WHERE terms ---
    where_terms: list[WhereTerm] = []
    if one.where is not None:
        where_terms.append(WhereTerm(expr=one.where))

    # --- LIMIT/OFFSET ---
    limit_expr = None
    offset_expr = None
    if ast.limit is not None:
        limit_expr = ast.limit.count
        offset_expr = ast.limit.offset

    return Plan(
        source=source,
        where_terms=where_terms,
        result_columns=result_columns,
        order_by=ast.order_by,
        limit=limit_expr,
        offset=offset_expr,
        distinct=one.distinctness is not None,
    )


def _resolve_column_index(expr: Expr, source: SourceTable) -> int:
    """Resolve an expression to a column index if it's a simple column ref.

    Returns -1 for non-column expressions (literals, function calls, etc.).
    The emitter handles -1 by compiling the expression.
    """
    if isinstance(expr, IdExpr):
        idx = source.table.column_index(expr.name.value)
        if idx is None:
            raise TursoError(f"no such column: {expr.name.value}")
        return idx
    if isinstance(expr, QualifiedExpr):
        # table.col — verify the table name matches.
        if expr.table.value.lower() != source.alias.lower() and \
           expr.table.value.lower() != source.table.name.lower():
            raise TursoError(f"no such table: {expr.table.value}")
        idx = source.table.column_index(expr.column.value)
        if idx is None:
            raise TursoError(f"no such column: {expr.column.value}")
        return idx
    return -1  # expression, not a simple column ref


def _derive_column_name(expr: Expr) -> str:
    """Derive a default output column name from an expression."""
    if isinstance(expr, IdExpr):
        return expr.name.value
    if isinstance(expr, QualifiedExpr):
        return expr.column.value
    if isinstance(expr, LiteralExpr):
        return str(expr.value) if expr.value else expr.literal.value
    return ""  # unnamed expression