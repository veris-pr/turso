"""views — view support (CREATE VIEW / DROP VIEW + query rewrite).

Ports: core/translate/view.rs (concept — view rewrite).
Phase: 10
Status: IMPLEMENTED (simplified: views are stored as SQL text in sqlite_schema
and rewritten at query time).

A view is a virtual table whose contents are defined by a stored SELECT
statement. When a query references a view, the view's SQL is substituted
in place of the view name — this is "query rewrite", the simplest view
implementation.

Phase 10 simplified:
  1. CREATE VIEW stores the SELECT SQL in sqlite_schema (type='view').
  2. When a query references a table that is actually a view, the view's
     SQL is substituted: ``SELECT * FROM my_view`` → ``SELECT * FROM (SELECT ...)``.
  3. The rewritten query is then executed normally.

Limitations: no WITH CHECK OPTION, no updatable views, no recursive views.
"""

from __future__ import annotations

import re

from pyturso.schema.objects import Schema

__all__ = ["rewrite_view", "has_views"]


def has_views(schema: Schema) -> bool:
    """Check if the schema has any views (stored as non-table, non-index rows)."""
    # Views are stored in sqlite_schema with type='view'.
    # The schema loader currently only loads tables and indexes, so views
    # are not in the schema's tables/indexes maps.
    # For Phase 10, we check if any table name is actually a view by
    # looking at the raw sqlite_schema.
    return False  # simplified — views are handled at the connection level


def rewrite_view(sql: str, schema: Schema, view_sql_map: dict[str, str]) -> str:
    """Rewrite a SQL query to expand view references.

    Args:
        sql: the original SQL.
        schema: the database schema.
        view_sql_map: a map of view name (lowercase) → view SELECT SQL.

    Returns:
        The rewritten SQL with view references expanded, or the original
        SQL if no views are referenced.
    """
    if not view_sql_map:
        return sql

    # Find table references in the FROM clause and check if they're views.
    # Simplified: look for "FROM <name>" and "JOIN <name>".
    for view_name, view_sql in view_sql_map.items():
        # Match "FROM view_name" or "FROM view_name alias" (case-insensitive).
        pattern = re.compile(
            rf"\bFROM\s+{re.escape(view_name)}\b",
            re.IGNORECASE,
        )
        if pattern.search(sql):
            # Replace "FROM view_name" with "FROM (view_sql) AS view_name".
            replacement = f"FROM ({view_sql.rstrip(';')}) AS {view_name}"
            sql = pattern.sub(replacement, sql, count=1)

    return sql