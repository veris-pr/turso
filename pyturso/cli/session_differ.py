"""CLI scripted-session differ — run a session file through pyturso and compare.

Ports: (pyturso-specific — no Rust counterpart; inspired by testing/cli_tests/).
Phase: 12
Status: IMPLEMENTED (runs a .sql session file through the pyturso CLI and
captures output, diffable against tursodb).

A scripted session is a plain text file containing SQL statements and
dot-commands, one per line (or multi-line with ';' termination). The differ
runs the session through pyturso and captures the output, then optionally
compares against tursodb's output for the same session.
"""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"

from pathlib import Path

from pyturso.database import Database

__all__ = ["run_session", "compare_sessions"]


def run_session(db_path: str, session_path: str) -> str:
    """Run a session file through the pyturso CLI and capture output.

    Args:
        db_path: path to the database file.
        session_path: path to the session file (.sql or .txt).

    Returns:
        The captured output as a string.
    """
    from cli.output import render_rows
    from cli.dot_commands import handle_dot_command

    db = Database.open(db_path)
    conn = db.connect()

    session = Path(session_path).read_text(encoding="utf-8")
    output_lines: list[str] = []
    buffer: list[str] = []

    for line in session.split("\n"):
        line = line.strip()
        if not line or line.startswith("--"):
            continue

        # Dot commands.
        if not buffer and line.startswith("."):
            if handle_dot_command(conn, line):
                break
            continue

        buffer.append(line)
        sql = " ".join(buffer)

        if not sql.rstrip().endswith(";"):
            continue

        # Execute the SQL.
        try:
            rows = conn.execute(sql)
            for line_out in render_rows(rows):
                output_lines.append(line_out)
        except Exception as e:
            output_lines.append(f"Error: {e}")

        buffer.clear()

    db.close()
    return "\n".join(output_lines) + "\n" if output_lines else ""


def compare_sessions(
    db_path: str, session_path: str, tursodb_bin: str | None = None,
) -> tuple[str, str | None]:
    """Run a session through pyturso and optionally tursodb.

    Returns ``(pyturso_output, tursodb_output_or_None)``.
    """
    pyturso_out = run_session(db_path, session_path)
    tursodb_out = None

    if tursodb_bin:
        import subprocess
        try:
            result = subprocess.run(
                [tursodb_bin, "-m", "list", db_path],
                input=Path(session_path).read_text(encoding="utf-8"),
                capture_output=True, text=True, timeout=15,
            )
            tursodb_out = result.stdout
        except Exception:
            tursodb_out = None

    return pyturso_out, tursodb_out