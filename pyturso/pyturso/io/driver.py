"""driver — run generator-based I/O operations to completion.

Ports: (no Rust counterpart — pyturso-specific) the synchronous driver that
turns a generator yielding :mod:`pyturso.io.protocol` requests into a plain
return value, mirroring how Turso's synchronous I/O path drains completions.
Phase: 1
Status: IMPLEMENTED (``run_to_completion``). ``StepDriver`` is the next item.

The generator convention (see pyturso/io/README.md and HOWTO.md)::

    def read_page(file, page_size, page_no):
        buf = yield ReadRequest(file, offset=..., n=...)
        return decode_page(buf.unwrap_read())

``run_to_completion`` drives such a generator to completion: it primes the
generator with ``next()``, then on each yielded request asks the request's
backend :class:`File` to perform it and ``send()``s the resulting
:class:`Completion` back in, looping until the generator returns (``StopIteration``
carries the return value). Errors raised inside the generator propagate out;
a failure :class:`Completion` raised via ``unwrap_*`` propagates as the
:class:`CompletionError` it carries.

This is the everyday driver used at API boundaries (``statement.run()``, tools).
It is deliberately *not* used inside engine internals — there, generators
compose with ``yield from`` and a driver only appears at the very edge.
"""

from __future__ import annotations

from typing import Generator, Generic, TypeVar, cast

from .protocol import (
    Completion,
    CompletionError,
    File,
    ReadRequest,
    Request,
    SyncRequest,
    TruncateRequest,
    WriteRequest,
)

__all__ = ["run_to_completion", "StepDriver"]

T = TypeVar("T")


def run_to_completion(gen: Generator[Request, Completion, T]) -> T:
    """Drive ``gen`` to completion, returning its value.

    Args:
        gen: a generator that yields :class:`Request` objects and is resumed
            with the matching :class:`Completion` (the request's backend
            ``File`` performs the I/O and produces the completion).

    Returns:
        The generator's return value (``None`` if the generator returns
        without a value — the engine's "done, no result" signal).

    Raises:
        Whatever the generator raises (including :class:`CompletionError`
        raised by ``unwrap_read``/``unwrap_count`` on a failure completion):
        errors propagate straight out, never swallowed — engine code relies on
        this to surface corrupt/IO failures as the right :class:`pyturso.errors`
        class at the API boundary.
    """
    # Prime: advance to the first yield (or immediate return).
    try:
        req = next(gen)
    except StopIteration as stop:
        return cast("T", stop.value)

    while True:
        completion = _service(req)
        try:
            req = gen.send(completion)
        except StopIteration as stop:
            return cast("T", stop.value)


def _service(req: Request) -> Completion:
    """Perform ``req`` on its backend :class:`File` and return the completion."""
    f: File = req.file
    if isinstance(req, ReadRequest):
        return f.pread(req)
    if isinstance(req, WriteRequest):
        return f.pwrite(req)
    if isinstance(req, SyncRequest):
        return f.psync(req)
    if isinstance(req, TruncateRequest):
        return f.ptruncate(req)
    raise TypeError(f"unknown request type: {type(req).__name__}")


class StepDriver(Generic[T]):
    """Step-controlled driver for tests: pause any I/O mid-flight.

    The crash/interleaving hook the whole project leans on later (WAL crash
    injection, MVCC scheduling). Mirrors ``run_to_completion`` but advances one
    yield at a time, exposing the pending request so a test can:
      - assert the exact request sequence (request identity = invariants),
      - inject a failure completion (:meth:`fail`) to test error paths, or
      - stop early (:meth:`abandon`) to simulate a crash/abort.

    Usage::

        d = StepDriver(my_read_generator())
        assert isinstance(d.pending(), ReadRequest)
        d.step()              # service the request, send the completion
        assert d.done and d.result == b'...'

    A failure injected via :meth:`fail` raises the carried :class:`CompletionError`
    inside the generator (via ``unwrap_*``), so it propagates as the same
    exception a real backend would surface.
    """

    def __init__(self, gen: Generator[Request, Completion, T]) -> None:
        self._gen: Generator[Request, Completion, T] = gen
        self._pending: Request | None = None
        self._result: T | None = None
        self._done: bool = False
        # Prime to the first yield (or immediate return).
        try:
            self._pending = next(self._gen)
        except StopIteration as stop:
            self._done = True
            self._result = cast("T", stop.value)

    @property
    def pending(self) -> Request | None:
        """The current request awaiting service, or ``None`` if done."""
        return self._pending

    @property
    def done(self) -> bool:
        """True iff the generator has returned (no more yields)."""
        return self._done

    @property
    def result(self) -> T | None:
        """The generator's return value; ``None`` until :attr:`done`."""
        return self._result

    def step(self, completion: Completion | None = None) -> None:
        """Service the pending request and advance one yield.

        Args:
            completion: the completion to send back. ``None`` (default) asks
                the request's backend :class:`File` to perform the I/O and
                synthesizes the completion — the normal (non-injecting) path.
                Pass an explicit :class:`Completion` to inject a specific result.

        Raises:
            RuntimeError: called when :attr:`done` (no pending request).
            StopIteration: not raised — the generator's return is captured into
                :attr:`result` and :attr:`done` flips ``True``.
            Any exception raised inside the generator (e.g.
            :class:`CompletionError` from ``unwrap_*`` on an injected failure).
        """
        if self._done or self._pending is None:
            raise RuntimeError("StepDriver.step called when done")
        comp = completion if completion is not None else _service(self._pending)
        try:
            self._pending = self._gen.send(comp)
        except StopIteration as stop:
            self._done = True
            self._pending = None
            self._result = cast("T", stop.value)

    def fail(self, error: CompletionError) -> None:
        """Inject a failure completion for the pending request.

        The generator receives a :class:`Completion` carrying ``error``; if it
        calls ``unwrap_read``/``unwrap_count`` the error is raised inside the
        generator and propagates out of :meth:`fail` — exactly as a real
        backend failure would surface.
        """
        self.step(Completion(error=error))

    def abandon(self) -> None:
        """Close the generator, abandoning it mid-operation.

        Simulates a crash/abort at the current yield point: the generator is
        closed (``GeneratorExit`` raised inside it), and the driver is marked
        done with no result. Safe to call whether or not the generator is done.
        """
        if not self._done:
            self._gen.close()
        self._done = True
        self._pending = None