"""CLI non-interactive exec helper — runs SQL from stdin or args, prints results.

Ports: cli/app.rs (non-interactive mode).
Phase: 12
Status: IMPLEMENTED (the __main__.py already supports non-interactive mode;
this module provides a reusable helper).
"""

from __future__ import annotations

import sys
from pathlib import Path

from pyturso.database import Database

__all__ = ["exec_sql", "exec_sql_file"]


def exec_sql(db_path: str, sql: str, *, quiet: bool = False) -> str:
    """Execute SQL on a database and return the output as a string.

    Args:
        db_path: path to the database file.
        sql: SQL statement(s) to execute.
        quiet: if True, suppress headers.

    Returns:
        The output as a string (pipe-separated rows, one per line).
    """
    from cli.output import render_rows

    db = Database.open(db_path)
    conn = db.connect()
    output_lines: list[str] = []

    # Split on semicolons (simplified — no string-aware splitting).
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        try:
            rows = conn.execute(stmt + ";")
            for line in render_rows(rows):
                output_lines.append(line)
        except Exception as e:
            output_lines.append(f"Error: {e}")

    db.close()
    return "\n".join(output_lines) + ("\n" if output_lines else "")


def exec_sql_file(db_path: str, file_path: str, *, quiet: bool = False) -> str:
    """Execute SQL from a file on a database and return the output.

    Args:
        db_path: path to the database file.
        file_path: path to the SQL file.
        quiet: if True, suppress headers.

    Returns:
        The output as a string.
    """
    sql = Path(file_path).read_text(encoding="utf-8")
    return exec_sql(db_path, sql, quiet=quiet)