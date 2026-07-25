"""Unit tests for tests.differential.engine — the adapter protocol + result types.

Verified against: tests/differential/README.md (per-statement, errors-by-class
contract) and the run_script signature in tests/differential/TODO.md.
"""

from __future__ import annotations

from pathlib import Path

from tests.differential.engine import (
    Engine,
    ErrorClass,
    FixtureError,
    Rows,
    SqlValue,
    StatementResult,
    render_cell,
)

# --- result-type model -----------------------------------------------------
class TestResultTypes:
    def test_rows_is_list_of_string_tuples(self) -> None:
        # Rows are rendered text cells (Design B): str per cell, tuple per row.
        rows: Rows = [("1",), ("NULL", "x"), ("1.5", "x'00ff'", "0")]
        assert isinstance(rows, list)
        assert all(isinstance(r, tuple) for r in rows)
        assert all(isinstance(c, str) for r in rows for c in r)

    def test_empty_rows_represent_non_row_statement(self) -> None:
        # CREATE/INSERT contribute an empty Rows entry, not a skip, so the
        # per-statement index stays aligned across engines.
        empty: Rows = []
        assert empty == []

    def test_errorclass_is_str(self) -> None:
        err: ErrorClass = "OperationalError"
        assert isinstance(err, str)

    def test_sqlvalue_covers_all_sqlite_dynamic_types(self) -> None:
        # Raw typed input values that render_cell turns into canonical text.
        values: list[SqlValue] = [1, 1.5, "txt", b"blob", None]
        assert len(values) == 5

    def test_statement_result_distinguishable_at_runtime(self) -> None:
        # The whole point: rows (list) vs error (str) are told apart by type,
        # so normalization/comparison can dispatch without ambiguity.
        rows: StatementResult = [("1",)]
        err: StatementResult = "IntegrityError"
        assert isinstance(rows, list)
        assert isinstance(err, str)
        assert not isinstance(rows, str)
        assert not isinstance(err, list)


# --- Protocol structural conformance --------------------------------------
class _GoodEngine:
    """A minimal class satisfying Engine: has run_script with the right shape."""

    def run_script(
        self, sql_text: str, db_path: Path | None
    ) -> list[StatementResult]:
        # Design B: text cells. Return one Rows (a list of one row tuple).
        return [[("1",)]]


class _NoRunScript:
    """Wrong shape: no run_script method."""

    def execute(self, sql: str) -> None:
        return None


class TestProtocolConformance:
    def test_conforming_object_is_an_engine(self) -> None:
        assert isinstance(_GoodEngine(), Engine)

    def test_nonconforming_object_is_not_an_engine(self) -> None:
        assert not isinstance(_NoRunScript(), Engine)

    def test_none_is_not_an_engine(self) -> None:
        assert not isinstance(None, Engine)

    def test_protocol_is_runtime_checkable(self) -> None:
        # The decorator was applied: a structural isinstance check is possible.
        assert getattr(Engine, "_is_runtime_protocol", False) is True


# --- FixtureError ----------------------------------------------------------
class TestFixtureError:
    def test_missing_path_message_names_it(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.db"
        err = FixtureError(missing)
        assert err.db_path == missing
        assert str(missing) in str(err)

    def test_none_path_described_as_in_memory(self) -> None:
        err = FixtureError(None)
        assert err.db_path is None
        assert "in-memory" in str(err)

    def test_is_an_exception(self) -> None:
        assert issubclass(FixtureError, Exception)


# --- render_cell: canonical renderer for type-aware adapters -------------
class TestRenderCell:
    def test_none_is_null_literal(self) -> None:
        assert render_cell(None) == "NULL"

    def test_int_is_decimal(self) -> None:
        assert render_cell(42) == "42"
        assert render_cell(-7) == "-7"

    def test_bool_coerced_to_0_1(self) -> None:
        # SQLite has no bool; the int subclass must not render as True/False.
        assert render_cell(True) == "1"
        assert render_cell(False) == "0"

    def test_float_is_15g(self) -> None:
        assert render_cell(1.5) == "1.5"
        assert render_cell(0.1) == "0.1"
        # %.15g trims trailing precision noise.
        assert render_cell(1.0 / 3.0) == "0.333333333333333"

    def test_text_is_verbatim(self) -> None:
        assert render_cell("hello") == "hello"
        assert render_cell("") == ""
        assert render_cell("NULL") == "NULL"  # known ambiguity, documented

    def test_blob_is_lowerhex(self) -> None:
        assert render_cell(b"\x00\xff") == "x'00ff'"
        assert render_cell(b"") == "x''"


# --- end-to-end shape of one conforming run -------------------------------
class TestConformingRunShape:
    def test_good_engine_returns_statement_result_list(self) -> None:
        eng: Engine = _GoodEngine()
        out = eng.run_script("SELECT 1;", None)
        assert isinstance(out, list)
        assert len(out) == 1
        # The single entry is Rows (a list), not an ErrorClass (a str).
        assert isinstance(out[0], list)
        assert out[0] == [("1",)]
