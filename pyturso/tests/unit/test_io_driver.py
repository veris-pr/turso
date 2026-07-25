"""Unit tests for pyturso.io.driver.run_to_completion.

Verified against: the generator convention in pyturso/io/HOWTO.md (drive a
yielding generator to completion, send completions back, propagate errors).
The toy generator here mirrors the canonical read_page example.
"""

from __future__ import annotations

from typing import Generator

import pytest

from pyturso.io.driver import run_to_completion, StepDriver
from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import (
    Completion,
    CompletionError,
    File,
    FileSyncType,
    ReadRequest,
    Request,
    SyncRequest,
    WriteRequest,
)


@pytest.fixture
def file() -> File:
    io = MemoryIO()
    f = io.open_file("test.db")
    # Seed two pages of known content.
    f.pwrite(WriteRequest(f, 0, b"PAGE1" + b"\x00" * 3))
    f.pwrite(WriteRequest(f, 8, b"PAGE2" + b"\x00" * 3))
    return f


# --- happy path: drive a two-read generator --------------------------------
def _two_reads(file: File) -> Generator[ReadRequest, Completion, bytes]:
    """Read 8 bytes from offset 0 and 8 from offset 8; return their concat."""
    c1 = yield ReadRequest(file, offset=0, n=8)
    c2 = yield ReadRequest(file, offset=8, n=8)
    return c1.unwrap_read() + c2.unwrap_read()


class TestHappyPath:
    def test_drives_two_reads_and_returns_concat(self, file: File) -> None:
        out = run_to_completion(_two_reads(file))
        assert out == b"PAGE1\x00\x00\x00PAGE2\x00\x00\x00"

    def test_generator_returning_value(self, file: File) -> None:
        out = run_to_completion(_two_reads(file))
        assert isinstance(out, bytes)
        assert len(out) == 16

    def test_single_read(self, file: File) -> None:
        def one(file: File) -> Generator[ReadRequest, Completion, bytes]:
            c = yield ReadRequest(file, 0, 5)
            return c.unwrap_read()

        assert run_to_completion(one(file)) == b"PAGE1"

    def test_write_then_sync(self, file: File) -> None:
        def op(file: File) -> Generator[Request, Completion, int]:
            wc = yield WriteRequest(file, 16, b"PAGE3")
            sc = yield SyncRequest(file, FileSyncType.Fsync)
            return wc.unwrap_count() + sc.unwrap_count()

        assert run_to_completion(op(file)) == 5  # 5 bytes + 0 sync


# --- immediate return (no yields) -----------------------------------------
class TestImmediateReturn:
    def test_return_value_after_yield(self, file: File) -> None:
        # A generator that yields once then returns a value.
        def noop() -> Generator[ReadRequest, Completion, int]:
            yield ReadRequest(file, 0, 1)
            return 42

        assert run_to_completion(noop()) == 42

    def test_return_none_after_yield(self, file: File) -> None:
        def noop() -> Generator[ReadRequest, Completion, None]:
            yield ReadRequest(file, 0, 1)
            return None

        assert run_to_completion(noop()) is None


# --- error propagation -----------------------------------------------------
class TestErrorPropagation:
    def test_generator_raise_propagates(self, file: File) -> None:
        def boom(file: File) -> Generator[ReadRequest, Completion, bytes]:
            yield ReadRequest(file, 0, 1)
            raise ValueError("kaboom")

        with pytest.raises(ValueError, match="kaboom"):
            run_to_completion(boom(file))

    def test_failure_completion_propagates_as_completionerror(
        self, file: File
    ) -> None:
        # A backend that returns a failure completion → unwrap raises
        # CompletionError → run_to_completion lets it propagate.
        class BadFile:
            def pread(self, req: ReadRequest) -> Completion:
                return Completion(error=CompletionError("io error", "boom"))

            def pwrite(self, req: WriteRequest) -> Completion:
                return Completion(count=0)

            def psync(self, req: SyncRequest) -> Completion:
                return Completion(count=0)

            def ptruncate(self, req: object) -> Completion:
                return Completion(count=0)

            def size(self) -> int:
                return 0

        def read_bad(file: object) -> Generator[ReadRequest, Completion, bytes]:
            req = ReadRequest(file, 0, 1)  # type: ignore[arg-type]
            c = yield req
            return c.unwrap_read()

        with pytest.raises(CompletionError, match="io error"):
            run_to_completion(read_bad(BadFile()))


# --- yield-from composition -----------------------------------------------
class TestYieldFrom:
    def test_yield_from_composes(self, file: File) -> None:
        def read8(file: File, offset: int) -> Generator[ReadRequest, Completion, bytes]:
            c = yield ReadRequest(file, offset, 8)
            return c.unwrap_read()

        def two(file: File) -> Generator[ReadRequest, Completion, bytes]:
            a = yield from read8(file, 0)
            b = yield from read8(file, 8)
            return a + b

        assert run_to_completion(two(file)) == b"PAGE1\x00\x00\x00PAGE2\x00\x00\x00"


# --- StepDriver: step-controlled driving (#17/#18) -------------------------
class TestStepDriver:
    def _gen(self, file: File) -> Generator[ReadRequest, Completion, bytes]:
        """Two-read generator that unwraps each read immediately (like real
        engine code — an error in the completion surfaces on the next step)."""
        c1 = yield ReadRequest(file, 0, 5)
        a = c1.unwrap_read()  # surfaces an injected error here
        c2 = yield ReadRequest(file, 8, 5)
        b = c2.unwrap_read()
        return a + b

    def test_primes_to_first_request(self, file: File) -> None:
        d = StepDriver(self._gen(file))
        assert not d.done
        assert isinstance(d.pending, ReadRequest)
        assert d.pending.offset == 0

    def test_step_advances_one_yield(self, file: File) -> None:
        d = StepDriver(self._gen(file))
        d.step()  # service first read
        assert not d.done
        assert isinstance(d.pending, ReadRequest)
        assert d.pending.offset == 8

    def test_second_step_completes_and_returns(self, file: File) -> None:
        d = StepDriver(self._gen(file))
        d.step()
        d.step()
        assert d.done
        assert d.result == b"PAGE1PAGE2"

    def test_request_sequence_matches_expectation(self, file: File) -> None:
        d = StepDriver(self._gen(file))
        offsets: list[int] = []
        while not d.done:
            assert isinstance(d.pending, ReadRequest)
            offsets.append(d.pending.offset)
            d.step()
        assert offsets == [0, 8]

    def test_result_none_until_done(self, file: File) -> None:
        d = StepDriver(self._gen(file))
        assert d.result is None
        d.step()
        assert d.result is None
        d.step()
        assert d.result is not None

    def test_step_when_done_raises(self, file: File) -> None:
        d = StepDriver(self._gen(file))
        d.step()
        d.step()
        assert d.done
        with pytest.raises(RuntimeError):
            d.step()

    def test_fail_injects_completionerror(self, file: File) -> None:
        # Inject a failure at the first read → unwrap_read raises CompletionError
        # inside the generator, which propagates out of fail(). The generator
        # is left not-cleanly-done (the error pre-empted the return).
        d = StepDriver(self._gen(file))
        with pytest.raises(CompletionError, match="io error"):
            d.fail(CompletionError("io error", "boom"))

    def test_abandon_closes_generator_mid_flight(self, file: File) -> None:
        d = StepDriver(self._gen(file))
        d.step()  # one read serviced, one pending
        assert not d.done
        d.abandon()
        assert d.done
        assert d.pending is None
        # Abandoning again is safe.
        d.abandon()

    def test_immediate_return_primes_as_done(self, file: File) -> None:
        def noop() -> Generator[ReadRequest, Completion, int]:
            yield ReadRequest(file, 0, 1)
            return 42

        d = StepDriver(noop())
        d.step()
        assert d.done and d.result == 42

    def test_inject_explicit_success_completion(self, file: File) -> None:
        # Inject a canned read result instead of servicing the real backend.
        d = StepDriver(self._gen(file))
        d.step(Completion(read_data=b"AAAAA"))
        d.step(Completion(read_data=b"BBBBB"))
        assert d.result == b"AAAAABBBBB"