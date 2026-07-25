"""run — the three-way harness entry point.

Ports: scripts/diff.sh (spirit); assembles the Phase 0 modules: discover,
frontmatter, mkdb (fixtures), the three adapters, reporter.
Phase: 0
Status: IMPLEMENTED (Phase 0 gate).

Usage::

    python -m tests.differential.run [corpus_dir] [-k SUBSTR] [--phase SUBSTR]
                                       [--record] [--not-implemented-red]
                                       [--sqlite3-only]

Runs every discovered case through sqlite3, tursodb, and pyturso, normalizes
and compares, prints a per-case verdict + summary, and exits nonzero on red
(DIVERGENT / ERROR; plus NOT-IMPLEMENTED when ``--not-implemented-red``).

The Phase 0 exit criterion (PLAN.md): a trivial corpus runs, sqlite3≡tursodb on
it, and pyturso reports NOT-IMPLEMENTED without crashing. This gate is the
first real exercise of the harness end to end; everything before it was the
building blocks.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .discover import discover_corpus, discover_quarantine
from .frontmatter import parse_frontmatter
from .pyturso_adapter import PytursoEngine
from .reporter import (
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
from .sqlite3_adapter import Sqlite3Engine
from .tursodb_adapter import TursodbEngine

#: Default corpus location relative to the harness package.
_DEFAULT_CORPUS: Path = Path(__file__).resolve().parent / "corpus"

#: Default fixture-cache directory: ``corpus/.fixtures``. mkdb builds .db
#: binaries here; they are gitignored (*.db in root .gitignore) so the cache
#: is rebuilt on demand and never committed.
_DEFAULT_FIXTURES: Path = Path(__file__).resolve().parent / "corpus" / ".fixtures"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tests.differential.run",
        description="Three-way differential harness (sqlite3 / tursodb / pyturso).",
    )
    parser.add_argument(
        "corpus_dir",
        nargs="?",
        default=str(_DEFAULT_CORPUS),
        help=f"corpus root (default: {_DEFAULT_CORPUS})",
    )
    parser.add_argument("-k", default=None, help="case-name substring filter")
    parser.add_argument("--phase", default=None, help="phase-dir substring filter")
    parser.add_argument(
        "--record",
        action="store_true",
        help="(re)record oracle sidecars from sqlite3 output",
    )
    parser.add_argument(
        "--not-implemented-red",
        action="store_true",
        help="treat NOT-IMPLEMENTED as red (default: expected through Phase 4)",
    )
    parser.add_argument(
        "--sqlite3-only",
        action="store_true",
        help="skip tursodb (use sqlite3 as the sole oracle; for envs without "
        "the tursodb binary)",
    )
    args = parser.parse_args(argv)

    corpus = Path(args.corpus_dir)
    cases = discover_corpus(corpus, k=args.k, phase=args.phase)
    q_cases = discover_quarantine(corpus)

    sqlite3_engine = Sqlite3Engine()
    tursodb_engine = TursodbEngine()  # resolves TURSODB_BIN / cargo at run time
    pyturso_engine = PytursoEngine()

    main_outcomes: list[CaseOutcome] = []
    quarantine_outcomes: list[CaseOutcome] = []

    for case in cases:
        outcome = _run_case(
            case.path,
            sqlite3_engine,
            tursodb_engine,
            pyturso_engine,
            args.sqlite3_only,
        )
        main_outcomes.append(outcome)

    # Quarantined cases are informational; run them but report separately.
    for case in q_cases:
        quarantine_outcomes.append(
            _run_case(
                case.path,
                sqlite3_engine,
                tursodb_engine,
                pyturso_engine,
                args.sqlite3_only,
                is_quarantine=True,
            )
        )

    summary = summarize(main_outcomes)
    report = format_report(summary, quarantine_outcomes)
    print(report, end="")

    extra_red = [Verdict.NOT_IMPLEMENTED] if args.not_implemented_red else []
    return exit_code(summary, extra_red=extra_red)


def _run_case(
    case_path: Path,
    sqlite3_engine: Sqlite3Engine,
    tursodb_engine: TursodbEngine,
    pyturso_engine: PytursoEngine,
    sqlite3_only: bool,
    *,
    is_quarantine: bool = False,
) -> CaseOutcome:
    """Run one case through the three engines and judge it."""
    sql_text = case_path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(sql_text)

    fixture = _resolve_fixture(frontmatter.fixture)

    sqlite3_out = run_engine(sqlite3_engine, body, fixture)
    if sqlite3_only:
        # sqlite3 as the sole oracle: tursodb outcome mirrors sqlite3 so the
        # oracles trivially "agree", and the comparison reduces to sqlite3 vs
        # pyturso. This is the documented fallback for environments without
        # the tursodb binary.
        tursodb_out = sqlite3_out
    else:
        tursodb_out = run_engine(tursodb_engine, body, fixture)
    pyturso_out = run_engine(pyturso_engine, body, fixture)

    name = case_path.stem if not is_quarantine else f"[quarantine] {case_path.stem}"
    return judge(name, body, sqlite3_out, tursodb_out, pyturso_out)


def _resolve_fixture(fixture_name: str | None) -> Path | None:
    """Resolve a fixture name to a built .db path, building it on demand.

    ``None`` → in-memory (no fixture). Otherwise the fixture is built into the
    fixtures cache from its ``.sql`` source if missing or stale. Returns the
    path to the built ``.db``.
    """
    if fixture_name is None:
        return None
    from tools.mkdb import build_database

    src = _DEFAULT_FIXTURES / f"{fixture_name}.sql" if "." not in fixture_name \
        else _DEFAULT_FIXTURES / fixture_name
    # Allow fixture scripts to live alongside the case too (relative to
    # corpus root) — but the canonical home is the fixtures cache.
    if not src.is_file():
        # Fall back to corpus/.fixtures/<name>.sql already tried; if still
        # missing, return None so the engines run in-memory (a detectable
        # harness gap, not a crash).
        return None
    out = src.with_suffix(".db")
    build_database(src, out)
    return out


if __name__ == "__main__":  # pragma: no cover - entry point
    sys.exit(main())