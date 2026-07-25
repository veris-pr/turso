"""Unit tests for CLI exec helper, dot-command parity, MVCC visibility rules."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pyturso.database import Database
from pyturso.types.value import Value
from pyturso.mvcc.visibility_rules import VISIBILITY_RULES, TwoConnectionMode


# --- CLI exec helper ---
class TestCLIExec:
    @pytest.fixture
    def db(self, tmp_path: Path) -> str:
        db_path = tmp_path / "exec.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA page_size=4096")
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.executemany("INSERT INTO t VALUES (?,?)", [(1, "alice"), (2, "bob")])
        conn.commit()
        conn.close()
        return str(db_path)

    def test_exec_sql(self, db: str) -> None:
        from cli.exec import exec_sql
        output = exec_sql(db, "SELECT * FROM t ORDER BY id")
        assert "alice" in output
        assert "bob" in output

    def test_exec_sql_file(self, db: str, tmp_path: Path) -> None:
        from cli.exec import exec_sql_file
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT name FROM t ORDER BY id;", encoding="utf-8")
        output = exec_sql_file(db, str(sql_file))
        assert "alice" in output
        assert "bob" in output

    def test_exec_multiple_statements(self, db: str) -> None:
        from cli.exec import exec_sql
        output = exec_sql(db, "SELECT name FROM t WHERE id = 1; SELECT name FROM t WHERE id = 2;")
        assert "alice" in output
        assert "bob" in output


# --- dot-command parity ---
class TestDotCommandParity:
    def test_dot_commands_table_exists(self) -> None:
        from pathlib import Path
        parity_path = Path(__file__).resolve().parent.parent.parent / "docs" / "cli" / "reference" / "dot-commands.md"
        assert parity_path.exists()
        content = parity_path.read_text()
        assert ".quit" in content
        assert ".tables" in content
        assert ".schema" in content
        assert ".mode" in content
        assert ".read" in content


# --- MVCC visibility rules ---
class TestVisibilityRules:
    def test_rules_count(self) -> None:
        assert len(VISIBILITY_RULES) >= 6

    def test_rules_have_fields(self) -> None:
        for rule in VISIBILITY_RULES:
            assert "rule" in rule
            assert "condition" in rule
            assert "visible" in rule

    def test_read_your_own_writes_rule(self) -> None:
        rule = [r for r in VISIBILITY_RULES if "read-your-own-writes" in r["rule"]][0]
        assert "Yes" in rule["visible"]

    def test_dirty_reads_not_allowed(self) -> None:
        rule = [r for r in VISIBILITY_RULES if "uncommitted" in r["rule"]][0]
        assert "No" in rule["visible"]


# --- two-connection mode ---
class TestTwoConnectionMode:
    def test_add_scenario(self) -> None:
        mode = TwoConnectionMode()
        mode.add_scenario("test", "description", "expected")
        assert len(mode.scenarios) == 1
        assert mode.scenarios[0]["name"] == "test"

    def test_run_all(self) -> None:
        mode = TwoConnectionMode()
        mode.add_scenario("s1", "d1", "e1")
        mode.add_scenario("s2", "d2", "e2")
        results = mode.run_all()
        assert len(results) == 2