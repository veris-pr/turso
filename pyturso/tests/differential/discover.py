"""discover — find corpus cases and filter them by name / phase.

Ports: the corpus layout in tests/differential/README.md
(``corpus/<phaseN_topic>/<case>.sql``) and the ``-k``-style + ``--phase``
filtering in tests/differential/HOWTO.md.
Phase: 0
Status: IMPLEMENTED.

A corpus case is a ``.sql`` file under a phase subdirectory, e.g.
``corpus/phase5_select/select_literals.sql``. This module enumerates them and
applies two filters the harness CLI exposes:

  - ``-k <substr>``: case-insensitive substring match against the case's path
    relative to the corpus root (so ``-k select`` matches both a case named
    ``select_1`` in ``phase5_select/`` and one in any other phase whose path
    contains ``select``). Mirrors pytest's ``-k`` intent: a quick narrowing.
  - ``--phase <substr>``: case-insensitive substring match against the phase
    directory name (e.g. ``--phase phase1`` matches ``phase1_read``).

A case matches iff it passes BOTH filters. ``_quarantine/`` is excluded from
normal discovery (quarantined cases are reported separately by #12 and never
count toward a phase's green tally); :func:`discover_quarantine` lists them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "DiscoveredCase",
    "discover_corpus",
    "discover_quarantine",
    "QUARANTINE_DIR",
]

#: The quarantine directory name. Cases here are discovered separately (#12)
#: and never count toward a phase's green tally.
QUARANTINE_DIR: str = "_quarantine"


@dataclass(frozen=True)
class DiscoveredCase:
    """One discovered corpus case.

    ``phase`` is the immediate subdirectory of the corpus root (the phase
    topic, e.g. ``phase5_select``); ``""`` for a case sitting at the corpus
    root (defensive — the corpus convention groups cases under phase dirs).
    ``rel`` is the path relative to the corpus root, POSIX-style, used for
    ``-k`` matching and display.
    """

    path: Path
    name: str
    phase: str
    rel: str


def discover_corpus(
    corpus_dir: Path,
    *,
    k: str | None = None,
    phase: str | None = None,
) -> list[DiscoveredCase]:
    """Discover non-quarantined ``.sql`` cases under ``corpus_dir``.

    Applies the ``-k`` and ``--phase`` substring filters (both must pass). Cases
    are sorted by relative path for stable, diff-friendly reporting. Returns
    ``[]`` if the directory does not exist (a missing corpus is an empty
    corpus, not a crash).
    """
    found = _discover(corpus_dir, include_quarantine=False)
    filtered = [c for c in found if _matches(c, k=k, phase=phase)]
    return sorted(filtered, key=lambda c: c.rel)


def discover_quarantine(corpus_dir: Path) -> list[DiscoveredCase]:
    """Discover quarantined cases under ``corpus_dir/_quarantine/``.

    Quarantined cases are reported separately (#12) and never enter the green
    tally. No ``-k``/``--phase`` filter (quarantine is its own bucket). Sorted
    by relative path; ``[]`` if none or no corpus.
    """
    return sorted(_discover(corpus_dir, include_quarantine=True), key=lambda c: c.rel)


def _matches(
    case: DiscoveredCase, *, k: str | None, phase: str | None
) -> bool:
    """Both filters must pass (AND)."""
    if k is not None and k.lower() not in case.rel.lower():
        return False
    if phase is not None and phase.lower() not in case.phase.lower():
        return False
    return True


def _discover(
    corpus_dir: Path, *, include_quarantine: bool
) -> list[DiscoveredCase]:
    if not corpus_dir.is_dir():
        return []
    cases: list[DiscoveredCase] = []
    for path in sorted(corpus_dir.rglob("*.sql")):
        rel = path.relative_to(corpus_dir)
        parts = rel.parts
        # A case is quarantined iff _quarantine is anywhere in its path.
        is_quarantined = QUARANTINE_DIR in parts
        if is_quarantined != include_quarantine:
            continue
        phase = parts[0] if len(parts) > 1 else ""
        cases.append(
            DiscoveredCase(
                path=path,
                name=path.stem,
                phase=phase,
                rel=rel.as_posix(),
            )
        )
    return cases
