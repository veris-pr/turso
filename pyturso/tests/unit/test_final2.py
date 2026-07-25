"""Unit tests for CLI session differ, MVCC scenarios, and remaining items."""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="assignment"
# mypy: disable-error-code="attr-defined"
# mypy: disable-error-code="arg-type"

import sqlite3
from pathlib import Path

import pytest

from pyturso.database import Database
from pyturso.types.value import Value
from pyturso.mvcc.scenarios import SCENARIOS, run_write_skew


# --- MVCC scenarios ---
class TestMVCCScenarios:
    def test_scenario_catalog(self) -> None:
        assert len(SCENARIOS) >= 5
        names = [s["name"] for s in SCENARIOS]
        assert "disjoint_concurrent_writes" in names
        assert "write_write_conflict" in names
        assert "read_your_own_writes" in names
        assert "snapshot_stable_reads" in names
        assert "write_skew" in names

    def test_write_skew(self) -> None:
        result = run_write_skew()
        assert result["scenario"] == "write_skew"
        assert len(result["committed"]) == 2  # both commit
        assert len(result["aborted"]) == 0  # no conflict
        assert "anomaly" in result
        assert "nobody on call" in result["anomaly"].lower() or "inconsistent" in result["anomaly"].lower()

    def test_all_scenarios_have_deviate_flag(self) -> None:
        for s in SCENARIOS:
            assert "deviates" in s


# --- CLI session differ ---
class TestSessionDiffer:
    @pytest.fixture
    def db_and_session(self, tmp_path: Path) -> tuple[str, str]:
        db_path = tmp_path / "session.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA page_size=4096")
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.executemany("INSERT INTO t VALUES (?,?)", [(1, "alice"), (2, "bob")])
        conn.commit()
        conn.close()

        session_path = tmp_path / "session.sql"
        session_path.write_text(
            "SELECT * FROM t ORDER BY id;\n"
            "INSERT INTO t VALUES (3, 'carol');\n"
            "SELECT name FROM t ORDER BY id;\n",
            encoding="utf-8",
        )
        return str(db_path), str(session_path)

    def test_run_session(self, db_and_session: tuple[str, str]) -> None:
        from cli.session_differ import run_session
        db_path, session_path = db_and_session
        output = run_session(db_path, session_path)
        assert "alice" in output
        assert "bob" in output
        assert "carol" in output

    def test_run_session_dot_commands(self, db_and_session: tuple[str, str]) -> None:
        from cli.session_differ import run_session
        db_path, session_path = db_and_session
        # Add dot commands to the session.
        session = Path(session_path)
        session.write_text(
            ".tables\n"
            "SELECT * FROM t ORDER BY id;\n",
            encoding="utf-8",
        )
        output = run_session(db_path, str(session))
        # .tables output goes to stdout (not captured by run_session).
        # Just verify the SELECT output is there.
        assert "alice" in output


# --- final comprehensive integration ---
class TestComprehensiveIntegration:
    @pytest.fixture
    def db(self, tmp_path: Path) -> Database:
        db_path = tmp_path / "comp.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA page_size=4096")
        conn.execute("""CREATE TABLE products(
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            price REAL,
            in_stock INTEGER DEFAULT 1
        )""")
        conn.execute("CREATE INDEX idx_category ON products(category)")
        conn.executemany("INSERT INTO products VALUES (?,?,?,?,?)", [
            (1, "Widget", "hardware", 19.99, 1),
            (2, "Gadget", "hardware", 29.99, 1),
            (3, "Book", "media", 12.50, 0),
            (4, "Pen", "office", 2.99, 1),
            (5, "Notebook", "office", 5.99, 1),
        ])
        conn.commit()
        conn.close()
        return Database.open(str(db_path))

    def test_full_workflow(self, db: Database) -> None:
        """A comprehensive workflow: SELECT, INSERT, UPDATE, compound, PRAGMA."""
        conn = db.connect()

        # SELECT with WHERE and ORDER BY
        rows = conn.execute("SELECT name, price FROM products WHERE category = 'hardware' ORDER BY id")
        assert len(rows) == 2  # Widget and Gadget
        assert Value.text("Widget") in [r[0] for r in rows]

        # INSERT
        conn.execute("INSERT INTO products VALUES (6, 'Eraser', 'office', 1.99, 1)")
        rows = conn.execute("SELECT name FROM products ORDER BY id")
        assert len(rows) == 6

        # UPDATE
        conn.execute("UPDATE products SET in_stock = 1 WHERE name = 'Book'")
        rows = conn.execute("SELECT in_stock FROM products WHERE name = 'Book'")
        assert rows[0][0] == Value.integer(1)

        # Compound SELECT
        rows = conn.execute("SELECT name FROM products WHERE category = 'office' UNION SELECT name FROM products WHERE category = 'hardware'")
        names = {r[0].payload for r in rows}  # type: ignore[union-attr]
        assert "Pen" in names
        assert "Notebook" in names
        assert "Widget" in names
        assert "Gadget" in names
        assert "Eraser" in names

        # PRAGMA
        rows = conn.execute("PRAGMA table_info(products)")
        assert len(rows) == 5
        assert rows[0][1] == Value.text("id")

        rows = conn.execute("PRAGMA index_list(products)")
        assert len(rows) == 1

        # Functions
        rows = conn.execute("SELECT upper(name), length(name) FROM products WHERE id = 1")
        assert rows[0][0] == Value.text("WIDGET")
        assert rows[0][1] == Value.integer(6)

        # WHERE with IN
        rows = conn.execute("SELECT name FROM products WHERE category IN ('office', 'media') ORDER BY id")
        names = [r[0].payload for r in rows]  # type: ignore[union-attr]
        assert "Book" in names
        assert "Pen" in names
        assert "Notebook" in names
        assert "Eraser" in names

        # WHERE with BETWEEN
        rows = conn.execute("SELECT name FROM products WHERE price BETWEEN 3.0 AND 20.0 ORDER BY id")
        names = [r[0].payload for r in rows]  # type: ignore[union-attr]
        assert "Widget" in names  # 19.99
        assert "Book" in names  # 12.50
        assert "Notebook" in names  # 5.99
        assert "Pen" not in names  # 2.99 (below 3)

        # WHERE with LIKE
        rows = conn.execute("SELECT name FROM products WHERE name LIKE 'N%' ORDER BY id")
        assert rows[0][0] == Value.text("Notebook")

        # coalesce
        rows = conn.execute("SELECT coalesce(NULL, 'default') FROM products WHERE id = 1")
        assert rows[0][0] == Value.text("default")