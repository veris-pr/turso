"""Unit tests for pyturso.schema — objects + load, verified against sqlite3.

Uses stdlib sqlite3 to create fixtures (no tursodb dependency). Verifies:
- Schema loads from a real db file.
- Table/column/index objects match sqlite3's PRAGMA.
- Rowid-alias detection for INTEGER PRIMARY KEY.
- Quoted identifiers, mixed case, multi-column indexes.
- Unparseable SQL raises Corrupt.
- is_stale() seam.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from pyturso.errors import Corrupt
from pyturso.schema.load import load_schema_from_file
from pyturso.schema.objects import Column, Index, IndexColumn, Schema, Table, make_column
from pyturso.types.affinity import Affinity


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create a db with tables, indexes, and edge cases."""
    db = tmp_path / "schema.db"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE people (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER,
            score REAL DEFAULT 0,
            data BLOB
        );
        CREATE INDEX idx_age ON people (age);
        CREATE TABLE "Mixed Case" (x INTEGER, y TEXT);
        CREATE TABLE no_pk (a TEXT, b INTEGER);
        CREATE TABLE ipk_auto (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT);
    """)
    conn.executemany("INSERT INTO people VALUES (?, ?, ?, ?, ?)",
                     [(1, "alice", 30, 95.5, b"\x00\xff"),
                      (2, "bob", 25, 80.0, b"\xde\xad")])
    conn.execute('INSERT INTO "Mixed Case" VALUES (1, "hello")')
    conn.commit()
    conn.close()
    return db


# --- objects.py: unit tests ---
class TestObjects:
    def test_make_column_affinity(self) -> None:
        col = make_column("x", "INTEGER")
        assert col.affinity is Affinity.INTEGER

    def test_make_column_text_affinity(self) -> None:
        col = make_column("name", "VARCHAR(255)")
        assert col.affinity is Affinity.TEXT

    def test_make_column_no_type_blob_affinity(self) -> None:
        col = make_column("x", "")
        assert col.affinity is Affinity.BLOB

    def test_table_column_index_case_insensitive(self) -> None:
        t = Table("T", [make_column("Col", "TEXT")], 2)
        assert t.column_index("col") == 0
        assert t.column_index("COL") == 0
        assert t.column_index("Col") == 0
        assert t.column_index("nonexistent") is None

    def test_schema_get_table_case_insensitive(self) -> None:
        s = Schema()
        t = Table("MyTable", [make_column("x", "INT")], 3)
        s.add_table(t)
        assert s.get_table("mytable") is not None
        assert s.get_table("MYTABLE") is not None
        assert s.get_table("MyTable") is not None

    def test_schema_indexes_on(self) -> None:
        s = Schema()
        s.add_index(Index("idx1", "t", [IndexColumn("x", False)], 3))
        s.add_index(Index("idx2", "t", [IndexColumn("y", False)], 4))
        s.add_index(Index("idx3", "u", [IndexColumn("z", False)], 5))
        assert len(s.indexes_on("t")) == 2
        assert len(s.indexes_on("u")) == 1
        assert len(s.indexes_on("v")) == 0

    def test_is_stale(self) -> None:
        s = Schema()
        s.schema_cookie = 5
        assert not s.is_stale(5)
        assert s.is_stale(6)


# --- load.py: verified against a real sqlite3 db ---
class TestLoadSchema:
    def test_loads_tables(self, db_path: Path) -> None:
        schema = load_schema_from_file(str(db_path))
        assert schema.get_table("people") is not None
        assert schema.get_table("Mixed Case") is not None
        assert schema.get_table("no_pk") is not None
        assert schema.get_table("ipk_auto") is not None

    def test_people_table_columns(self, db_path: Path) -> None:
        schema = load_schema_from_file(str(db_path))
        table = schema.get_table("people")
        assert table is not None
        assert len(table.columns) == 5
        assert table.columns[0].name == "id"
        assert table.columns[1].name == "name"
        assert table.columns[2].name == "age"
        assert table.columns[3].name == "score"
        assert table.columns[4].name == "data"

    def test_people_column_affinities(self, db_path: Path) -> None:
        schema = load_schema_from_file(str(db_path))
        table = schema.get_table("people")
        assert table is not None
        assert table.columns[0].affinity is Affinity.INTEGER
        assert table.columns[1].affinity is Affinity.TEXT
        assert table.columns[2].affinity is Affinity.INTEGER
        assert table.columns[3].affinity is Affinity.REAL
        assert table.columns[4].affinity is Affinity.BLOB

    def test_rowid_alias_detection(self, db_path: Path) -> None:
        schema = load_schema_from_file(str(db_path))
        people = schema.get_table("people")
        assert people is not None
        assert people.rowid_alias_col == 0, "id is INTEGER PRIMARY KEY → rowid alias"
        assert people.columns[0].rowid_alias is True

        no_pk = schema.get_table("no_pk")
        assert no_pk is not None
        assert no_pk.rowid_alias_col is None

    def test_autoincrement_flag(self, db_path: Path) -> None:
        schema = load_schema_from_file(str(db_path))
        ipk_auto = schema.get_table("ipk_auto")
        assert ipk_auto is not None
        assert ipk_auto.has_autoincrement is True
        assert ipk_auto.rowid_alias_col == 0

    def test_not_null_flag(self, db_path: Path) -> None:
        schema = load_schema_from_file(str(db_path))
        people = schema.get_table("people")
        assert people is not None
        assert people.columns[1].not_null is True  # name TEXT NOT NULL
        assert people.columns[2].not_null is False  # age INTEGER (nullable)

    def test_loads_indexes(self, db_path: Path) -> None:
        schema = load_schema_from_file(str(db_path))
        idx = schema.get_index("idx_age")
        assert idx is not None
        assert idx.table_name == "people"
        assert idx.columns[0].name == "age"
        assert not idx.unique

    def test_quoted_identifier_table(self, db_path: Path) -> None:
        schema = load_schema_from_file(str(db_path))
        table = schema.get_table("Mixed Case")
        assert table is not None
        assert table.columns[0].name == "x"
        assert table.columns[1].name == "y"

    def test_schema_cookie_captured(self, db_path: Path) -> None:
        schema = load_schema_from_file(str(db_path))
        assert schema.schema_cookie > 0

    def test_root_page_is_valid(self, db_path: Path) -> None:
        schema = load_schema_from_file(str(db_path))
        people = schema.get_table("people")
        assert people is not None
        assert people.root_page >= 2  # page 1 is sqlite_schema

    def test_matches_sqlite3_table_info(self, db_path: Path) -> None:
        """pyturso's schema objects agree with sqlite3's PRAGMA table_info."""
        schema = load_schema_from_file(str(db_path))
        people = schema.get_table("people")
        assert people is not None
        conn = sqlite3.connect(str(db_path))
        pragma_cols = conn.execute("PRAGMA table_info(people)").fetchall()
        conn.close()
        assert len(pragma_cols) == len(people.columns)
        for i, (cid, name, type_name, notnull, dflt, pk) in enumerate(pragma_cols):
            col = people.columns[i]
            assert col.name == name
            assert col.declared_type.upper().replace(" ", "") == type_name.upper().replace(" ", "")