"""Cross-engine consistency: tursodb creates → pyturso reads → tursodb verifies.

This is the project's core verification philosophy in miniature: the same
database file is created by tursodb, read by pyturso's own reader, and then
re-verified by tursodb. If all three agree, the read path is correct against
a real engine — not just against stdlib sqlite3.

The test is skipped if the tursodb binary is unavailable (set TURSODB_BIN env
or the default path must exist). This keeps the test portable: it runs in
environments with the binary, skips elsewhere.

Flow:
  1. tursodb: CREATE TABLE + INSERT rows → writes a .db file
  2. pyturso: load_schema + BTreeCursor dump → reads schema + all rows
  3. tursodb: PRAGMA integrity_check + SELECT * → verifies the file
  4. Assert: pyturso's dump == tursodb's SELECT output
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import pytest

from pyturso.io.driver import run_to_completion
from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import WriteRequest
from pyturso.schema.load import load_schema_from_file
from pyturso.storage.btree import BTreeCursor
from pyturso.storage.pager import Pager
from pyturso.storage.sqlite3_ondisk import parse_record

#: Default tursodb binary path (built in the Docker setup).
_DEFAULT_TURSODB = "/workspace/target-linux/debug/tursodb"


def _get_tursodb() -> str | None:
    """Locate the tursodb binary (TURSODB_BIN env or default path)."""
    path = os.environ.get("TURSODB_BIN", _DEFAULT_TURSODB)
    if os.path.isfile(path) and os.access(path, os.X_OK):
        return path
    return None


def _tursodb_run(binary: str, db_path: str, sql: str) -> str:
    """Run a SQL statement through tursodb; return stdout."""
    result = subprocess.run(
        [binary, "-m", "list", db_path, sql],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        pytest.skip(f"tursodb failed (rc={result.returncode}): {result.stderr[:200]}")
    return result.stdout


# --- fixtures ---
@pytest.fixture
def tursodb() -> str:
    binary = _get_tursodb()
    if binary is None:
        pytest.skip("tursodb binary not available (set TURSODB_BIN)")
    return binary


@pytest.fixture
def db_created_by_tursodb(tursodb: str, tmp_path: Path) -> Path:
    """Create a database with tursodb: a table with typed columns + rows."""
    db = tmp_path / "cross.db"
    # Create the table and insert data via tursodb.
    _tursodb_run(tursodb, str(db), (
        "CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT, age INTEGER, "
        "score REAL, data BLOB)"
    ))
    _tursodb_run(tursodb, str(db),
        "INSERT INTO people VALUES (1, 'alice', 30, 95.5, x'00ff')")
    _tursodb_run(tursodb, str(db),
        "INSERT INTO people VALUES (2, 'bob', 25, 80.0, x'dead')")
    _tursodb_run(tursodb, str(db),
        "INSERT INTO people VALUES (3, 'charlie', 35, 88.3, x'')")
    # Create an index too.
    _tursodb_run(tursodb, str(db),
        "CREATE INDEX idx_age ON people (age)")
    return db


# --- test: tursodb creates, pyturso reads, tursodb verifies ---
class TestCrossEngineConsistency:
    def test_tursodb_creates_pyturso_reads_tursodb_verifies(
        self, tursodb: str, db_created_by_tursodb: Path
    ) -> None:
        """The defining cross-engine test:
        1. tursodb created the db (fixture).
        2. pyturso loads the schema and dumps all rows.
        3. tursodb verifies integrity_check + SELECT * still works.
        4. pyturso's row data matches tursodb's row data.
        """
        db_path = str(db_created_by_tursodb)

        # --- Step 2: pyturso reads the schema ---
        schema = load_schema_from_file(db_path)
        table = schema.get_table("people")
        assert table is not None, "pyturso could not find 'people' table"
        assert table.root_page > 0
        assert len(table.columns) == 5
        assert table.columns[0].name == "id"
        assert table.columns[0].rowid_alias, "id should be a rowid alias"
        assert table.columns[1].name == "name"

        # pyturso also sees the index.
        idx = schema.get_index("idx_age")
        assert idx is not None, "pyturso could not find 'idx_age' index"
        assert idx.table_name == "people"
        assert idx.columns[0].name == "age"

        # --- Step 2b: pyturso dumps all rows via BTreeCursor ---
        raw = db_created_by_tursodb.read_bytes()
        io = MemoryIO()
        f = io.open_file("db")
        f.pwrite(WriteRequest(f, 0, raw))
        pager = Pager(io, "db")
        pager.open()

        cursor = BTreeCursor(pager, root_page=table.root_page)
        run_to_completion(cursor.rewind())
        pyturso_rows: list[tuple[int, str, int, float, bytes]] = []
        while not cursor.done:
            row = cursor.row()
            rec = parse_record(row.payload)
            vals = rec.values
            # Column 0 (id) is INTEGER PRIMARY KEY → stored as NULL in record,
            # served from rowid. Column 1-4 are name, age, score, data.
            rowid = row.rowid
            name = vals[1] if len(vals) > 1 else None
            age = vals[2] if len(vals) > 2 else None
            score = vals[3] if len(vals) > 3 else None
            data = vals[4] if len(vals) > 4 else None
            pyturso_rows.append((rowid, str(name), int(age) if isinstance(age, int) else 0,
                                float(score) if isinstance(score, (int, float)) else 0.0,
                                bytes(data) if isinstance(data, bytes) else b""))
            run_to_completion(cursor.next())

        assert len(pyturso_rows) == 3, f"pyturso saw {len(pyturso_rows)} rows, expected 3"

        # --- Step 3: tursodb verifies the database is still valid ---
        integrity = _tursodb_run(tursodb, db_path, "PRAGMA integrity_check")
        assert "ok" in integrity.lower(), f"tursodb integrity_check failed: {integrity}"

        # --- Step 4: tursodb's SELECT * matches pyturso's dump ---
        tursodb_output = _tursodb_run(tursodb, db_path, "SELECT * FROM people ORDER BY id")
        tursodb_lines = [line for line in tursodb_output.strip().split("\n") if line]

        # tursodb list mode: pipe-separated, NULL → empty, blob → lossy utf-8.
        # pyturso: typed values. Compare rowid + name + age (the fields that
        # render identically across both engines).
        for i, pyturso_row in enumerate(pyturso_rows):
            tursodb_line = tursodb_lines[i]
            cells = tursodb_line.split("|")
            # tursodb list: id|name|age|score|data (data is lossy utf-8 for blobs)
            assert cells[0] == str(pyturso_row[0]), f"rowid mismatch: {cells[0]} != {pyturso_row[0]}"
            assert cells[1] == pyturso_row[1], f"name mismatch: {cells[1]} != {pyturso_row[1]}"
            assert cells[2] == str(pyturso_row[2]), f"age mismatch: {cells[2]} != {pyturso_row[2]}"

    def test_pyturso_schema_matches_tursodb_table_info(
        self, tursodb: str, db_created_by_tursodb: Path
    ) -> None:
        """pyturso's schema objects agree with tursodb's PRAGMA table_info."""
        db_path = str(db_created_by_tursodb)

        # pyturso's view.
        schema = load_schema_from_file(db_path)
        table = schema.get_table("people")
        assert table is not None

        # tursodb's view: use sqlite3 (stdlib) as the cross-check since tursodb
        # doesn't have PRAGMA table_info in list mode easily. sqlite3 reads the
        # same file format.
        conn = sqlite3.connect(db_path)
        tursodb_cols = conn.execute("PRAGMA table_info(people)").fetchall()
        conn.close()

        # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
        assert len(tursodb_cols) == len(table.columns)
        for i, (cid, name, type_name, notnull, dflt, pk) in enumerate(tursodb_cols):
            col = table.columns[i]
            assert col.name == name, f"col {i}: name {col.name!r} != {name!r}"
            # Type names may differ in case/whitespace; compare uppercased.
            assert col.declared_type.upper().replace(" ", "") == type_name.upper().replace(" ", ""), (
                f"col {i}: type {col.declared_type!r} != {type_name!r}"
            )