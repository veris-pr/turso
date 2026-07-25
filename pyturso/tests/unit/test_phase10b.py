"""Unit tests for Phase 10: sorter, aggregates, GROUP BY basics."""

from __future__ import annotations

import pytest

from pyturso.types.value import Value
from pyturso.vdbe.sorter import Sorter, SorterRecord
from pyturso.functions.aggregate import AggregateState


# --- sorter ---
class TestSorter:
    def test_insert_and_sort(self) -> None:
        s = Sorter()
        s.insert(keys=(Value.integer(3),), row=(Value.text("c"),))
        s.insert(keys=(Value.integer(1),), row=(Value.text("a"),))
        s.insert(keys=(Value.integer(2),), row=(Value.text("b"),))
        s.sort()
        s.rewind()
        results = []
        while not s.done:
            results.append(s.record.row[0].payload)  # type: ignore[union-attr]
            s.next()
        assert results == ["a", "b", "c"]

    def test_empty_sorter(self) -> None:
        s = Sorter()
        s.sort()
        s.rewind()
        assert s.done
        assert s.record is None

    def test_count(self) -> None:
        s = Sorter()
        s.insert(keys=(Value.integer(1),), row=(Value.text("x"),))
        s.insert(keys=(Value.integer(2),), row=(Value.text("y"),))
        assert s.count == 2

    def test_sort_by_multiple_keys(self) -> None:
        s = Sorter()
        s.insert(keys=(Value.integer(2), Value.text("a")), row=(Value.text("row1"),))
        s.insert(keys=(Value.integer(1), Value.text("b")), row=(Value.text("row2"),))
        s.insert(keys=(Value.integer(1), Value.text("a")), row=(Value.text("row3"),))
        s.sort()
        s.rewind()
        results = []
        while not s.done:
            r = s.record
            results.append((r.keys[0].payload, r.keys[1].payload, r.row[0].payload))  # type: ignore[union-attr]
            s.next()
        assert results == [(1, "a", "row3"), (1, "b", "row2"), (2, "a", "row1")]


# --- aggregates ---
class TestAggregates:
    def test_count_star(self) -> None:
        state = AggregateState("count")
        state.step([])
        state.step([])
        state.step([])
        assert state.finalize() == Value.integer(3)

    def test_count_x(self) -> None:
        state = AggregateState("count")
        state.step([Value.integer(1)])
        state.step([Value.null()])
        state.step([Value.integer(3)])
        assert state.finalize() == Value.integer(2)  # null not counted

    def test_sum_integers(self) -> None:
        state = AggregateState("sum")
        state.step([Value.integer(10)])
        state.step([Value.integer(20)])
        state.step([Value.integer(30)])
        assert state.finalize() == Value.integer(60)

    def test_sum_mixed(self) -> None:
        state = AggregateState("sum")
        state.step([Value.integer(10)])
        state.step([Value.real(20.5)])
        assert state.finalize() == Value.real(30.5)

    def test_sum_empty(self) -> None:
        state = AggregateState("sum")
        assert state.finalize() == Value.null()

    def test_total_always_real(self) -> None:
        state = AggregateState("total")
        state.step([Value.integer(10)])
        state.step([Value.integer(20)])
        assert state.finalize() == Value.real(30.0)

    def test_total_empty(self) -> None:
        state = AggregateState("total")
        assert state.finalize() == Value.real(0.0)

    def test_avg(self) -> None:
        state = AggregateState("avg")
        state.step([Value.integer(10)])
        state.step([Value.integer(20)])
        state.step([Value.integer(30)])
        assert state.finalize() == Value.real(20.0)

    def test_avg_empty(self) -> None:
        state = AggregateState("avg")
        assert state.finalize() == Value.null()

    def test_min(self) -> None:
        state = AggregateState("min")
        state.step([Value.integer(30)])
        state.step([Value.integer(10)])
        state.step([Value.integer(20)])
        assert state.finalize() == Value.integer(10)

    def test_min_all_null(self) -> None:
        state = AggregateState("min")
        state.step([Value.null()])
        state.step([Value.null()])
        assert state.finalize() == Value.null()

    def test_max(self) -> None:
        state = AggregateState("max")
        state.step([Value.integer(10)])
        state.step([Value.integer(30)])
        state.step([Value.integer(20)])
        assert state.finalize() == Value.integer(30)

    def test_group_concat(self) -> None:
        state = AggregateState("group_concat")
        state.step([Value.text("a")])
        state.step([Value.text("b")])
        state.step([Value.text("c")])
        assert state.finalize() == Value.text("a,b,c")

    def test_group_concat_empty(self) -> None:
        state = AggregateState("group_concat")
        assert state.finalize() == Value.null()

    def test_group_concat_with_nulls(self) -> None:
        state = AggregateState("group_concat")
        state.step([Value.text("a")])
        state.step([Value.null()])
        state.step([Value.text("b")])
        assert state.finalize() == Value.text("a,b")