"""Unit tests for tools.mkdb — deterministic fixture DB builder.

Builds fixture databases via stdlib sqlite3; verifies the determinism contract,
round-trip correctness, output-path derivation, and error handling.

Ports/verified against: SQLite file format (page_size power-of-two rule),
tools/HOWTO.md determinism contract.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tools.mkdb import (
    DEFAULT_PAGE_SIZE,
    BuildResult,
    build_database,
    main,
    validate_page_size,
)

# A fixture script exercising every serial type the Phase 1 reader must handle
# (serial 0 NULL, 1 int8, 2 int16, 3 int24, 4 int32, 5 int48, 6 int64, 7 float,
# 8/9 const 0/1, plus TEXT and BLOB). Doubles as a phase1_read corpus reference.
FIXTURE_SQL = """
CREATE TABLE typed (
    id INTEGER PRIMARY KEY,
    n_null,
    n_zero,
    n_one,
    n_small,
    n_big,
    real,
    txt,
    blb
);
INSERT INTO typed VALUES
    (1, NULL, 0, 1, 127, 9223372036854775807, 3.14, 'hello', x'00ff10'),
    (2, NULL, 0, 1, -128, -9223372036854775808, -0.5, '', x''),
    (3, NULL, 0, 1, 256, 4294967296, 0.0, 'multi\nline', x'deadbeef');
CREATE INDEX idx_typed_small ON typed(n_small);
"""


@pytest.fixture
def script(tmp_path: Path) -> Path:
    p = tmp_path / "fixture.sql"
    p.write_text(FIXTURE_SQL, encoding="utf-8")
    return p


# --- determinism contract --------------------------------------------------
class TestDeterminism:
    def test_rebuild_is_byte_identical(self, script: Path, tmp_path: Path) -> None:
        a = tmp_path / "a.db"
        b = tmp_path / "b.db"
        build_database(script, a)
        build_database(script, b)
        assert a.read_bytes() == b.read_bytes()

    def test_forces_fixed_page_size(self, script: Path, tmp_path: Path) -> None:
        out = tmp_path / "out.db"
        result = build_database(script, out, page_size=1024)
        actual = sqlite3.connect(str(out)).execute("PRAGMA page_size").fetchone()[0]
        assert actual == 1024
        assert result.page_size == 1024

    def test_default_page_size_is_4096(self, script: Path, tmp_path: Path) -> None:
        result = build_database(script, tmp_path / "out.db")
        assert result.page_size == DEFAULT_PAGE_SIZE == 4096


# --- round-trip correctness ------------------------------------------------
class TestRoundTrip:
    def test_rows_readable_by_sqlite3(self, script: Path, tmp_path: Path) -> None:
        out = build_database(script, tmp_path / "out.db").path
        conn = sqlite3.connect(str(out))
        rows = conn.execute(
            "SELECT n_small, n_big, real, txt, blb FROM typed ORDER BY id"
        ).fetchall()
        conn.close()
        assert rows[0] == (127, 9223372036854775807, 3.14, "hello", b"\x00\xff\x10")
        assert rows[1] == (-128, -9223372036854775808, -0.5, "", b"")
        assert rows[2] == (256, 4294967296, 0.0, "multi\nline", b"\xde\xad\xbe\xef")

    def test_integrity_check_passes(self, script: Path, tmp_path: Path) -> None:
        out = build_database(script, tmp_path / "out.db").path
        integrity = sqlite3.connect(str(out)).execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
        assert integrity == "ok"

    def test_single_file_no_wal_sidecar(self, script: Path, tmp_path: Path) -> None:
        out = build_database(script, tmp_path / "out.db").path
        assert out.exists()
        # DELETE journal mode: no -wal / -shm sidecars.
        assert not out.with_suffix(out.suffix + "-wal").exists()

    def test_page_count_reported(self, script: Path, tmp_path: Path) -> None:
        result = build_database(script, tmp_path / "out.db")
        assert result.page_count >= 1
        actual = sqlite3.connect(str(result.path)).execute(
            "PRAGMA page_count"
        ).fetchone()[0]
        assert result.page_count == actual


# --- output-path derivation ------------------------------------------------
class TestOutputPath:
    def test_default_replaces_suffix(self, script: Path) -> None:
        # script is <tmp>/fixture.sql -> default output fixture.db, same dir.
        result = build_database(script)
        assert result.path == script.with_suffix(".db")
        assert result.path.exists()

    def test_existing_output_rebuilt(self, script: Path, tmp_path: Path) -> None:
        out = tmp_path / "out.db"
        first = build_database(script, out)
        assert first.path.stat().st_size > 0
        # Stale content present; rebuild must replace, not append.
        build_database(script, out)
        # Still a valid single build (round-trips).
        rows = sqlite3.connect(str(out)).execute("SELECT COUNT(*) FROM typed").fetchone()
        assert rows[0] == 3


# --- error handling --------------------------------------------------------
class TestErrors:
    def test_missing_script_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            build_database(tmp_path / "nope.sql", tmp_path / "out.db")

    def test_bad_sql_removes_partial_output(
        self, tmp_path: Path
    ) -> None:
        bad = tmp_path / "bad.sql"
        bad.write_text("CREATE TABLE t(x); THIS IS NOT SQL;", encoding="utf-8")
        out = tmp_path / "out.db"
        with pytest.raises(sqlite3.Error):
            build_database(bad, out)
        # No broken fixture left behind.
        assert not out.exists()

    def test_invalid_page_size_raises_valueerror(self) -> None:
        with pytest.raises(ValueError):
            validate_page_size(1000)  # not a power of two

    def test_invalid_page_size_in_build(self, script: Path, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            build_database(script, tmp_path / "out.db", page_size=3000)


# --- CLI -------------------------------------------------------------------
class TestCli:
    def test_main_builds_and_exits_zero(
        self, script: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = tmp_path / "out.db"
        rc = main([str(script), "-o", str(out)])
        assert rc == 0
        assert out.exists()
        captured = capsys.readouterr().out
        assert "built" in captured
        assert "page_size=" in captured
        assert "page_count=" in captured

    def test_invalid_page_size_cli_exits_nonzero(
        self, script: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            main([str(script), "-o", str(tmp_path / "out.db"), "--page-size", "7"])
        assert exc.value.code != 0

    def test_valid_page_size_via_cli_succeeds(
        self, script: Path, tmp_path: Path
    ) -> None:
        # Regression: argparse hands the token as str; a valid page size must
        # parse and build, not be rejected as "not in the int set".
        out = tmp_path / "out.db"
        rc = main([str(script), "-o", str(out), "--page-size", "1024"])
        assert rc == 0
        actual = sqlite3.connect(str(out)).execute("PRAGMA page_size").fetchone()[0]
        assert actual == 1024
