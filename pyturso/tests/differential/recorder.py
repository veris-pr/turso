"""recorder — record/load oracle-output sidecars for corpus cases.

Ports: the expectation discipline in tests/differential/corpus/HOWTO.md
("Expected outputs are never hand-written: the harness records the oracle's
normalized output. Regenerate via the harness flag, review the diff.")
Phase: 0
Status: IMPLEMENTED.

A case may carry an *expected-output sidecar*: the oracle's (sqlite3) normalized
per-statement results, recorded once and reviewed via git diff, against which
pyturso is later compared. Sidecars are **generated, never hand-written** — the
``--record`` harness flag calls :func:`record_expected` to (re)write them from
the oracle; a hand-edited sidecar is a process violation.

Format: JSON. It is stdlib-only, round-trips exactly, and escapes cell content
(pipes, spaces, newlines, quotes) unambiguously — important because normalized
cells are arbitrary text. A git diff of two JSON sidecars is reviewable: a
changed row shows as a one-line JSON change. The list structure mirrors
``list[StatementResult]`` directly (a list whose elements are either a list of
row-lists (Rows) or a string (ErrorClass)); tuples are restored on load so the
type matches :data:`tests.differential.engine.Rows`.

The primary comparison in the harness is still the live three-way (sqlite3 vs
tursodb vs pyturso); recorded sidecars are an additional pin against oracle
drift (e.g. a sqlite3 version change) and a faster path for pyturso-only
development. Loading is optional: a case without a sidecar compares live.
"""

from __future__ import annotations

import json
from pathlib import Path

from .engine import Rows, StatementResult

__all__ = [
    "SIDECAR_SUFFIX",
    "expected_path",
    "record_expected",
    "load_expected",
    "serialize",
    "deserialize",
]

#: Sidecar files append this to the case name: ``case.sql`` → ``case.sql.exp``.
#: Appending (not replacing) keeps the case and its expectation adjacent in a
#: directory listing and survives any case suffix.
SIDECAR_SUFFIX: str = ".exp"


def expected_path(case_path: Path) -> Path:
    """The sidecar path for ``case_path`` (``case.sql`` → ``case.sql.exp``)."""
    return case_path.with_name(case_path.name + SIDECAR_SUFFIX)


def record_expected(case_path: Path, results: list[StatementResult]) -> Path:
    """Write ``results`` as the oracle sidecar for ``case_path``.

    Returns the sidecar path. Overwrites any prior sidecar so ``--record`` is
    idempotent and reflects current oracle output, not a stale file. The
    serialized form is deterministic (sorted keys, stable separators) so the
    git diff of two recordings shows only real changes.
    """
    path = expected_path(case_path)
    path.write_text(serialize(results), encoding="utf-8")
    return path


def load_expected(case_path: Path) -> list[StatementResult] | None:
    """Load the sidecar for ``case_path``, or ``None`` if absent.

    Absent → ``None`` (the harness then compares live). A corrupt sidecar is a
    real failure (a generated file should never be malformed), so JSON errors
    propagate rather than being swallowed.
    """
    path = expected_path(case_path)
    if not path.is_file():
        return None
    return deserialize(path.read_text(encoding="utf-8"))


def serialize(results: list[StatementResult]) -> str:
    """Serialize results to deterministic JSON.

    Rows (``tuple[str, ...]``) become JSON arrays; an :data:`ErrorClass` string
    stays a JSON string. ``sort_keys`` keeps object key order stable (there are
    no object keys here today, but the flag future-proofs any added metadata).
    """
    # tuples serialize as JSON arrays automatically; no manual conversion needed.
    return json.dumps(results, sort_keys=True, ensure_ascii=False, indent=0)


def deserialize(text: str) -> list[StatementResult]:
    """Parse a sidecar back into typed results.

    JSON arrays become Python lists; row arrays are converted back to tuples so
    the loaded :data:`Rows` match the in-memory type (``list[tuple[str, ...]]``).
    A statement entry that is a JSON string is an :data:`ErrorClass`.
    """
    raw = json.loads(text)
    out: list[StatementResult] = []
    for entry in raw:
        if isinstance(entry, str):
            out.append(entry)
        else:
            rows: Rows = [tuple(cells) for cells in entry]
            out.append(rows)
    return out
