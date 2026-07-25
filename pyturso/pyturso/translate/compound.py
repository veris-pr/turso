"""compound — compound SELECT (UNION/UNION ALL/INTERSECT/EXCEPT) support.

Ports: core/translate/compound_select.rs (concept).
Phase: 10
Status: IMPLEMENTED (in-memory: execute each SELECT, combine results with
set operations in Python).

Compound SELECTs combine the results of two or more SELECT statements:
  - ``UNION``: all unique rows from both sides.
  - ``UNION ALL``: all rows from both sides (including duplicates).
  - ``INTERSECT``: rows that appear in both sides (unique).
  - ``EXCEPT``: rows in the left side that are not in the right side (unique).

Phase 10 simplified: each sub-SELECT is executed independently and the
results are combined in Python using set operations. This is not how SQLite
does it (SQLite uses ephemeral tables and sorters in the VDBE), but it
produces the correct results.
"""

from __future__ import annotations
# mypy: disable-error-code="no-untyped-def"
# mypy: disable-error-code="has-type"

from pyturso.parser.ast.stmt import Select, SelectBody
from pyturso.parser.parser import parse as parse_sql
from pyturso.schema.objects import Schema
from pyturso.translate.select import translate_select
from pyturso.vdbe.execute import execute as run_vdbe
from pyturso.types.value import Value

__all__ = ["execute_compound_select", "combine_results"]


def execute_compound_select(
    sql: str, schema: Schema, pager,
) -> list[tuple[Value, ...]]:
    """Execute a compound SELECT (UNION/INTERSECT/EXCEPT/UNION ALL).

    Parses the SQL, detects compound operators, executes each sub-SELECT,
    and combines results. Falls back to regular SELECT for non-compound.
    """
    # Split on compound keywords (simplified — no nested compound support).
    parts = _split_compound(sql)
    if len(parts[1]) == 0:
        # Not a compound SELECT — regular execution.
        prog = translate_select(sql.strip().rstrip(";"), schema)
        state = run_vdbe(prog, pager)
        return list(state.result_rows)

    # Execute each part and combine.
    operators = parts[1]  # list of (operator, sql)
    left_sql = parts[0]
    left_rows = _exec_subquery(left_sql, schema, pager)

    for op, right_sql in operators:
        right_rows = _exec_subquery(right_sql, schema, pager)
        left_rows = combine_results(left_rows, right_rows, op)

    return left_rows


def combine_results(
    left: list[tuple[Value, ...]],
    right: list[tuple[Value, ...]],
    op: str,
) -> list[tuple[Value, ...]]:
    """Combine two result sets with a compound operator."""
    op_upper = op.upper().strip()
    if op_upper == "UNION ALL":
        return left + right
    if op_upper == "UNION":
        # All unique rows from both sides.
        seen: set[tuple[Value, ...]] = set()
        result: list[tuple[Value, ...]] = []
        for row in left + right:
            if row not in seen:
                seen.add(row)
                result.append(row)
        return result
    if op_upper == "INTERSECT":
        right_set = set(right)
        seen = set()
        result = []
        for row in left:
            if row in right_set and row not in seen:
                seen.add(row)
                result.append(row)
        return result
    if op_upper == "EXCEPT":
        right_set = set(right)
        seen = set()
        result = []
        for row in left:
            if row not in right_set and row not in seen:
                seen.add(row)
                result.append(row)
        return result
    raise ValueError(f"unknown compound operator: {op}")


def _exec_subquery(
    sql: str, schema: Schema, pager,
) -> list[tuple[Value, ...]]:
    """Execute a sub-SELECT and return its rows."""
    # Wrap in a SELECT if the SQL is just a SELECT fragment.
    clean_sql = sql.strip().rstrip(";")
    prog = translate_select(clean_sql, schema)
    state = run_vdbe(prog, pager)
    return list(state.result_rows)


def _split_compound(sql: str) -> tuple[str, list[tuple[str, str]]]:
    """Split a compound SELECT into parts.

    Returns (first_select, [(operator, next_select), ...]).
    Returns (sql, []) if not a compound SELECT.
    """
    import re

    # Match UNION, UNION ALL, INTERSECT, EXCEPT at the top level.
    # Simplified: no parenthesized subqueries.
    pattern = re.compile(
        r"\b(UNION\s+ALL|UNION|INTERSECT|EXCEPT)\b",
        re.IGNORECASE,
    )

    parts: list[tuple[str, str]] = []
    current = sql
    last_pos = 0
    first_sql = ""
    operators: list[tuple[str, str]] = []

    matches = list(pattern.finditer(sql))
    if not matches:
        return (sql, [])

    pos = 0
    for m in matches:
        # Extract the SELECT before this operator.
        before = sql[pos:m.start()].strip()
        if not first_sql:
            first_sql = before
        else:
            operators.append((prev_op, before))
        prev_op = m.group(1).upper().replace("  ", " ")
        pos = m.end()

    # The last SELECT after the final operator.
    last_sql = sql[pos:].strip().rstrip(";")
    operators.append((prev_op, last_sql))

    return (first_sql, operators)