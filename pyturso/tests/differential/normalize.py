"""normalize — canonical row rendering for the three-way comparison.

Ports: the normalization rules in tests/differential/README.md (the
"hard-won part — documented as they are earned").
Phase: 0
Status: IMPLEMENTED (Phase 0 rules: NULL literal, %.15g float reconciliation,
text passthrough). Float/blob edge cases are earned as the corpus exercises
them.

Canonical form (pinned by README):
  - NULL  → ``"NULL"`` (the literal)
  - float → ``%.15g``  (sqlite3's convention; the canonical oracle format)
  - int   → decimal, verbatim
  - text  → verbatim
  - blob  → ``x'<lowerhex>'``  (only type-aware engines can produce this)

Why a *text* normalizer, not a typed one: the tursodb adapter emits rendered
text (subprocess boundary loses types), so the only common currency across
engines is text. Type-aware adapters (sqlite3, pyturso) already emit canonical
text via :func:`tests.differential.engine.render_cell`; this module's job is to
make tursodb's native text match that canonical form, and to do so
**idempotently** — normalizing already-canonical text must leave it unchanged,
so the harness applies the same normalizer to every engine uniformly.

Reconciliation rules (each documented with its limitation):
  - ``""`` → ``"NULL"``. tursodb renders SQL NULL as an empty cell; the
    canonical literal is ``"NULL"``. LIMITATION: a TEXT value that is the empty
    string is indistinguishable from NULL in tursodb's output, so the corpus
    must not rely on empty-TEXT vs NULL distinction (earned, documented).
  - float-looking cells (contain ``.``/``e``/``E`` and parse as ``float``) →
    re-rendered ``%.15g``. This reconciles tursodb's ``format_float``
    (``core/numeric/mod.rs``, a custom precision-15 algorithm that diverges
    from ``%.15g`` for some magnitudes, e.g. ``1e20``) to the canonical
    ``%.15g``. Idempotent on canonical input. LIMITATION: a TEXT value whose
    contents parse as a float (``"1e5"``) is normalized as if it were a float;
    the corpus avoids such text, and both engines render text identically so
    the mis-normalization is symmetric (still compares equal).
  - everything else: verbatim. In particular integers (no ``.``/``e``) pass
    through untouched, preserving full int64 precision that a float round-trip
    would destroy.

Error handling is NOT done here: each adapter maps its engine's errors to the
comparison-class vocabulary (``pyturso.errors`` constants) at the source —
sqlite3 via MRO, tursodb via ``#[error]`` prefix, pyturso via
:class:`EngineNotImplemented`. Normalization only touches rows; it passes
:data:`ErrorClass` strings through unchanged.

Blobs: type-aware adapters render ``x'<hex>'``; tursodb renders blobs as
lossy-UTF-8, which cannot be reversed to hex. Blob corpus cases therefore
cannot be compared against tursodb and are quarantined/excluded there — this
module makes no attempt to recover blob type from tursodb text.
"""

from __future__ import annotations

from .engine import ErrorClass, Rows, StatementResult

__all__ = [
    "CANONICAL_NULL",
    "FLOAT_FORMAT",
    "normalize_cell",
    "normalize_rows",
    "normalize_result",
    "normalize_results",
]

#: The canonical NULL literal. README: "NULL literal".
CANONICAL_NULL: str = "NULL"

#: The canonical float format (README: "sqlite3's %.15g convention"). Matches
#: :func:`tests.differential.engine.render_cell` so the two stay in sync.
FLOAT_FORMAT: str = "%.15g"

#: Characters that mark a cell as a float candidate. A pure-integer string
#: (no ``.``/``e``/``E``) is never float-normalized, so int64 precision is
#: preserved — a float round-trip would silently destroy it.
_FLOAT_MARKS: frozenset[str] = frozenset(".eE")


def normalize_cell(cell: str) -> str:
    """Canonicalize one text cell.

    See module docstring for the rules and their limitations. Idempotent on
    canonical input: applying it twice yields the same string.
    """
    # NULL: tursodb's empty cell → the canonical NULL literal. (Empty TEXT is
    # indistinguishable in tursodb output; see module docstring.)
    if cell == "":
        return CANONICAL_NULL

    # Float reconciliation: only attempt when the cell looks numeric (contains
    # a float mark). Guards integer/hex-blob/text strings from a spurious
    # float() attempt and its precision loss.
    if any(mark in cell for mark in _FLOAT_MARKS):
        try:
            return FLOAT_FORMAT % float(cell)
        except ValueError:
            pass  # looked numeric but isn't a float (e.g. blob "x'abef'"): keep

    return cell


def normalize_rows(rows: Rows) -> Rows:
    """Canonicalize every cell of every row. Row/column shape is preserved."""
    return [tuple(normalize_cell(c) for c in row) for row in rows]


def normalize_result(result: StatementResult) -> StatementResult:
    """Canonicalize one statement result.

    Rows are normalized; an :data:`ErrorClass` string is passed through
    unchanged (errors are already comparison classes — see module docstring).
    """
    if isinstance(result, str):
        return result
    return normalize_rows(result)


def normalize_results(results: list[StatementResult]) -> list[StatementResult]:
    """Canonicalize a whole script's per-statement results, in place-by-value."""
    return [normalize_result(r) for r in results]
