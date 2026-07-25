"""repl — readline loop, multi-line statements, ';' termination.

Ports: cli/ (tursodb REPL loop, app.rs).
Phase: 12
Status: IMPLEMENTED (basic REPL with ';' termination, dot-command dispatch,
Ctrl-C clears buffer, errors printed without killing the session).
"""

from __future__ import annotations
# mypy: disable-error-code="no-untyped-def"
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="arg-type"

import sys

from pyturso.errors import TursoError

__all__ = ["run_repl"]


def run_repl(conn, *, quiet: bool = False) -> None:
    """Run the interactive REPL on ``conn``.

    Reads lines until a ``;`` is seen, then executes the accumulated SQL.
    Dot commands (``.quit``, ``.tables``, ``.schema``, etc.) are handled
    immediately. Errors are printed without killing the session.
    """
    from cli.output import render_rows
    from cli.dot_commands import handle_dot_command

    buffer: list[str] = []
    while True:
        try:
            prompt = "pyturso> " if not buffer else "   ...> "
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break

        line = line.strip()
        if not line:
            continue

        # Dot commands.
        if not buffer and line.startswith("."):
            if handle_dot_command(conn, line):
                break  # .quit returns True
            continue

        buffer.append(line)
        sql = " ".join(buffer)

        # Check for statement termination.
        if not sql.rstrip().endswith(";"):
            continue

        # Execute the SQL.
        try:
            rows = conn.execute(sql)
            for line_out in render_rows(rows):
                print(line_out)
        except TursoError as e:
            print(f"Error: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

        buffer.clear()