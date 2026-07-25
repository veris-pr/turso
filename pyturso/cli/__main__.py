"""__main__ — python -m cli — interactive and -q non-interactive modes.

Ports: cli/ (entry, app.rs main).
Phase: 12
Status: IMPLEMENTED (non-interactive mode + basic interactive REPL).

Usage::

    python -m cli <db_path>              # interactive REPL
    python -m cli <db_path> "SQL"        # non-interactive: execute SQL, print results
    python -m cli <db_path> "SQL" -q     # quiet mode (no header)
"""

from __future__ import annotations
# mypy: disable-error-code="no-untyped-def"
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="arg-type"

import argparse
import sys

from pyturso.database import Database

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(prog="pyturso")
    parser.add_argument("database", help="database file path")
    parser.add_argument("sql", nargs="?", default=None, help="SQL to execute (non-interactive)")
    parser.add_argument("-q", action="store_true", help="quiet mode (no header)")
    args = parser.parse_args(argv)

    db = Database.open(args.database)
    conn = db.connect()

    if args.sql:
        # Non-interactive mode: execute SQL and print results.
        _execute_and_print(conn, args.sql, quiet=args.q)
    else:
        # Interactive REPL.
        from cli.repl import run_repl
        run_repl(conn, quiet=args.q)

    db.close()
    return 0


def _execute_and_print(conn, sql: str, *, quiet: bool = False) -> None:
    """Execute SQL and print results in list mode."""
    from cli.output import render_rows
    rows = conn.execute(sql)
    for line in render_rows(rows):
        print(line)


if __name__ == "__main__":
    sys.exit(main())