"""Unit tests for Phase 8: WAL checkpoint + Phase 10 DISTINCT + LEFT JOIN basics."""

from __future__ import annotations
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="arg-type"
# mypy: disable-error-code="assignment"

import sqlite3
from pathlib import Path

import pytest

from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import WriteRequest
from pyturso.storage.checksum import WAL_MAGIC_BE
from pyturso.storage.pager import Pager
from pyturso.storage.wal import WAL, WAL_HEADER_SIZE, WAL_FRAME_HEADER_SIZE
from pyturso.storage.checkpoint import checkpoint
from pyturso.types.value import Value
from pyturso.vdbe.sorter import Sorter


# --- WAL checkpoint ---
class TestCheckpoint:
    def test_checkpoint_empty_wal(self) -> None:
        """Checkpointing an empty WAL does nothing."""
        io = MemoryIO()
        io.open_file("db")
        pager = Pager(io, "db", page_size=4096)
        wal = WAL(io, "wal")
        wal.create(page_size=4096)
        result = checkpoint(pager, wal)
        assert result == 0

    def test_checkpoint_writes_frames_to_pager(self) -> None:
        """Checkpoint writes committed WAL frames back to the pager."""
        io = MemoryIO()
        f = io.open_file("db")
        f.pwrite(WriteRequest(f, 0, b"\x00" * 8192))
        pager = Pager(io, "db", page_size=4096)
        pager._file = f
        pager._page_size = 4096
        pager._header = None  # skip header write

        wal = WAL(io, "wal")
        wal.create(page_size=4096)
        wal.append_frame(page_no=2, page_data=b"\xAA" * 4096, db_size=0)
        wal.append_frame(page_no=2, page_data=b"\xBB" * 4096, db_size=3)

        assert len(wal.frames) == 2
        result = checkpoint(pager, wal)
        assert result == 1
        assert len(wal.frames) == 0
        from pyturso.io.driver import run_to_completion
        page2 = run_to_completion(pager.read_page(2))
        assert page2 == b"\xBB" * 4096

    def test_checkpoint_only_committed_frames(self) -> None:
        """Uncommitted frames (no commit frame) are not checkpointed."""
        io = MemoryIO()
        io.open_file("db")
        pager = Pager(io, "db", page_size=4096)

        wal = WAL(io, "wal")
        wal.create(page_size=4096)
        wal.append_frame(page_no=1, page_data=b"\xCC" * 4096, db_size=0)  # no commit

        result = checkpoint(pager, wal)
        assert result == 0  # nothing committed → nothing to checkpoint


# --- DISTINCT via sorter ---
class TestDistinct:
    def test_distinct_sorter(self) -> None:
        """DISTINCT: sort rows, skip consecutive duplicates."""
        s = Sorter()
        s.insert(keys=(Value.text("a"),), row=(Value.text("a"),))
        s.insert(keys=(Value.text("a"),), row=(Value.text("a"),))
        s.insert(keys=(Value.text("b"),), row=(Value.text("b"),))
        s.insert(keys=(Value.text("b"),), row=(Value.text("b"),))
        s.insert(keys=(Value.text("c"),), row=(Value.text("c"),))
        s.sort()
        s.rewind()

        results: list[str] = []
        prev: str | None = None
        while not s.done:
            r = s.record
            val = r.row[0].payload  # type: ignore[union-attr]
            if val != prev:
                results.append(val)
                prev = val
            s.next()
        assert results == ["a", "b", "c"]  # distinct values only


# --- GROUP BY basics ---
class TestGroupBy:
    def test_group_by_sort_then_aggregate(self) -> None:
        """GROUP BY: sort by group key, then aggregate consecutive rows."""
        from pyturso.functions.aggregate import AggregateState

        # Simulate: rows (dept, salary) → group by dept → sum(salary).
        s = Sorter()
        s.insert(keys=(Value.text("eng"),), row=(Value.text("eng"), Value.integer(100)))
        s.insert(keys=(Value.text("sales"),), row=(Value.text("sales"), Value.integer(50)))
        s.insert(keys=(Value.text("eng"),), row=(Value.text("eng"), Value.integer(200)))
        s.insert(keys=(Value.text("sales"),), row=(Value.text("sales"), Value.integer(60)))
        s.sort()
        s.rewind()

        results: list[tuple[str, int]] = []
        current_group: str | None = None
        agg: AggregateState | None = None

        while not s.done:
            r = s.record
            group = r.keys[0].payload  # type: ignore[union-attr]
            if group != current_group:
                if agg is not None:
                    results.append((current_group, agg.finalize().payload))  # type: ignore[union-attr]
                current_group = group
                agg = AggregateState("sum")
            if agg is not None:
                agg.step([r.row[1]])
            s.next()

        if agg is not None:
            results.append((current_group, agg.finalize().payload))  # type: ignore[union-attr]

        assert results == [("eng", 300), ("sales", 110)]