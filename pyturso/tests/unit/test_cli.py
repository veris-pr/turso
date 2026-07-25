"""Unit tests for Phase 12: CLI output, dot-commands, non-interactive mode."""

from __future__ import annotations
# mypy: disable-error-code="no-untyped-def"
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="union-attr"

import sqlite3
from pathlib import Path

import pytest

from pyturso.database import Database
from pyturso.types.value import Value
from cli.output import render_rows, render_cell
from cli.dot_commands import handle_dot_command


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db_path = tmp_path / "cli.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    conn.executemany("INSERT INTO t VALUES (?,?,?)",
                     [(1, "alice", 30), (2, "bob", 25)])
    conn.commit()
    conn.close()
    return Database.open(str(db_path))


# --- output ---
class TestOutput:
    def test_render_cell_integer(self) -> None:
        assert render_cell(Value.integer(42)) == "42"

    def test_render_cell_text(self) -> None:
        assert render_cell(Value.text("hello")) == "hello"

    def test_render_cell_null(self) -> None:
        assert render_cell(Value.null()) == ""

    def test_render_cell_real(self) -> None:
        assert render_cell(Value.real(3.14)) == "3.14"

    def test_render_rows_pipe_separated(self) -> None:
        rows = [(Value.integer(1), Value.text("x"), Value.null())]
        assert render_rows(rows) == ["1|x|"]

    def test_render_rows_multiple(self) -> None:
        rows = [
            (Value.integer(1), Value.text("alice")),
            (Value.integer(2), Value.text("bob")),
        ]
        assert render_rows(rows) == ["1|alice", "2|bob"]


# --- dot commands ---
class TestDotCommands:
    def test_quit_returns_true(self, db: Database) -> None:
        conn = db.connect()
        assert handle_dot_command(conn, ".quit") is True

    def test_tables(self, db: Database, capsys) -> None:
        conn = db.connect()
        handle_dot_command(conn, ".tables")
        out = capsys.readouterr().out
        assert "t" in out

    def test_schema(self, db: Database, capsys) -> None:
        conn = db.connect()
        handle_dot_command(conn, ".schema t")
        out = capsys.readouterr().out
        assert "CREATE TABLE" in out
        assert "id" in out
        assert "name" in out

    def test_schema_all(self, db: Database, capsys) -> None:
        conn = db.connect()
        handle_dot_command(conn, ".schema")
        out = capsys.readouterr().out
        assert "CREATE TABLE" in out

    def test_mode(self, db: Database, capsys) -> None:
        conn = db.connect()
        handle_dot_command(conn, ".mode list")
        out = capsys.readouterr().out
        assert "list" in out

    def test_help(self, db: Database, capsys) -> None:
        conn = db.connect()
        handle_dot_command(conn, ".help")
        out = capsys.readouterr().out
        assert ".quit" in out

    def test_unknown(self, db: Database, capsys) -> None:
        conn = db.connect()
        handle_dot_command(conn, ".bogus")
        out = capsys.readouterr().out
        assert "Unknown" in out


# --- non-interactive mode ---
class TestNonInteractive:
    def test_execute_sql(self, db: Database, capsys) -> None:
        conn = db.connect()
        from cli.__main__ import _execute_and_print
        _execute_and_print(conn, "SELECT name FROM t ORDER BY id")
        out = capsys.readouterr().out
        assert "alice" in out
        assert "bob" in out

    def test_execute_select_all(self, db: Database, capsys) -> None:
        conn = db.connect()
        from cli.__main__ import _execute_and_print
        _execute_and_print(conn, "SELECT * FROM t ORDER BY id")
        out = capsys.readouterr().out
        lines = out.strip().split("\n")
        assert lines[0] == "1|alice|30"
        assert lines[1] == "2|bob|25"