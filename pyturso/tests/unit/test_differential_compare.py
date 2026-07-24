"""Unit tests for tests.differential.compare — multiset/ordered comparison.

Verified against: tests/differential/README.md (unordered→multiset,
ordered-by-ORDER-BY→sequence; errors compared by class).
"""

from __future__ import annotations

from tests.differential.compare import (
    is_ordered_query,
    result_equal,
    results_equal,
    rows_equal,
)
from tests.differential.engine import StatementResult

R = [("1",), ("2",), ("3",)]


# --- multiset (default: no ORDER BY) --------------------------------------
class TestMultiset:
    def test_same_order_equal(self) -> None:
        assert rows_equal(R, R, ordered=False)

    def test_different_order_equal_as_multiset(self) -> None:
        # The core invariant: SQL leaves order unspecified, so two correct
        # engines may return the same rows differently ordered.
        assert rows_equal([("1",), ("2",)], [("2",), ("1",)], ordered=False)

    def test_duplicate_rows_counted(self) -> None:
        # Multiset, not set: duplicates matter.
        assert not rows_equal([("1",), ("1",)], [("1",)], ordered=False)
        assert rows_equal([("1",), ("1",)], [("1",), ("1",)], ordered=False)

    def test_different_rows_not_equal(self) -> None:
        assert not rows_equal([("1",)], [("2",)], ordered=False)

    def test_empty_equal_empty(self) -> None:
        assert rows_equal([], [], ordered=False)


# --- ordered (statement has ORDER BY) -------------------------------------
class TestOrdered:
    def test_same_order_equal(self) -> None:
        assert rows_equal(R, R, ordered=True)

    def test_different_order_NOT_equal(self) -> None:
        # With ORDER BY, order is part of the contract.
        assert not rows_equal([("1",), ("2",)], [("2",), ("1",)], ordered=True)

    def test_duplicates_still_counted(self) -> None:
        assert rows_equal([("1",), ("1",)], [("1",), ("1",)], ordered=True)
        assert not rows_equal([("1",), ("1",)], [("1",), ("2",)], ordered=True)


# --- result dispatch (rows / error / mixed) -------------------------------
class TestResultEqual:
    def test_both_rows_uses_ordered_flag(self) -> None:
        a = [("1",), ("2",)]
        assert result_equal(a, [("2",), ("1",)], ordered=False)
        assert not result_equal(a, [("2",), ("1",)], ordered=True)

    def test_both_same_error_class_equal(self) -> None:
        assert result_equal("OperationalError", "OperationalError", ordered=False)

    def test_different_error_class_not_equal(self) -> None:
        assert not result_equal("OperationalError", "IntegrityError", ordered=False)

    def test_rows_vs_error_is_divergence(self) -> None:
        assert not result_equal([("1",)], "OperationalError", ordered=False)
        assert not result_equal("OperationalError", [("1",)], ordered=False)

    def test_empty_rows_vs_empty_rows_equal(self) -> None:
        # Non-row statements (CREATE) → empty Rows on both engines.
        assert result_equal([], [], ordered=False)


# --- whole-script comparison ----------------------------------------------
class TestResultsEqual:
    def test_identical_scripts_equal(self) -> None:
        a: list[StatementResult] = [[("1",)], [], "OperationalError"]
        assert results_equal(a, a, [True, False, False])

    def test_length_mismatch_is_divergence(self) -> None:
        # One engine stopped early at an error the other didn't.
        short: list[StatementResult] = [[("1",)], "OperationalError"]
        long_: list[StatementResult] = [[("1",)], [], [("2",)]]
        assert not results_equal(short, long_, [False, False, False])

    def test_flags_length_mismatch_is_divergence(self) -> None:
        sa = [[("1",)]]
        assert not results_equal(sa, sa, [False, False])

    def test_per_statement_ordered_flag_respected(self) -> None:
        # Statement 0 ordered (must match in order); statement 1 unordered.
        a: list[StatementResult] = [[("1",), ("2",)], [("b",), ("a",)]]
        b: list[StatementResult] = [[("2",), ("1",)], [("a",), ("b",)]]
        # stmt0 ordered → differ; stmt1 unordered → same.
        assert not results_equal(a, b, [True, False])
        # Both unordered → both same-as-multiset → equal.
        assert results_equal(a, b, [False, False])


# --- ORDER BY heuristic detection -----------------------------------------
class TestIsOrderedQuery:
    def test_plain_order_by(self) -> None:
        assert is_ordered_query("SELECT * FROM t ORDER BY x")

    def test_lowercase(self) -> None:
        assert is_ordered_query("select * from t order by x")

    def test_multiline_and_extra_whitespace(self) -> None:
        assert is_ordered_query("SELECT *\nFROM t\nORDER   BY\nx")

    def test_no_order_by(self) -> None:
        assert not is_ordered_query("SELECT * FROM t WHERE x = 1")

    def test_group_by_is_not_ordered(self) -> None:
        assert not is_ordered_query("SELECT x, COUNT(*) FROM t GROUP BY x")

    def test_order_by_inside_string_literal_not_detected(self) -> None:
        # Conservative: a literal containing the words must not trigger.
        assert not is_ordered_query("SELECT 'ORDER BY foo' AS s")

    def test_order_by_inside_quoted_identifier_not_detected(self) -> None:
        assert not is_ordered_query('SELECT "ORDER BY" FROM t')

    def test_order_inside_identifier_not_false_positive(self) -> None:
        # "REORDER" / "BYPASS" word boundaries.
        assert not is_ordered_query("SELECT REORDER FROM t")
        assert not is_ordered_query("SELECT * FROM t WHERE x = BYPASS")

    def test_order_by_in_subquery_detected_conservatively(self) -> None:
        # Documented conservative behaviour: a subquery ORDER BY is reported.
        # Only a false-positive, which is safe (ordered compare passes for
        # matching rows). Phase 3 parser lifts this.
        assert is_ordered_query("SELECT * FROM (SELECT * FROM t ORDER BY x)")
