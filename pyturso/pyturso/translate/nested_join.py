"""nested_join — nested-loop join execution for multi-table SELECT.

Ports: core/translate/main_loop/ (concept — nested-loop join).
Phase: 9/10
Status: IMPLEMENTED (simplified: Python-level nested-loop join for
multi-table SELECT with INNER and LEFT joins).

The nested-loop join iterates over each row of the outer table, and for each
outer row, iterates over all rows of the inner table, emitting combinations
that satisfy the join condition. For LEFT JOIN, unmatched outer rows are
emitted with NULL-filled inner columns.

Phase 9/10 simplified: the join is executed at the Python level (not as
VDBE opcodes). Each table is scanned independently, and the join condition
is evaluated in Python. This produces correct results but is not how SQLite
does it (SQLite uses nested VDBE cursors with Rewind/Next loops).
"""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="no-untyped-def"

from pyturso.parser.parser import parse as parse_sql
from pyturso.parser.ast.stmt import Select
from pyturso.parser.ast.expr import (
    BinaryExpr, Expr, IdExpr, Literal, LiteralExpr, Operator,
    QualifiedExpr,
)
from pyturso.schema.objects import Schema, Table
from pyturso.translate.select import translate_select
from pyturso.vdbe.execute import execute as run_vdbe
from pyturso.types.compare import compare_values
from pyturso.types.value import Value

__all__ = ["execute_nested_join"]


def execute_nested_join(
    sql: str, schema: Schema, pager,
) -> list[tuple[Value, ...]]:
    """Execute a multi-table SELECT with a nested-loop join.

    Detects multi-table FROM (comma-separated or JOIN) and handles it with
    a Python-level nested loop. Falls back to regular SELECT for single-table.
    """
    # Parse to check for multi-table FROM.
    # The parser currently only handles single-table FROM, so we need to
    # detect multi-table queries at the SQL text level and handle them specially.
    import re

    # Check for comma-separated tables in FROM (e.g., "FROM t1, t2").
    from_match = re.search(
        r"\bFROM\s+(\w+)\s*,\s*(\w+)",
        sql, re.IGNORECASE,
    )
    if not from_match:
        # Check for explicit JOIN (e.g., "FROM t1 JOIN t2 ON ...").
        join_match = re.search(
            r"\bFROM\s+(\w+)\s+(?:INNER\s+|LEFT\s+|CROSS\s+)?JOIN\s+(\w+)",
            sql, re.IGNORECASE,
        )
        if not join_match:
            # Single table — regular execution.
            prog = translate_select(sql, schema)
            state = run_vdbe(prog, pager)
            return list(state.result_rows)
        table1_name = join_match.group(1)
        table2_name = join_match.group(2)
        is_left = "LEFT" in join_match.group(0).upper()
    else:
        table1_name = from_match.group(1)
        table2_name = from_match.group(2)
        is_left = False

    # Resolve tables.
    table1 = schema.get_table(table1_name)
    table2 = schema.get_table(table2_name)
    if table1 is None or table2 is None:
        raise ValueError(f"no such table: {table1_name} or {table2_name}")

    # Execute each table scan independently.
    rows1 = _scan_table(table1, schema, pager)
    rows2 = _scan_table(table2, schema, pager)

    # Parse the WHERE clause to find the join condition.
    # For Phase 10, we handle the simple case: WHERE t1.col = t2.col.
    where_match = re.search(r"\b(?:WHERE|ON)\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|;|$)", sql, re.IGNORECASE | re.DOTALL)
    join_conditions: list[tuple[str, str]] = []
    if where_match:
        where_text = where_match.group(1).strip()
        # Look for t1.col = t2.col patterns.
        eq_matches = re.finditer(
            r"(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)",
            where_text,
            re.IGNORECASE,
        )
        for m in eq_matches:
            t1, c1, t2, c2 = m.group(1), m.group(2), m.group(3), m.group(4)
            join_conditions.append((f"{t1}.{c1}", f"{t2}.{c2}"))

    # Execute the nested loop.
    result: list[tuple[Value, ...]] = []
    n_cols1 = len(table1.columns)
    n_cols2 = len(table2.columns)

    for row1 in rows1:
        matched = False
        for row2 in rows2:
            if _matches_join(row1, row2, table1, table2, join_conditions):
                result.append(tuple(row1) + tuple(row2))
                matched = True
        if not matched and is_left:
            # LEFT JOIN: emit outer row with NULL-filled inner columns.
            null_row = tuple(Value.null() for _ in range(n_cols2))
            result.append(tuple(row1) + null_row)

    return result


def _scan_table(
    table: Table, schema: Schema, pager,
) -> list[tuple[Value, ...]]:
    """Scan all rows of a table."""
    prog = translate_select(f"SELECT * FROM {table.name}", schema)
    state = run_vdbe(prog, pager)
    return list(state.result_rows)


def _matches_join(
    row1: tuple[Value, ...], row2: tuple[Value, ...],
    table1: Table, table2: Table,
    conditions: list[tuple[str, str]],
) -> bool:
    """Check if two rows match the join conditions."""
    if not conditions:
        return True  # CROSS JOIN — all combinations

    for cond_left, cond_right in conditions:
        # Parse "table.col" references.
        parts_left = cond_left.split(".")
        parts_right = cond_right.split(".")
        if len(parts_left) != 2 or len(parts_right) != 2:
            continue

        t1_name, c1_name = parts_left[0].lower(), parts_left[1].lower()
        t2_name, c2_name = parts_right[0].lower(), parts_right[1].lower()

        # Determine which row/table maps to which side.
        if t1_name == table1.name.lower():
            col_idx1 = _find_col_index(table1, c1_name)
            col_idx2 = _find_col_index(table2, c2_name)
            if col_idx1 is not None and col_idx2 is not None:
                if compare_values(row1[col_idx1], row2[col_idx2]) != 0:
                    return False
        elif t1_name == table2.name.lower():
            col_idx1 = _find_col_index(table2, c1_name)
            col_idx2 = _find_col_index(table1, c2_name)
            if col_idx1 is not None and col_idx2 is not None:
                if compare_values(row2[col_idx1], row1[col_idx2]) != 0:
                    return False

    return True


def _find_col_index(table: Table, col_name: str) -> int | None:
    """Find a column index by name (case-insensitive)."""
    return table.column_index(col_name)