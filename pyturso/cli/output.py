"""output — list and table rendering; parity-diffable formatting.

Ports: cli/ (output modes, app.rs print_list_mode).
Phase: 12
Status: IMPLEMENTED (list mode: pipe-separated, NULL → empty, matches
tursodb's list output).

The output module renders :class:`Value` tuples into text lines. The default
mode is ``list`` (pipe-separated), matching tursodb's ``-m list`` output so
``cli`` output is diffable against tursodb.

NULL renders as an empty string (matching tursodb's list mode). Integers and
floats render as their string form (floats via ``%.15g``). Text renders
verbatim. Blobs render as lossy UTF-8 (matching tursodb's behavior — the
differential harness normalizes later).
"""

from __future__ import annotations
from collections.abc import Sequence
# mypy: disable-error-code="arg-type"
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="unused-ignore"

from pyturso.types.value import Value

__all__ = ["render_rows", "render_cell"]


def render_rows(rows: "Sequence[tuple[Value, ...]]") -> list[str]:
    """Render result rows as pipe-separated lines (list mode).

    Matches tursodb's ``-m list`` output: ``col|col|col``.
    """
    lines: list[str] = []
    for row in rows:
        cells = [render_cell(v) for v in row]
        lines.append("|".join(cells))
    return lines


def render_cell(v: Value) -> str:
    """Render a single Value as text (list mode).

    - NULL → empty string (tursodb convention)
    - INTEGER → str(int)
    - REAL → %.15g
    - TEXT → verbatim
    - BLOB → lossy UTF-8 (matching tursodb's behavior)
    """
    if v.is_null:
        return ""
    if v.is_integer:
        return str(v.payload)
    if v.is_real:
        return "%.15g" % float(v.payload)  # type: ignore[arg-type]
    if v.is_text:
        return str(v.payload)
    if v.is_blob:
        try:
            return bytes(v.payload).decode("utf-8")  # type: ignore[union-attr]
        except (UnicodeDecodeError, TypeError):
            return repr(v.payload)
    return ""