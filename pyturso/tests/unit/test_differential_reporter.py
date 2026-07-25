"""Unit tests for tests.differential.reporter — verdict logic + summary.

Verified against: the verdict decision tree in tests/differential/README.md
and HOWTO.md (PASS / DIVERGENT / NOT-IMPLEMENTED / ORACLE-DISAGREEMENT /
ERROR) and the "nonzero exit on red" contract.

judge() is a pure function over EngineOutcome values — no real engines needed.
"""

from __future__ import annotations

import pytest

from tests.differential.engine import StatementResult
from tests.differential.pyturso_adapter import EngineNotImplemented
from tests.differential.reporter import (
    DEFAULT_RED_VERDICTS,
    CaseOutcome,
    EngineOutcome,
    Summary,
    Verdict,
    exit_code,
    format_report,
    judge,
    run_engine,
    summarize,
)
from tests.differential.tursodb_adapter import AdapterError

CASE = "t"


def _rows(*rows: tuple[str, ...]) -> list[StatementResult]:
    """Build a one-statement rows result."""
    return [list(rows)]


def _ok(*rows: tuple[str, ...]) -> EngineOutcome:
    return EngineOutcome(results=_rows(*rows))


# --- PASS: oracles agree, pyturso matches ---------------------------------
class TestPass:
    def test_all_three_agree(self) -> None:
        out = judge(CASE, "SELECT 1;", _ok(("1",)), _ok(("1",)), _ok(("1",)))
        assert out.verdict is Verdict.PASS

    def test_multiset_pass_for_reordered_rows(self) -> None:
        # No ORDER BY → multiset: pyturso may return rows in a different order.
        out = judge(
            CASE,
            "SELECT * FROM t;",
            _ok(("1",), ("2",)),
            _ok(("1",), ("2",)),
            _ok(("2",), ("1",)),
        )
        assert out.verdict is Verdict.PASS

    def test_empty_rows_pass(self) -> None:
        # CREATE TABLE: empty Rows on all three.
        out = judge(
            CASE, "CREATE TABLE t(x);", EngineOutcome(results=[[]]),
            EngineOutcome(results=[[]]), EngineOutcome(results=[[]]),
        )
        assert out.verdict is Verdict.PASS


# --- DIVERGENT: oracles agree, pyturso differs ----------------------------
class TestDivergent:
    def test_pyturso_value_differs(self) -> None:
        out = judge(CASE, "SELECT 1;", _ok(("1",)), _ok(("1",)), _ok(("2",)))
        assert out.verdict is Verdict.DIVERGENT
        assert "pyturso" in out.detail

    def test_order_by_makes_order_a_divergence(self) -> None:
        # With ORDER BY, order is part of the contract: pyturso returning the
        # same rows differently ordered is now a DIVERGENT.
        out = judge(
            CASE,
            "SELECT * FROM t ORDER BY x",
            _ok(("1",), ("2",)),
            _ok(("1",), ("2",)),
            _ok(("2",), ("1",)),
        )
        assert out.verdict is Verdict.DIVERGENT


# --- NOT-IMPLEMENTED ------------------------------------------------------
class TestNotImplemented:
    def test_pyturso_not_implemented(self) -> None:
        py = EngineOutcome(error=EngineNotImplemented("no engine yet"))
        out = judge(CASE, "SELECT 1;", _ok(("1",)), _ok(("1",)), py)
        assert out.verdict is Verdict.NOT_IMPLEMENTED
        assert "no engine yet" in out.detail


# --- ORACLE-DISAGREEMENT --------------------------------------------------
class TestOracleDisagreement:
    def test_oracles_disagree_on_value(self) -> None:
        out = judge(CASE, "SELECT 1;", _ok(("1",)), _ok(("2",)), _ok(("1",)))
        assert out.verdict is Verdict.ORACLE_DISAGREEMENT

    def test_oracles_disagree_rows_vs_error(self) -> None:
        # sqlite3 returns rows, tursodb returns an error class.
        tu = EngineOutcome(results=["OperationalError"])
        out = judge(CASE, "SELECT 1;", _ok(("1",)), tu, _ok(("1",)))
        assert out.verdict is Verdict.ORACLE_DISAGREEMENT


# --- ERROR: engine-internal failures --------------------------------------
class TestError:
    def test_sqlite3_adaptererror_is_error(self) -> None:
        bad = EngineOutcome(error=AdapterError("sqlite3 blew up"))
        out = judge(CASE, "SELECT 1;", bad, _ok(("1",)), _ok(("1",)))
        assert out.verdict is Verdict.ERROR
        assert "sqlite3" in out.detail

    def test_tursodb_adaptererror_is_error(self) -> None:
        bad = EngineOutcome(error=AdapterError("tursodb crashed"))
        out = judge(CASE, "SELECT 1;", _ok(("1",)), bad, _ok(("1",)))
        assert out.verdict is Verdict.ERROR
        assert "tursodb" in out.detail

    def test_unexpected_pyturso_error_is_error_not_notimplemented(self) -> None:
        # pyturso raising something other than EngineNotImplemented is an
        # unexpected failure, distinct from honest NOT-IMPLEMENTED.
        py = EngineOutcome(error=RuntimeError("kaboom"))
        out = judge(CASE, "SELECT 1;", _ok(("1",)), _ok(("1",)), py)
        assert out.verdict is Verdict.ERROR
        assert "RuntimeError" in out.detail


# --- normalization integration --------------------------------------------
class TestNormalization:
    def test_tursodb_null_reconciled_to_pass(self) -> None:
        # sqlite3 renders NULL → "NULL"; tursodb renders NULL → "". After
        # normalization both are "NULL", so the comparison passes.
        out = judge(
            CASE,
            "SELECT NULL;",
            _ok(("NULL",)),
            _ok(("",)),  # tursodb's empty-NULL, normalized to NULL
            _ok(("NULL",)),
        )
        assert out.verdict is Verdict.PASS

    def test_tursodb_float_format_reconciled(self) -> None:
        # sqlite3 %.15g "1e+20" vs tursodb "1.00000000000000e+20" → both "1e+20".
        out = judge(
            CASE,
            "SELECT 1e20;",
            _ok(("1e+20",)),
            _ok(("1.00000000000000e+20",)),
            _ok(("1e+20",)),
        )
        assert out.verdict is Verdict.PASS


# --- run_engine exception classification ----------------------------------
class _Recording:
    """A fake Engine that returns canned results or raises a canned error."""

    def __init__(self, *, results: list[StatementResult] | None = None,
                 error: Exception | None = None) -> None:
        self._results = results
        self._error = error

    def run_script(self, sql_text: str, db_path):  # type: ignore[no-untyped-def]
        if self._error is not None:
            raise self._error
        return self._results


class TestRunEngine:
    def test_success(self) -> None:
        eng = _Recording(results=[[("1",)]])
        out = run_engine(eng, "SELECT 1;", None)
        assert out.ran and out.results == [[("1",)]]

    def test_not_implemented_captured(self) -> None:
        eng = _Recording(error=EngineNotImplemented("x"))
        out = run_engine(eng, "SELECT 1;", None)
        assert not out.ran and isinstance(out.error, EngineNotImplemented)

    def test_adaptererror_captured(self) -> None:
        eng = _Recording(error=AdapterError("crash"))
        out = run_engine(eng, "SELECT 1;", None)
        assert not out.ran and isinstance(out.error, AdapterError)

    def test_unexpected_exception_captured(self) -> None:
        eng = _Recording(error=ValueError("bad"))
        out = run_engine(eng, "SELECT 1;", None)
        assert not out.ran and isinstance(out.error, ValueError)


# --- summary + exit code --------------------------------------------------
class TestSummaryAndExit:
    def test_counts_per_verdict(self) -> None:
        outcomes = [
            CaseOutcome("a", Verdict.PASS),
            CaseOutcome("b", Verdict.PASS),
            CaseOutcome("c", Verdict.DIVERGENT),
            CaseOutcome("d", Verdict.NOT_IMPLEMENTED),
        ]
        s = summarize(outcomes)
        assert s.counts[Verdict.PASS] == 2
        assert s.counts[Verdict.DIVERGENT] == 1
        assert s.counts[Verdict.NOT_IMPLEMENTED] == 1
        assert s.total == 4

    def test_exit_zero_when_no_red(self) -> None:
        s = summarize([CaseOutcome("a", Verdict.PASS),
                       CaseOutcome("b", Verdict.NOT_IMPLEMENTED)])
        assert exit_code(s) == 0

    def test_exit_nonzero_on_divergent(self) -> None:
        s = summarize([CaseOutcome("a", Verdict.PASS),
                       CaseOutcome("b", Verdict.DIVERGENT)])
        assert exit_code(s) == 1

    def test_exit_nonzero_on_error(self) -> None:
        s = summarize([CaseOutcome("a", Verdict.ERROR)])
        assert exit_code(s) == 1

    def test_not_implemented_red_only_when_configured(self) -> None:
        s = summarize([CaseOutcome("a", Verdict.NOT_IMPLEMENTED)])
        assert exit_code(s) == 0
        assert exit_code(s, extra_red=[Verdict.NOT_IMPLEMENTED]) == 1

    def test_oracle_disagreement_not_red_by_default(self) -> None:
        s = summarize([CaseOutcome("a", Verdict.ORACLE_DISAGREEMENT)])
        assert exit_code(s) == 0

    def test_default_red_set_contents(self) -> None:
        assert DEFAULT_RED_VERDICTS == frozenset(
            {Verdict.DIVERGENT, Verdict.ERROR}
        )


# --- quarantine reporting (#12) ------------------------------------------
class TestQuarantineReport:
    def _summary_with(self, *verdicts: Verdict) -> Summary:
        return summarize(
            CaseOutcome(f"case{i}", v) for i, v in enumerate(verdicts)
        )

    def test_report_has_quarantine_section(self) -> None:
        main = self._summary_with(Verdict.PASS, Verdict.NOT_IMPLEMENTED)
        q = [CaseOutcome("quarantined_case", Verdict.ORACLE_DISAGREEMENT,
                         "sqlite3 vs tursodb")]
        report = format_report(main, q)
        assert "Quarantine: 1 case(s)" in report
        assert "quarantined_case" in report

    def test_report_no_quarantine_section_when_empty(self) -> None:
        report = format_report(self._summary_with(Verdict.PASS), [])
        assert "Quarantine" not in report

    def test_quarantine_excluded_from_main_summary(self) -> None:
        # The defining contract: quarantined cases never count toward the main
        # tally (green or red). Their outcomes are reported but not in `main`.
        main = self._summary_with(Verdict.PASS)
        q = [CaseOutcome("q1", Verdict.ORACLE_DISAGREEMENT)]
        # exit_code looks only at the main summary; quarantine is separate.
        assert exit_code(main) == 0
        # And the quarantine list is not in main.cases.
        assert all(c.name != "q1" for c in main.cases)
        # format_report shows it in its own section, not in main counts.
        report = format_report(main, q)
        assert report.count("ORACLE-DISAGREEMENT") == 1  # only in quarantine

    def test_quarantine_case_that_now_passes_is_still_not_green(self) -> None:
        # A quarantined case that now agrees is informational (could promote
        # back), not green/red — it stays out of the main tally.
        main = self._summary_with(Verdict.PASS)
        q = [CaseOutcome("fixed_now", Verdict.PASS)]
        assert exit_code(main) == 0
        assert len(main.cases) == 1  # main unaffected
        report = format_report(main, q)
        assert "fixed_now" in report
        assert "Quarantine: 1 case(s)" in report
