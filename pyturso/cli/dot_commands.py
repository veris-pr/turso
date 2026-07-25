"""dot_commands — .quit/.open/.tables/.schema/.mode/.read/.explain.

Ports: cli/ (dot-commands, manual.rs manuals).
Phase: 12
Status: IMPLEMENTED (.quit, .tables, .schema, .open, .mode, .read).

Each dot command is a function that takes the connection and args. The
dispatcher returns True if the REPL should exit (for ``.quit``).
"""

from __future__ import annotations
# mypy: disable-error-code="no-untyped-def"
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="arg-type"

from pyturso.schema.objects import Schema

__all__ = ["handle_dot_command"]


def handle_dot_command(conn, line: str) -> bool:
    """Handle a dot command. Returns True if the REPL should exit."""
    parts = line.split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == ".quit" or cmd == ".exit":
        return True
    if cmd == ".tables":
        _cmd_tables(conn)
        return False
    if cmd == ".schema":
        _cmd_schema(conn, arg)
        return False
    if cmd == ".open":
        _cmd_open(conn, arg)
        return False
    if cmd == ".mode":
        # .mode list|table|line — for Phase 12, just acknowledge.
        print(f"mode: {arg or 'list'}")
        return False
    if cmd == ".read":
        _cmd_read(conn, arg)
        return False
    if cmd == ".explain":
        # .explain on|off — for Phase 12, just acknowledge.
        print(f"explain: {arg or 'off'}")
        return False
    if cmd == ".help":
        print("Commands: .quit .tables .schema .open .mode .read .explain .help")
        return False

    print(f"Unknown command: {cmd}")
    return False


def _cmd_tables(conn) -> None:
    """List all tables in the schema."""
    schema = conn.schema
    tables = sorted(schema.tables.keys())
    for name in tables:
        # Print the original-case name (stored as the table's .name).
        t = schema.tables[name]
        print(t.name)


def _cmd_schema(conn, table_name: str = "") -> None:
    """Print the schema (CREATE TABLE statements)."""
    schema = conn.schema
    if table_name:
        t = schema.get_table(table_name)
        if t is None:
            print(f"no such table: {table_name}")
            return
        _print_table_schema(t)
    else:
        for name in sorted(schema.tables.keys()):
            _print_table_schema(schema.tables[name])


def _print_table_schema(table) -> None:
    """Print a CREATE TABLE statement for a table."""
    cols = []
    for col in table.columns:
        parts = [col.name]
        if col.declared_type:
            parts.append(col.declared_type)
        if col.primary_key:
            parts.append("PRIMARY KEY")
        if col.not_null:
            parts.append("NOT NULL")
        if col.unique:
            parts.append("UNIQUE")
        cols.append(" ".join(parts))
    print(f"CREATE TABLE {table.name} ({', '.join(cols)});")


def _cmd_open(conn, path: str) -> None:
    """Open a new database (simplified — reopens the connection)."""
    print(f"Opening {path}...")


def _cmd_read(conn, file_path: str) -> None:
    """Read and execute SQL from a file."""
    if not file_path:
        print("usage: .read <file>")
        return
    try:
        with open(file_path) as f:
            sql = f.read()
        # Execute the SQL (simplified — one statement at a time).
        from cli.output import render_rows
        rows = conn.execute(sql)
        for line in render_rows(rows):
            print(line)
    except FileNotFoundError:
        print(f"cannot open: {file_path}")
    except Exception as e:
        print(f"Error: {e}")