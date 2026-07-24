"""Unit tests for tests.differential.run — the harness entry point (#13).

Drives ``main()`` against a throwaway temp corpus so the Phase 0 gate is
exercised in-process: discovery, frontmatter, the three engines, judging,
reporting, and the exit code. tursodb is optional here (``--sqlite3-only``)
so the test never depends on a built binary; the full three-way path is the
manual Phase 0 gate, run separately.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.differential.run import main


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    (root / "phase1_read").mkdir(parents=True)
    (root / "phase1_read" / "literals.sql").write_text(
        "SELECT 1, 1.5, NULL, 'hi';\nSELECT 1 WHERE 1=1;\n"
    )
    return root


# --- the Phase 0 exit criterion (sqlite3-only, no binary needed) ---------
class TestPhase0GateSqliteOnly:
    def test_runs_and_exits_zero_when_not_implemented_not_red(
        self, corpus: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main([str(corpus), "--sqlite3-only"])
        out = capsys.readouterr().out
        # The defining exit criterion: trivial corpus runs, pyturso reports
        # NOT-IMPLEMENTED without crashing, exit 0 (not red by default).
        assert rc == 0
        assert "NOT-IMPLEMENTED" in out
        assert "literals" in out

    def test_not_implemented_red_flag_makes_exit_nonzero(
        self, corpus: Path
    ) -> None:
        rc = main([str(corpus), "--sqlite3-only", "--not-implemented-red"])
        assert rc == 1

    def test_missing_corpus_exits_zero(self, tmp_path: Path) -> None:
        # No cases → empty summary → exit 0 (not a crash).
        rc = main([str(tmp_path / "nope"), "--sqlite3-only"])
        assert rc == 0


# --- -k / --phase filtering at the run level ------------------------------
class TestFilters:
    def test_k_no_match_runs_no_cases(
        self, corpus: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main([str(corpus), "--sqlite3-only", "-k", "zzz"])
        assert rc == 0
        assert "0 case(s)" in capsys.readouterr().out

    def test_phase_match_runs_the_case(
        self, corpus: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main([str(corpus), "--sqlite3-only", "--phase", "phase1"])
        assert "literals" in capsys.readouterr().out


# --- report shape ---------------------------------------------------------
class TestReport:
    def test_report_has_summary_counts(
        self, corpus: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main([str(corpus), "--sqlite3-only"])
        out = capsys.readouterr().out
        assert "Differential report" in out
        assert "Summary:" in out
        assert "NOT-IMPLEMENTED" in out