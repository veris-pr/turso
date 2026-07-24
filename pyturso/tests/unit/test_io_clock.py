"""Unit tests for pyturso.io.clock — injectable time source.

Verified against: core/io/clock.rs (Clock trait, DefaultClock, FixedClock
equivalent, MonotonicInstant/WallClockInstant shapes).
"""

from __future__ import annotations

import pytest

from pyturso.io.clock import (
    Clock,
    FixedClock,
    SystemClock,
    WallClockInstant,
)


# --- WallClockInstant ------------------------------------------------------
class TestWallClockInstant:
    def test_fields(self) -> None:
        w = WallClockInstant(secs=100, micros=500_000)
        assert w.secs == 100 and w.micros == 500_000

    def test_to_micros(self) -> None:
        assert WallClockInstant(2, 500_000).to_micros() == 2_500_000

    def test_frozen_equality(self) -> None:
        assert WallClockInstant(1, 0) == WallClockInstant(1, 0)


# --- Protocol conformance --------------------------------------------------
class TestProtocol:
    def test_system_clock_is_a_clock(self) -> None:
        assert isinstance(SystemClock(), Clock)

    def test_fixed_clock_is_a_clock(self) -> None:
        assert isinstance(FixedClock(), Clock)


# --- SystemClock: real time (smoke; no exact assertions) -------------------
class TestSystemClock:
    def test_monotonic_nondecreasing(self) -> None:
        c = SystemClock()
        a = c.current_time_monotonic()
        b = c.current_time_monotonic()
        assert b >= a

    def test_wall_clock_reasonable(self) -> None:
        w = SystemClock().current_time_wall_clock()
        assert w.secs > 1_000_000_000  # after ~2001
        assert 0 <= w.micros < 1_000_000


# --- FixedClock: deterministic ---------------------------------------------
class TestFixedClock:
    def test_monotonic_frozen_by_default(self) -> None:
        c = FixedClock(monotonic_ns=1000)
        assert c.current_time_monotonic() == 1000
        assert c.current_time_monotonic() == 1000  # no step → frozen

    def test_monotonic_advances_with_step(self) -> None:
        c = FixedClock(monotonic_ns=100, step_ns=50)
        assert c.current_time_monotonic() == 100
        assert c.current_time_monotonic() == 150
        assert c.current_time_monotonic() == 200

    def test_wall_clock_fixed(self) -> None:
        w = WallClockInstant(secs=42, micros=123)
        c = FixedClock(wall=w)
        assert c.current_time_wall_clock() == w
        assert c.current_time_wall_clock() == w  # stable

    def test_set_monotonic(self) -> None:
        c = FixedClock()
        c.set_monotonic(999)
        assert c.current_time_monotonic() == 999

    def test_advance(self) -> None:
        c = FixedClock(monotonic_ns=100)
        c.advance(50)
        assert c.current_time_monotonic() == 150

    def test_set_wall(self) -> None:
        c = FixedClock()
        w = WallClockInstant(secs=7, micros=0)
        c.set_wall(w)
        assert c.current_time_wall_clock() == w

    def test_default_wall_is_epoch(self) -> None:
        c = FixedClock()
        assert c.current_time_wall_clock() == WallClockInstant(0, 0)