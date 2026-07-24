"""clock — injectable time source (monotonic + wall clock).

Ports: core/io/clock.rs (``Clock`` trait, ``DefaultClock``, ``MonotonicInstant``,
``WallClockInstant``).
Phase: 1
Status: IMPLEMENTED.

Turso abstracts time behind a ``Clock`` trait so tests (WAL salts, datetime
functions, timeout policies) can inject a deterministic clock instead of
depending on wall time. pyturso mirrors this: :class:`Clock` is a
:class:`typing.Protocol` with two methods — monotonic (for elapsed-time /
timeouts) and wall-clock (for timestamps / WAL salts).

:class:`SystemClock` is the real clock (``time.monotonic_ns`` /
``time.time``); :class:`FixedClock` is the deterministic test clock (returns
configured values, advances on call). The ``IO`` trait in Rust subsumes
``Clock`` (``trait IO: Clock``); pyturso keeps them separate for clarity and
composes them at the point where an ``IO`` backend also needs a clock (a later
item wires this).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = [
    "Clock",
    "SystemClock",
    "FixedClock",
    "WallClockInstant",
]


@dataclass(frozen=True)
class WallClockInstant:
    """Wall-clock time as seconds + microseconds since the Unix epoch.

    Ports ``core::io::clock::WallClockInstant``. ``micros`` is in [0, 999999].
    """

    secs: int
    micros: int

    def to_micros(self) -> int:
        """Total microseconds since the epoch (lossless for valid instants)."""
        return self.secs * 1_000_000 + self.micros


@runtime_checkable
class Clock(Protocol):
    """Time source. Ports ``core::io::Clock``.

    Two surfaces: monotonic (never goes backwards; for elapsed-time/timeout)
    and wall-clock (real-world time; for timestamps/WAL salts). Backends pick
    which they need; most engine code uses monotonic for deadlines.
    """

    def current_time_monotonic(self) -> int:
        """Monotonic nanoseconds since an arbitrary fixed epoch (never decreases)."""
        ...

    def current_time_wall_clock(self) -> WallClockInstant:
        """Wall-clock time as seconds+micros since the Unix epoch."""
        ...


class SystemClock:
    """The real clock backed by ``time.monotonic_ns`` / ``time.time``.

    Ports ``DefaultClock``. Used in production; tests inject
    :class:`FixedClock` instead so WAL salts / timeouts / datetime functions
    are deterministic.
    """

    def current_time_monotonic(self) -> int:
        return time.monotonic_ns()

    def current_time_wall_clock(self) -> WallClockInstant:
        now = time.time()
        secs = int(now)
        micros = int((now - secs) * 1_000_000)
        return WallClockInstant(secs=secs, micros=micros)


class FixedClock:
    """A deterministic clock for tests: returns configured, advanceable time.

    ``monotonic`` advances by ``step_ns`` on each call (default 0 — frozen);
    ``wall_clock`` returns a fixed instant until set. This lets a test pin
    time exactly (WAL salts, timeout expiry) and advance it deterministically.
    """

    def __init__(
        self,
        *,
        monotonic_ns: int = 0,
        wall: WallClockInstant | None = None,
        step_ns: int = 0,
    ) -> None:
        self._monotonic: int = monotonic_ns
        self._wall: WallClockInstant = wall or WallClockInstant(secs=0, micros=0)
        self._step_ns: int = step_ns

    def current_time_monotonic(self) -> int:
        val = self._monotonic
        self._monotonic += self._step_ns
        return val

    def current_time_wall_clock(self) -> WallClockInstant:
        return self._wall

    def set_monotonic(self, ns: int) -> None:
        """Set the monotonic clock to ``ns`` (test control)."""
        self._monotonic = ns

    def set_wall(self, instant: WallClockInstant) -> None:
        """Set the wall clock to ``instant`` (test control)."""
        self._wall = instant

    def advance(self, ns: int) -> None:
        """Advance the monotonic clock by ``ns`` (test control)."""
        self._monotonic += ns