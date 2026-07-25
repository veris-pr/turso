"""Unit tests for tests.differential.discover — corpus discovery + filters.

Verified against: the corpus layout in tests/differential/README.md
(corpus/<phaseN_topic>/<case>.sql) and the -k / --phase filtering in HOWTO.md.
"""

from __future__ import annotations

from pathlib import Path

from tests.differential.discover import (
    QUARANTINE_DIR,
    DiscoveredCase,
    discover_corpus,
    discover_quarantine,
)


def _build_corpus(tmp_path: Path) -> Path:
    """Build a tiny corpus tree mirroring the real layout."""
    root = tmp_path / "corpus"
    (root / "phase1_read").mkdir(parents=True)
    (root / "phase5_select").mkdir(parents=True)
    (root / QUARANTINE_DIR).mkdir(parents=True)
    (root / "phase1_read" / "select_one.sql").write_text("SELECT 1;")
    (root / "phase1_read" / "select_two.sql").write_text("SELECT 2;")
    (root / "phase5_select" / "where_clause.sql").write_text("SELECT 1 WHERE 1;")
    (root / QUARANTINE_DIR / "bad_oracle.sql").write_text("SELECT 1;")
    return root


# --- discovery -------------------------------------------------------------
class TestDiscover:
    def test_finds_all_non_quarantine_cases(self, tmp_path: Path) -> None:
        root = _build_corpus(tmp_path)
        cases = discover_corpus(root)
        rels = [c.rel for c in cases]
        assert rels == [
            "phase1_read/select_one.sql",
            "phase1_read/select_two.sql",
            "phase5_select/where_clause.sql",
        ]

    def test_excludes_quarantine(self, tmp_path: Path) -> None:
        root = _build_corpus(tmp_path)
        cases = discover_corpus(root)
        assert all(QUARANTINE_DIR not in c.rel for c in cases)

    def test_missing_corpus_returns_empty(self, tmp_path: Path) -> None:
        assert discover_corpus(tmp_path / "nope") == []

    def test_sorted_stable(self, tmp_path: Path) -> None:
        root = _build_corpus(tmp_path)
        cases = discover_corpus(root)
        assert [c.rel for c in cases] == sorted(c.rel for c in cases)

    def test_case_fields(self, tmp_path: Path) -> None:
        root = _build_corpus(tmp_path)
        case = next(
            c for c in discover_corpus(root) if c.name == "select_one"
        )
        assert case.phase == "phase1_read"
        assert case.name == "select_one"
        assert case.rel == "phase1_read/select_one.sql"
        assert case.path.is_file()


# --- -k substring filter ---------------------------------------------------
class TestKFilter:
    def test_k_matches_case_name(self, tmp_path: Path) -> None:
        root = _build_corpus(tmp_path)
        # k is a substring over the full rel path, so "select" matches both
        # select_* cases AND where_clause (whose phase dir is phase5_select).
        cases = discover_corpus(root, k="select")
        names = sorted(c.name for c in cases)
        assert names == ["select_one", "select_two", "where_clause"]

    def test_k_unique_name_matches_one(self, tmp_path: Path) -> None:
        cases = discover_corpus(_build_corpus(tmp_path), k="select_one")
        assert [c.name for c in cases] == ["select_one"]

    def test_k_matches_phase_dir(self, tmp_path: Path) -> None:
        # -k is a substring over the full rel path, so it matches the phase too.
        cases = discover_corpus(_build_corpus(tmp_path), k="phase5")
        assert [c.name for c in cases] == ["where_clause"]

    def test_k_case_insensitive(self, tmp_path: Path) -> None:
        cases = discover_corpus(_build_corpus(tmp_path), k="WHERE")
        assert [c.name for c in cases] == ["where_clause"]

    def test_k_no_match_returns_empty(self, tmp_path: Path) -> None:
        assert discover_corpus(_build_corpus(tmp_path), k="zzz") == []


# --- --phase filter --------------------------------------------------------
class TestPhaseFilter:
    def test_phase_matches_dir_substring(self, tmp_path: Path) -> None:
        cases = discover_corpus(_build_corpus(tmp_path), phase="phase1")
        assert sorted(c.name for c in cases) == ["select_one", "select_two"]

    def test_phase_case_insensitive(self, tmp_path: Path) -> None:
        cases = discover_corpus(_build_corpus(tmp_path), phase="PHASE5")
        assert [c.name for c in cases] == ["where_clause"]

    def test_phase_and_k_compose_as_and(self, tmp_path: Path) -> None:
        # Both must pass: phase1 AND name contains "one".
        cases = discover_corpus(
            _build_corpus(tmp_path), phase="phase1", k="one"
        )
        assert [c.name for c in cases] == ["select_one"]


# --- quarantine discovery (#12) -------------------------------------------
class TestQuarantine:
    def test_quarantine_listed_separately(self, tmp_path: Path) -> None:
        root = _build_corpus(tmp_path)
        q = discover_quarantine(root)
        assert len(q) == 1
        assert q[0].name == "bad_oracle"
        assert QUARANTINE_DIR in q[0].rel

    def test_quarantine_empty_when_none(self, tmp_path: Path) -> None:
        root = tmp_path / "corpus"
        (root / "phase1_read").mkdir(parents=True)
        (root / "phase1_read" / "a.sql").write_text("SELECT 1;")
        assert discover_quarantine(root) == []
