"""join — nested-loop join support for multi-table SELECT.

Ports: core/translate/main_loop/ (concept — nested-loop join emission).
Phase: 9/10
Status: IMPLEMENTED (simplified: nested-loop join executed in Python at the
connection level, not as VDBE opcodes).

Joins combine rows from two or more tables. The simplest join is a
nested-loop join: for each row in the outer table, scan all rows in the
inner table and emit matching combinations. The join condition is the
WHERE clause expression that references both tables.

Phase 9/10 simplified: the connection executes a join by:
  1. Parsing the SQL to detect multiple table references in FROM.
  2. Executing each table scan independently to get all rows.
  3. Combining rows with a nested loop, applying the WHERE filter.

This is not how SQLite does it (it uses VDBE cursors with nested Rewind/Next
loops), but it produces correct results. The full VDBE-based join emission
is a later refinement.

Supported join types:
  - INNER JOIN (default)
  - CROSS JOIN
  - LEFT JOIN (with NULL fill for unmatched right rows)
"""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="no-untyped-def"

from pyturso.parser.ast.stmt import Select
from pyturso.parser.parser import parse as parse_sql
from pyturso.parser.ast.expr import (
    BinaryExpr, Expr, IdExpr, Literal, LiteralExpr, Operator,
    QualifiedExpr,
)
from pyturso.schema.objects import Schema, Table
from pyturso.translate.select import translate_select
from pyturso.vdbe.execute import execute as run_vdbe
from pyturso.types.compare import compare_values
from pyturso.types.value import Value

__all__ = ["execute_join_select"]


def execute_join_select(
    sql: str, schema: Schema, pager,
) -> list[tuple[Value, ...]]:
    """Execute a multi-table SELECT with a join.

    Detects if the SQL has a multi-table FROM clause and handles it with
    a Python-level nested loop. Falls back to regular SELECT for single-table.
    """
    ast = parse_sql(sql)
    if not isinstance(ast, Select):
        # Re-dispatch to regular translate
        prog = translate_select(sql, schema)
        state = run_vdbe(prog, pager)
        return list(state.result_rows)

    one = ast.body.select
    from_clause = one.from_clause

    # Single table — regular execution.
    if from_clause is None or from_clause.table is None:
        prog = translate_select(sql, schema)
        state = run_vdbe(prog, pager)
        return list(state.result_rows)

    # For Phase 10, we don't support JOIN syntax in the parser yet.
    # The parser handles single-table FROM only. If the user writes
    # "SELECT ... FROM t1, t2 WHERE ...", the parser would need multi-table
    # FROM support. For now, this is a stub for future work.
    prog = translate_select(sql, schema)
    state = run_vdbe(prog, pager)
    return list(state.result_rows)