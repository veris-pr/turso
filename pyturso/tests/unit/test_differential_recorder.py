"""Unit tests for tests.differential.recorder — oracle sidecar record/load.

Verified against: the expectation discipline in tests/differential/corpus/
HOWTO.md (sidecars are generated, never hand-written; round-trip must be exact).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.differential.engine import StatementResult
from tests.differential.recorder import (
    SIDECAR_SUFFIX,
    deserialize,
    expected_path,
    load_expected,
    record_expected,
    serialize,
)


# A representative mixed result list: rows, an empty-rows statement (CREATE),
# and an error class.
SAMPLE: list[StatementResult] = [
    [("1",), ("2", "3")],
    [],
    "OperationalError",
]


# --- sidecar path ----------------------------------------------------------
class TestPath:
    def test_appends_suffix(self, tmp_path: Path) -> None:
        case = tmp_path / "phase1" / "select_one.sql"
        assert expected_path(case).name == "select_one.sql" + SIDECAR_SUFFIX

    def test_stays_in_same_dir(self, tmp_path: Path) -> None:
        case = tmp_path / "phase1" / "select_one.sql"
        assert expected_path(case).parent == case.parent


# --- serialize / deserialize round-trip -----------------------------------
class TestRoundTrip:
    def test_serialize_is_json(self) -> None:
        text = serialize(SAMPLE)
        assert json.loads(text) == [[["1"], ["2", "3"]], [], "OperationalError"]

    def test_round_trip_preserves_results(self) -> None:
        assert deserialize(serialize(SAMPLE)) == SAMPLE

    def test_round_trip_restores_tuples(self) -> None:
        # JSON stores arrays as lists; load must convert rows back to tuples.
        loaded = deserialize(serialize([[("a", "b")]]))
        assert loaded == [[("a", "b")]]
        assert isinstance(loaded[0][0], tuple)

    def test_empty_rows_statement_round_trips(self) -> None:
        # CREATE TABLE → empty Rows; must survive (not collapse to nothing).
        assert deserialize(serialize([[]])) == [[]]

    def test_error_class_round_trips(self) -> None:
        assert deserialize(serialize(["IntegrityError"])) == ["IntegrityError"]

    def test_cells_with_special_chars_round_trip(self) -> None:
        # Pipes, spaces, newlines, quotes — JSON escapes them all.
        tricky: list[StatementResult] = [[("a|b", "c d", "e\nf", 'g"h')]]
        assert deserialize(serialize(tricky)) == tricky

    def test_serialize_deterministic(self) -> None:
        # Same input → identical bytes (so git diffs show only real changes).
        assert serialize(SAMPLE) == serialize(SAMPLE)


# --- record / load to disk -------------------------------------------------
class TestRecordLoad:
    def test_record_writes_sidecar(self, tmp_path: Path) -> None:
        case = tmp_path / "case.sql"
        side = record_expected(case, SAMPLE)
        assert side == expected_path(case)
        assert side.is_file()

    def test_load_returns_recorded(self, tmp_path: Path) -> None:
        case = tmp_path / "case.sql"
        record_expected(case, SAMPLE)
        assert load_expected(case) == SAMPLE

    def test_load_none_when_absent(self, tmp_path: Path) -> None:
        case = tmp_path / "case.sql"
        assert load_expected(case) is None

    def test_record_overwrites_prior(self, tmp_path: Path) -> None:
        # --record is idempotent: a re-recording replaces, not appends.
        case = tmp_path / "case.sql"
        record_expected(case, [[("old",)]])
        record_expected(case, [[("new",)]])
        assert load_expected(case) == [[("new",)]]

    def record_then_load_matches_in_memory(
        self, tmp_path: Path
    ) -> None:
        case = tmp_path / "case.sql"
        record_expected(case, SAMPLE)
        assert load_expected(case) == SAMPLE

    def test_corrupt_sidecar_raises(self, tmp_path: Path) -> None:
        # A generated file should never be malformed; JSON errors propagate.
        case = tmp_path / "case.sql"
        expected_path(case).write_text("{not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_expected(case)
