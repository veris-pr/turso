"""sorter — in-memory sort cursor for ORDER BY / GROUP BY.

Ports: core/vdbe/sorter.rs.
Phase: 10
Status: IMPLEMENTED (in-memory sort using Python's sorted with sort_key).

The sorter is a cursor-shaped object: ``insert`` rows, then ``rewind`` and
``next`` to iterate in sorted order. For Phase 10, the sort is in-memory
using Python's ``sorted()`` with the :func:`pyturso.types.compare.sort_key`
function — no external merge sort (that's a later optimization for large
datasets).

The sorter is used by:
  - ORDER BY: the emitter inserts each row's sort keys + the row data, then
    rewinds and iterates in sorted order.
  - GROUP BY: rows are sorted by the GROUP BY columns, then consecutive
    rows with the same key are aggregated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from pyturso.types.compare import sort_key
from pyturso.types.value import Value

__all__ = ["Sorter", "SorterRecord"]


@dataclass
class SorterRecord:
    """A record in the sorter: sort keys + the full row data."""
    keys: tuple[Value, ...]
    row: tuple[Value, ...]


class Sorter:
    """An in-memory sort cursor.

    Usage:
      1. ``insert(keys, row)`` for each row.
      2. ``sort()`` to sort by keys.
      3. ``rewind()`` to position at the first record.
      4. ``next()`` to advance; ``done`` when past the end.
      5. ``record`` to get the current :class:`SorterRecord`.
    """

    def __init__(self) -> None:
        self._records: list[SorterRecord] = []
        self._index: int = 0
        self._sorted: bool = False

    def insert(self, keys: tuple[Value, ...], row: tuple[Value, ...]) -> None:
        """Insert a row with its sort keys."""
        self._records.append(SorterRecord(keys=keys, row=row))
        self._sorted = False

    def sort(self) -> None:
        """Sort the records by their sort keys (ascending)."""
        self._records.sort(key=lambda r: tuple(sort_key(v) for v in r.keys))
        self._sorted = True

    def rewind(self) -> None:
        """Position at the first record."""
        if not self._sorted:
            self.sort()
        self._index = 0

    def next(self) -> None:
        """Advance to the next record."""
        self._index += 1

    @property
    def done(self) -> bool:
        """True if past the last record."""
        return self._index >= len(self._records)

    @property
    def record(self) -> SorterRecord | None:
        """The current record, or None if done."""
        if self._index < len(self._records):
            return self._records[self._index]
        return None

    @property
    def count(self) -> int:
        """Number of records in the sorter."""
        return len(self._records)