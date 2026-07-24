"""reporter — per-case verdicts and the summary the harness exits on.

Ports: the verdict vocabulary in tests/differential/README.md and HOWTO.md
(PASS / DIVERGENT / NOT-IMPLEMENTED / ORACLE-DISAGREEMENT / ERROR) plus the
"nonzero exit on red" CI contract.
Phase: 0
Status: IMPLEMENTED.

This module is the judgement core of the harness. ``run.py`` (#10) drives
discovery and iteration; the reporter turns three engines' outcomes on one
case into a single :class:`Verdict`, then rolls many case outcomes into a
:class:`Summary` and an exit code.

Verdict decision tree (one case, three engines: sqlite3 oracle, tursodb
oracle, pyturso subject):

  1. Either *oracle* (sqlite3 / tursodb) raised an adapter/fixture/unexpected
     error → :data:`Verdict.ERROR`. The comparison cannot be trusted; this is a
     harness or engine-internal failure, not a SQL result. (pyturso's
     :class:`EngineNotImplemented` is explicitly NOT an error — see step 3.)
  2. Both oracles ran but disagree (rows or error-class differ, or one errored
     while the other returned rows) → :data:`Verdict.ORACLE_DISAGREEMENT`. The
     case is suspect; it is quarantined and (if turso looks wrong) reported
     upstream. pyturso's verdict is moot here.
  3. Oracles agree (the common, healthy case):
       - pyturso raised :class:`EngineNotImplemented` →
         :data:`Verdict.NOT_IMPLEMENTED` (honest, partial — expected through
         Phase 4).
       - pyturso ran and matches the oracle → :data:`Verdict.PASS`.
       - pyturso ran and differs → :data:`Verdict.DIVERGENT` (a red parity gate
         for the owning phase).

Exit-code policy ("red"): :data:`Verdict.DIVERGENT` and :data:`Verdict.ERROR`
are red by default. :data:`Verdict.NOT_IMPLEMENTED` is red only when configured
(by a phase gate that has closed the relevant scope); :data:`Verdict.PASS` and
:data:`Verdict.ORACLE_DISAGREEMENT` are never red. ``run.py`` sets the policy
per run; the Phase 0 gate (#13) treats NOT-IMPLEMENTED as expected (not red).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable

from .compare import is_ordered_query, results_equal
from .engine import Engine, StatementResult
from .normalize import normalize_results
from .pyturso_adapter import EngineNotImplemented
from .sqlsplit import split_sql_script
from .tursodb_adapter import AdapterError

__all__ = [
    "Verdict",
    "EngineOutcome",
    "CaseOutcome",
    "Summary",
    "run_engine",
    "judge",
    "summarize",
    "format_report",
    "exit_code",
    "DEFAULT_RED_VERDICTS",
]


class Verdict(str, Enum):
    """A single case's outcome. ``str`` mixin so values serialize plainly."""

    PASS = "PASS"
    DIVERGENT = "DIVERGENT"
    NOT_IMPLEMENTED = "NOT-IMPLEMENTED"
    ORACLE_DISAGREEMENT = "ORACLE-DISAGREEMENT"
    ERROR = "ERROR"


#: Verdicts that make the run red (nonzero exit) by default. NOT-IMPLEMENTED
#: is intentionally absent: through Phase 4 it is the expected honest status,
#: not a regression. A phase gate may add it via the ``extra_red`` argument.
DEFAULT_RED_VERDICTS: frozenset[Verdict] = frozenset(
    {Verdict.DIVERGENT, Verdict.ERROR}
)


@dataclass
class EngineOutcome:
    """What one engine produced for a case.

    Exactly one of ``results`` / ``error`` is set:
      - ``results``: the engine ran and returned per-statement results.
      - ``error``: the engine raised. Its type classifies the verdict:
        :class:`EngineNotImplemented` (pyturso scope), :class:`AdapterError`
        / :class:`FixtureError` (engine-internal / setup), or anything else
        (unexpected → ERROR).
    """

    results: list[StatementResult] | None = None
    error: Exception | None = None

    @property
    def ran(self) -> bool:
        """True iff the engine produced results (did not raise)."""
        return self.error is None


@dataclass
class CaseOutcome:
    """One case's verdict plus a human detail line for the report."""

    name: str
    verdict: Verdict
    detail: str = ""


@dataclass
class Summary:
    """Roll-up of many case outcomes: per-verdict counts and the case list."""

    counts: Counter[Verdict] = field(default_factory=Counter)
    cases: list[CaseOutcome] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def run_engine(engine: Engine, sql_text: str, db_path: Path | None) -> EngineOutcome:
    """Run one engine on one case, catching every exception into an outcome.

    Classifies the exception by type so :func:`judge` can route it to the right
    verdict without try/except of its own. Returns a :class:`EngineOutcome`
    whose ``results`` is set on success or whose ``error`` holds the exception.
    """
    try:
        results = engine.run_script(sql_text, db_path)
    except EngineNotImplemented as exc:
        return EngineOutcome(error=exc)
    except (AdapterError, Exception) as exc:  # noqa: BLE001 — harness must not crash
        # AdapterError (timeout/crash/missing binary) and FixtureError land here
        # too; the bare Exception arm catches any unexpected adapter failure so a
        # single bad case never aborts the whole corpus run.
        return EngineOutcome(error=exc)
    return EngineOutcome(results=results)


def judge(
    case_name: str,
    sql_body: str,
    sqlite3_out: EngineOutcome,
    tursodb_out: EngineOutcome,
    pyturso_out: EngineOutcome,
) -> CaseOutcome:
    """Decide one case's verdict from the three engines' outcomes.

    See module docstring for the decision tree. ``sql_body`` is the case's SQL
    (front-matter stripped); ordered flags are derived per statement via
    :func:`is_ordered_query`.
    """
    # Step 1: an oracle engine-internal failure is ERROR — comparison untrusted.
    # (pyturso's EngineNotImplemented is NOT an error; it routes via step 3.)
    for who, out in (("sqlite3", sqlite3_out), ("tursodb", tursodb_out)):
        if not out.ran:
            return CaseOutcome(
                case_name,
                Verdict.ERROR,
                f"{who} raised {type(out.error).__name__}: {out.error}",
            )

    flags = _ordered_flags(sql_body)
    s3 = normalize_results(sqlite3_out.results or [])
    tu = normalize_results(tursodb_out.results or [])

    # Step 2: oracle disagreement.
    if not results_equal(s3, tu, flags):
        return CaseOutcome(
            case_name,
            Verdict.ORACLE_DISAGREEMENT,
            "sqlite3 and tursodb disagree; case quarantined",
        )

    # Step 3: oracles agree — judge pyturso against them.
    oracle = s3  # == tu
    if not pyturso_out.ran:
        if isinstance(pyturso_out.error, EngineNotImplemented):
            return CaseOutcome(
                case_name,
                Verdict.NOT_IMPLEMENTED,
                str(pyturso_out.error),
            )
        # pyturso raised something other than not-implemented → ERROR.
        return CaseOutcome(
            case_name,
            Verdict.ERROR,
            f"pyturso raised {type(pyturso_out.error).__name__}: "
            f"{pyturso_out.error}",
        )

    py = normalize_results(pyturso_out.results or [])
    if results_equal(oracle, py, flags):
        return CaseOutcome(case_name, Verdict.PASS)
    return CaseOutcome(
        case_name,
        Verdict.DIVERGENT,
        "pyturso differs from the oracle",
    )


def _ordered_flags(sql_body: str) -> list[bool]:
    """One ``ordered`` flag per statement in ``sql_body`` (ORDER BY heuristic)."""
    return [is_ordered_query(stmt) for stmt in split_sql_script(sql_body)]


def summarize(outcomes: Iterable[CaseOutcome]) -> Summary:
    """Roll case outcomes into a :class:`Summary` with per-verdict counts."""
    cases = list(outcomes)
    counts: Counter[Verdict] = Counter(o.verdict for o in cases)
    return Summary(counts=counts, cases=cases)


def exit_code(
    summary: Summary,
    *,
    extra_red: Iterable[Verdict] = (),
) -> int:
    """Return the process exit code for a summary.

    Red verdicts (default :data:`DEFAULT_RED_VERDICTS` plus any ``extra_red``,
    e.g. NOT-IMPLEMENTED when a phase gate closes its scope) make the run exit
    nonzero. Returns 1 if any red case is present, else 0.

    Quarantined cases never reach here: the harness keeps them out of the
    main :class:`Summary` (they are reported separately via
    :func:`format_report` and never counted green or red).
    """
    red = DEFAULT_RED_VERDICTS | frozenset(extra_red)
    return 1 if any(c.verdict in red for c in summary.cases) else 0


def format_report(
    summary: Summary,
    quarantine: list[CaseOutcome],
) -> str:
    """Format the human-readable report: main cases, then quarantine section.

    Quarantined cases are shown in their own section so they are visibly
    separate from the green/red tally. They are informational only — a
    quarantined case that still disagrees with the oracle is expected (that is
    why it was quarantined); it is NOT a regression and does not affect the exit
    code. A quarantined case that now AGREES is worth noting (the oracle may
    have fixed, and the case could be promoted back) but still not green/red.
    """
    lines: list[str] = ["Differential report", "=" * 18]
    for case in summary.cases:
        lines.append(f"{case.verdict.value:<20} {case.name}  {case.detail}".rstrip())
    lines.append("")
    lines.append(f"Summary: {summary.total} case(s)")
    for verdict in Verdict:
        n = summary.counts.get(verdict, 0)
        if n:
            lines.append(f"  {verdict.value:<20} {n}")
    if quarantine:
        lines.append("")
        lines.append(
            f"Quarantine: {len(quarantine)} case(s) — reported separately, "
            "not counted"
        )
        for case in quarantine:
            lines.append(
                f"  {case.verdict.value:<20} {case.name}  {case.detail}".rstrip()
            )
    return "\n".join(lines) + "\n"
