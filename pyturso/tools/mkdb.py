"""mkdb — build fixture DBs with stdlib sqlite3 from DDL+data scripts.

Ports: (no Rust counterpart — a pyturso harness instrument; spirit from
``scripts/diff.sh`` and the corpus fixture workflow).
Phase: 0
Status: IMPLEMENTED.

Builds deterministic SQLite fixture databases from committed DDL+data scripts.
Fixture *scripts* are committed to the corpus; fixture *.db binaries are
gitignored (root ``.gitignore`` globs ``*.db``) and rebuilt on demand by this
tool. Until Phase 7 pyturso only *reads*, so every fixture is created with
stdlib sqlite3 and consumed back by the differential harness / dbdump.

Determinism contract (byte-reproducible output across rebuilds in the same
sqlite3 environment):
- A fixed ``PRAGMA page_size`` is forced on the empty database *before* any
  schema is created (page_size cannot change once pages are allocated).
- Journal mode is forced to ``DELETE`` so output is a single self-contained
  ``.db`` file — no ``-wal``/``-shm`` sidecars to leak or differ.
- A trailing ``PRAGMA integrity_check`` gates the build: a fixture that fails
  integrity is a broken fixture, so mkdb refuses to leave it behind.
- The script itself must be wall-clock-free (no ``CURRENT_TIMESTAMP`` /
  ``random()``); mkdb provides the deterministic environment, the script
  provides deterministic content.

Cross-sqlite3-version byte stability is *not* guaranteed — the header carries
the writing library's version number — so fixtures are rebuilt in one
environment rather than committed as binaries.

Usage::

    python -m tools.mkdb <script.sql> [-o out.db] [--page-size N]
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

#: Default page size. Matches SQLite's own compile-time default and the size
#: the file-format reader (Phase 1) is developed against.
DEFAULT_PAGE_SIZE: int = 4096

#: SQLite requires page_size to be a power of two in [512, 65536]
#: (see the file format spec). Validated so a bad --page-size fails fast and
#: deterministically rather than being silently coerced by SQLite.
_VALID_PAGE_SIZES: frozenset[int] = frozenset(1 << n for n in range(9, 17))

#: Forced journal mode. DELETE keeps the fixture a single ``.db`` file — WAL
#: would emit ``-wal``/``-shm`` sidecars that break the one-file-per-fixture
#: assumption the corpus and harness depend on.
_JOURNAL_MODE: str = "DELETE"


@dataclass(frozen=True)
class BuildResult:
    """Outcome of a fixture build. Returned by :func:`build_database` so the
    harness can consume ``path`` and report ``page_count`` without re-opening."""

    path: Path
    page_size: int
    page_count: int


def validate_page_size(size: int) -> int:
    """Validate a SQLite page size: power of two in 512..65536.

    Raises :class:`ValueError` on a bad value. This is the importable int
    pre-check used by :func:`build_database`; the argparse callback below
    parses the CLI string first, then delegates here.
    """
    if size not in _VALID_PAGE_SIZES:
        raise ValueError(
            f"page size must be a power of two in 512..65536, got {size}"
        )
    return size


def _page_size_from_cli(raw: str) -> int:
    """argparse ``type=`` callback: parse the CLI string then validate.

    argparse hands the raw token as ``str``; the int validator handles the
    membership check, so this just does the str→int step with a clear error.
    """
    try:
        n = int(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(f"page size must be an integer, got {raw!r}")
    return validate_page_size(n)


def build_database(
    script_path: str | Path,
    output_path: str | Path | None = None,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> BuildResult:
    """Build a deterministic SQLite fixture DB from a DDL+data script.

    Args:
        script_path: path to a ``.sql`` script (DDL + data).
        output_path: output ``.db`` path. Defaults to the script path with its
            suffix replaced by ``.db``.
        page_size: fixed page size; must be a power of two in 512..65536.

    Returns:
        The :class:`BuildResult` (output path, page_size, page_count).

    Raises:
        FileNotFoundError: the script does not exist.
        ValueError: ``page_size`` is not a valid SQLite page size.
        sqlite3.Error: the script failed to execute (propagated verbatim —
            fixture scripts are trusted corpus source, not untrusted input).
        RuntimeError: ``PRAGMA integrity_check`` returned anything but 'ok'.

    Any prior output file is removed first, and on failure the partial file is
    removed so a broken fixture never survives a failed build.
    """
    validate_page_size(page_size)

    script = Path(script_path)
    if not script.is_file():
        raise FileNotFoundError(f"fixture script not found: {script}")
    sql = script.read_text(encoding="utf-8")

    out = Path(output_path) if output_path is not None else script.with_suffix(".db")
    # Rebuild from scratch: never inherit a stale or corrupt file.
    if out.exists():
        out.unlink()

    try:
        conn = sqlite3.connect(str(out))
        try:
            # page_size + journal_mode must be set on the empty database before
            # any schema; SQLite ignores later page_size changes once allocated.
            conn.execute(f"PRAGMA page_size = {page_size}")
            conn.execute(f"PRAGMA journal_mode = {_JOURNAL_MODE}")
            conn.executescript(sql)
            conn.commit()
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(
                    f"integrity_check failed for {out}: {integrity}"
                )
            page_count = conn.execute("PRAGMA page_count").fetchone()[0]
        finally:
            conn.close()
    except Exception:
        # Leave no broken fixture behind. Remove then re-raise the real cause.
        if out.exists():
            out.unlink()
        raise

    return BuildResult(path=out, page_size=page_size, page_count=page_count)


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m tools.mkdb`` entry point. Returns a process exit code."""
    parser = argparse.ArgumentParser(
        prog="tools.mkdb",
        description=(
            "Build a deterministic SQLite fixture database from a DDL+data "
            "script using stdlib sqlite3."
        ),
    )
    parser.add_argument("script", help="path to .sql script (DDL + data)")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="output .db path (default: <script> with suffix .db)",
    )
    parser.add_argument(
        "--page-size",
        type=_page_size_from_cli,
        default=DEFAULT_PAGE_SIZE,
        help=f"page size in bytes, power of two in 512..65536 "
        f"(default: {DEFAULT_PAGE_SIZE})",
    )
    args = parser.parse_args(argv)

    result = build_database(
        args.script, args.output, page_size=args.page_size
    )
    # Stable, line-oriented output so the tool composes with grep/diff and
    # the harness can parse it if needed.
    print(f"built {result.path}")
    print(
        f"page_size={result.page_size} "
        f"journal_mode={_JOURNAL_MODE} "
        f"page_count={result.page_count}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via `python -m tools.mkdb`
    sys.exit(main())
