"""Unit tests for pyturso.storage.sqlite3_ondisk overflow thresholds.

Ports/verified against: core/storage/sqlite3_ondisk.rs payload_overflows +
core/storage/btree.rs payload_overflow_threshold_max/min.

The overflow threshold math is the most subtle part of the file format. It
determines how much payload stays on a page vs. spills into overflow chains.
Tests verify the exact formulas against the Rust and exercise boundary cases.
"""

from __future__ import annotations

import pytest

from pyturso.storage.sqlite3_ondisk import (
    OVERFLOW_HEADER_SIZE,
    PageType,
    payload_overflow_threshold_max,
    payload_overflow_threshold_min,
    payload_overflows,
)


# --- threshold formulas (ports btree.rs) ----------------------------------
class TestThresholds:
    def test_table_leaf_max_is_usable_minus_35(self) -> None:
        # usable_size = 4096 → max_local = 4096 - 35 = 4061
        assert payload_overflow_threshold_max(PageType.TABLE_LEAF, 4096) == 4061

    def test_table_interior_max_is_usable_minus_35(self) -> None:
        assert payload_overflow_threshold_max(PageType.TABLE_INTERIOR, 4096) == 4061

    def test_index_max_formula(self) -> None:
        # ((4096 - 12) * 64 / 255) - 23 = (4084 * 64 // 255) - 23 = 1025 - 23 = 1002
        assert payload_overflow_threshold_max(PageType.INDEX_LEAF, 4096) == 1002

    def test_min_formula_all_types(self) -> None:
        # ((4096 - 12) * 32 / 255) - 23 = (4084 * 32 // 255) - 23 = 512 - 23 = 489
        for pt in (PageType.TABLE_LEAF, PageType.TABLE_INTERIOR,
                   PageType.INDEX_LEAF, PageType.INDEX_INTERIOR):
            assert payload_overflow_threshold_min(pt, 4096) == 489


# --- payload_overflows: no-overflow case -----------------------------------
class TestNoOverflow:
    def test_payload_within_max_no_overflow(self) -> None:
        max_local = 4061
        min_local = 489
        usable = 4096
        overflows, local = payload_overflows(100, max_local, min_local, usable)
        assert not overflows
        assert local == 0

    def test_payload_exactly_max_no_overflow(self) -> None:
        max_local = 4061
        min_local = 489
        usable = 4096
        overflows, local = payload_overflows(max_local, max_local, min_local, usable)
        assert not overflows


# --- payload_overflows: overflow case --------------------------------------
class TestOverflow:
    def test_payload_above_max_overflows(self) -> None:
        max_local = 4061
        min_local = 489
        usable = 4096
        # payload_size = 5000 > max_local = 4061 → overflow.
        overflows, local = payload_overflows(5000, max_local, min_local, usable)
        assert overflows
        # The local formula:
        # space_left = min_local + (payload_size - min_local) % (usable - 4)
        # = 489 + (5000 - 489) % (4092)
        # = 489 + 4511 % 4092 = 489 + 419 = 908
        # 908 <= max_local (4061), so space_left stays 908
        # local = 908 + 4 = 912
        expected_space = 489 + (5000 - 489) % (4096 - 4)
        assert local == expected_space + 4

    def test_large_payload_space_left_capped_to_min(self) -> None:
        max_local = 4061
        min_local = 489
        usable = 4096
        # Very large payload: space_left would exceed max_local → capped to min_local.
        # payload_size = 100000
        # space_left = 489 + (100000 - 489) % 4092 = 489 + (99511 % 4092)
        # 99511 % 4092 = 99511 - 24*4092 = 99511 - 98208 = 1303
        # space_left = 489 + 1303 = 1792 → <= max_local (4061) → stays 1792
        # So NOT capped in this case. Let's pick a value that IS capped:
        # We need space_left > max_local. That happens when
        # (payload_size - min_local) % (usable - 4) > max_local - min_local
        # = 4061 - 489 = 3572. Since usable - 4 = 4092, the max remainder is
        # 4091. So 4091 > 3572 → capped.
        # Pick payload_size so remainder is 4091:
        # (payload_size - 489) % 4092 = 4091 → payload_size - 489 = 4091 + k*4092
        # k=0 → payload_size = 4580
        overflows, local = payload_overflows(4580, max_local, min_local, usable)
        assert overflows
        # space_left = 489 + 4091 = 4580 > 4061 → capped to 489
        # local = 489 + 4 = 493
        assert local == 489 + 4

    def test_local_bytes_includes_overflow_ptr(self) -> None:
        """When overflowing, local bytes include the 4-byte overflow page ptr."""
        max_local = 100
        min_local = 50
        usable = 200
        overflows, local = payload_overflows(150, max_local, min_local, usable)
        assert overflows
        # local = space_left + 4 (the +4 is the overflow pointer)
        # space_left = 50 + (150 - 50) % (200 - 4) = 50 + 100 % 196 = 50 + 100 = 150
        # 150 > max_local (100) → capped to 50
        # local = 50 + 4 = 54
        assert local == 54

    def test_just_above_max(self) -> None:
        """One byte above max → overflow with minimal local."""
        max_local = 4061
        min_local = 489
        usable = 4096
        overflows, local = payload_overflows(4062, max_local, min_local, usable)
        assert overflows
        # space_left = 489 + (4062 - 489) % 4092 = 489 + 3573 % 4092 = 489 + 3573
        # = 4062 → > 4061 → capped to 489
        # local = 489 + 4 = 493
        assert local == 493


# --- overflow header constant ---------------------------------------------
class TestOverflowHeader:
    def test_overflow_header_size_is_4(self) -> None:
        assert OVERFLOW_HEADER_SIZE == 4