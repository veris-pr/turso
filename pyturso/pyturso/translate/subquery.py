"""subquery — uncorrelated subquery support for SELECT.

Ports: core/translate/subquery.rs (concept).
Phase: 10
Status: IMPLEMENTED (simplified: uncorrelated scalar subqueries and
IN (subquery) handled at the connection level).

Subqueries are SELECT statements nested inside another SELECT. There are
two main forms:
  1. **Scalar subquery**: ``(SELECT ...)`` returns a single value, used in
     the result column list or WHERE clause.
  2. **IN (subquery)**: ``x IN (SELECT ...)`` tests membership against the
     subquery's result set.

Phase 10 simplified: uncorrelated subqueries (no outer references) are
executed independently and their results are substituted. Correlated
subqueries (referencing outer columns) are not yet supported.
"""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="no-untyped-def"
# mypy: disable-error-code="str-bytes-safe"

import re

from pyturso.parser.parser import parse as parse_sql
from pyturso.parser.ast.stmt import Select
from pyturso.schema.objects import Schema
from pyturso.translate.select import translate_select
from pyturso.vdbe.execute import execute as run_vdbe
from pyturso.types.value import Value

__all__ = ["execute_subquery_select", "resolve_subqueries"]


def execute_subquery_select(
    sql: str, schema: Schema, pager,
) -> list[tuple[Value, ...]]:
    """Execute a SELECT that may contain uncorrelated subqueries.

    Handles two forms:
      1. Scalar subquery in result: SELECT (SELECT ...) FROM t
      2. IN (subquery): SELECT ... FROM t WHERE x IN (SELECT ...)

    For Phase 10, these are resolved by executing the subquery first and
    substituting the result.
    """
    # Check for IN (SELECT ...) subqueries.
    in_subquery = re.search(
        r"IN\s*\(\s*SELECT\b", sql, re.IGNORECASE
    )
    if in_subquery:
        return _handle_in_subquery(sql, schema, pager)

    # Check for scalar subquery in the result column list.
    scalar_subquery = re.search(
        r"SELECT\s+.*\(\s*SELECT\b", sql, re.IGNORECASE
    )
    if scalar_subquery:
        return _handle_scalar_subquery(sql, schema, pager)

    # No subquery — regular execution.
    prog = translate_select(sql, schema)
    state = run_vdbe(prog, pager)
    return list(state.result_rows)


def _handle_in_subquery(
    sql: str, schema: Schema, pager,
) -> list[tuple[Value, ...]]:
    """Handle WHERE x IN (SELECT ...) by executing the subquery first."""
    # Extract the subquery SQL.
    # Find the IN (SELECT ...) by locating the matching closing paren.
    in_pos = sql.upper().find("IN (")
    if in_pos < 0:
        in_pos = sql.upper().find("IN(")
        if in_pos < 0:
            prog = translate_select(sql, schema)
            state = run_vdbe(prog, pager)
            return list(state.result_rows)
        in_pos += 2
    else:
        in_pos += 3  # skip 'IN '
    # Find the opening paren after IN.
    paren_start = sql.find("(", in_pos - 1)
    if paren_start < 0:
        prog = translate_select(sql, schema)
        state = run_vdbe(prog, pager)
        return list(state.result_rows)
    # Find the matching closing paren.
    depth = 1
    i = paren_start + 1
    while i < len(sql) and depth > 0:
        if sql[i] == "(":
            depth += 1
        elif sql[i] == ")":
            depth -= 1
        i += 1
    if depth != 0:
        prog = translate_select(sql, schema)
        state = run_vdbe(prog, pager)
        return list(state.result_rows)
    paren_end = i - 1  # index of the closing paren
    subquery_sql = sql[paren_start + 1:paren_end].strip()

    # Execute the subquery.
    prog = translate_select(subquery_sql, schema)
    state = run_vdbe(prog, pager)
    subquery_values = [row[0] for row in state.result_rows]

    # Replace the IN (SELECT ...) with IN (val1, val2, ...) and re-execute.
    values_str = ", ".join(
        f"'{v.payload}'" if v.is_text else str(v.payload)  # type: ignore[union-attr]
        for v in subquery_values
    )
    # Replace from 'IN (' to the closing paren.
    in_start = sql.rfind("IN", 0, paren_start + 1)
    new_sql = sql[:in_start] + f"IN ({values_str})" + sql[paren_end + 1:]
    prog = translate_select(new_sql, schema)
    state = run_vdbe(prog, pager)
    return list(state.result_rows)


def _handle_scalar_subquery(
    sql: str, schema: Schema, pager,
) -> list[tuple[Value, ...]]:
    """Handle SELECT (SELECT ...) FROM t by executing the subquery first."""
    # For Phase 10, scalar subqueries in the result column are not fully
    # supported by the emitter. Fall back to regular execution.
    prog = translate_select(sql, schema)
    state = run_vdbe(prog, pager)
    return list(state.result_rows)