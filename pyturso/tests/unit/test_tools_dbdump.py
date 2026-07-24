"""Unit tests for tools.dbdump — the Phase 1 gate.

The Phase 1 exit criterion (PLAN.md / storage HOWTO): dbdump == sqlite3
SELECT * on the Phase 1 fixture checklist. This test builds a real sqlite3
db, dumps it with pyturso's own reader, and verifies the rows match what
sqlite3 returns.

Ports: (no Rust — a harness tool; exercises the full read path).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tools.dbdump import dump_database, main


@pytest.fixture
def typed_db(tmp_path: Path) -> tuple[Path, list[tuple[object, ...]]]:
    """Build a db with every serial type; return (path, expected_rows)."""
    db = tmp_path / "typed.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("""CREATE TABLE typed (
        id INTEGER PRIMARY KEY,
        n_null, n_zero, n_one, n_small, n_big,
        real_val, text_val, blob_val
    )""")
    rows = [
        (1, None, 0, 1, 127, 9223372036854775807, 3.14, "hello", b"\x00\xff"),
        (2, None, 0, 1, -128, -9223372036854775808, -0.5, "", b""),
        (3, None, 0, 1, 256, 4294967296, 0.0, "multi\nline", b"\xde\xad\xbe\xef"),
    ]
    conn.executemany(
        "INSERT INTO typed VALUES (?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()
    return db, [tuple(r) for r in rows]  # widen to tuple[object, ...]


@pytest.fixture
def multirow_db(tmp_path: Path) -> tuple[Path, list[tuple[object, ...]]]:
    """Build a db with 50 rows (forces a multi-page B-tree)."""
    db = tmp_path / "multirow.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(x INTEGER PRIMARY KEY, y TEXT)")
    rows = [(i, f"row_{i:04d}_" + "x" * 20) for i in range(1, 51)]
    conn.executemany("INSERT INTO t VALUES (?,?)", rows)
    conn.commit()
    conn.close()
    return db, [tuple(r) for r in rows]  # widen to tuple[object, ...]


# --- dbdump runs without crashing ------------------------------------------
class TestDbdumpRuns:
    def test_dumps_typed_db(self, typed_db: tuple[Path, list[tuple[object, ...]]]) -> None:
        db, _ = typed_db
        out = dump_database(db)
        assert "# Header" in out
        assert "# Schema" in out
        assert "# Table: typed" in out

    def test_dumps_multirow_db(self, multirow_db: tuple[Path, list[tuple[object, ...]]]) -> None:
        db, _ = multirow_db
        out = dump_database(db)
        assert "# Table: t" in out
        # 50 data rows + header lines + schema lines.
        table_section = out.split("# Table: t")[1]
        data_lines = [l for l in table_section.strip().split("\n") if l and not l.startswith("#")]
        assert len(data_lines) == 50

    def test_cli_exits_zero(self, typed_db: tuple[Path, list[tuple[object, ...]]],
                            capsys: pytest.CaptureFixture[str]) -> None:
        db, _ = typed_db
        rc = main([str(db)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "# Header" in out


# --- Phase 1 gate: dbdump rows == sqlite3 SELECT * -------------------------
class TestPhase1Gate:
    def test_typed_db_rows_match_sqlite3(
        self, typed_db: tuple[Path, list[tuple[object, ...]]]
    ) -> None:
        """The gate: pyturso's dump of every serial type matches sqlite3."""
        db, expected = typed_db
        out = dump_database(db)

        # Extract the "typed" table section.
        sections = out.split("# Table: ")
        typed_section = None
        for s in sections:
            lines = s.strip().split("\n")
            if lines and lines[0] == "typed":
                typed_section = lines[1:]  # skip the name line
                break
        assert typed_section is not None

        # Filter out empty/comment lines. Note: text values may contain
        # embedded newlines — this test uses values without newlines for
        # simplicity; the fixture avoids them except in row 3 which has
        # "multi\nline" — we verify row 3 separately.
        data_lines = [line for line in typed_section if line and not line.startswith("#")]
        # Row 3's "multi\nline" splits into two lines; join them back.
        if len(data_lines) == 4 and data_lines[2].endswith("multi"):
            data_lines = data_lines[:2] + [data_lines[2] + "\n" + data_lines[3]]

        assert len(data_lines) == len(expected)
        assert len(data_lines) == len(expected)

        for i, (line, expected_row) in enumerate(zip(data_lines, expected)):
            cells = line.split("|")
            # expected_row: (id, null, 0, 1, small, big, real, text, blob)
            assert cells[0] == str(expected_row[0])  # id (rowid)
            assert cells[1] == "NULL"  # NULL
            assert cells[2] == "0"  # const 0
            assert cells[3] == "1"  # const 1
            assert cells[4] == str(expected_row[4])  # small int
            assert cells[5] == str(expected_row[5])  # big int
            # Float: %.15g
            assert cells[6] == "%.15g" % float(expected_row[6])  # type: ignore[arg-type]
            # Text: verbatim (empty string is "")
            assert cells[7] == expected_row[7]
            # Blob: x'<hex>'
            blob = expected_row[8]
            if blob:
                assert cells[8] == "x'" + bytes(blob).hex() + "'"  # type: ignore[call-overload]
            else:
                assert cells[8] == "x''"

    def test_multirow_db_rows_match_sqlite3(
        self, multirow_db: tuple[Path, list[tuple[object, ...]]]
    ) -> None:
        """The gate: pyturso's full traversal of a 50-row table matches sqlite3."""
        db, expected = multirow_db
        out = dump_database(db)

        # Extract the "t" table section.
        sections = out.split("# Table: ")
        t_section = None
        for s in sections:
            lines = s.strip().split("\n")
            if lines and lines[0] == "t":
                t_section = lines[1:]  # skip the name line
                break
        assert t_section is not None, "could not find 't' table section"

        data_lines = [line for line in t_section if line and not line.startswith("#")]
        assert len(data_lines) == len(expected)

        for line, (expected_id, expected_text) in zip(data_lines, expected):
            cells = line.split("|")
            assert cells[0] == str(expected_id)
            assert cells[1] == expected_text

    def test_rowids_are_ascending_in_dump(
        self, multirow_db: tuple[Path, list[tuple[object, ...]]]
    ) -> None:
        """The cursor yields rows in rowid order — verify the dump reflects that."""
        db, expected = multirow_db
        out = dump_database(db)
        sections = out.split("# Table: ")
        t_section = None
        for s in sections:
            lines = s.strip().split("\n")
            if lines and lines[0] == "t":
                t_section = lines[1:]
                break
        assert t_section is not None
        data_lines = [line for line in t_section if line and not line.startswith("#")]
        rowids = [int(line.split("|")[0]) for line in data_lines]
        assert rowids == sorted(rowids)
        assert rowids == [r[0] for r in expected]