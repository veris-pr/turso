# IOResult as generators — the project's keystone convention

**Status:** current · **Phase:** 1 · **Cites:** `core/io/mod.rs`, `core/io/completions.rs`, `docs/agent-guides/async-io-model.md`

> This is the single most important convention in pyturso. Everything about
> how the engine is structured — why the pager, the B-tree, the VDBE, and the
> WAL are all generators — follows from the one choice explained here. Read it
> once, refer back often.

## The question

Turso's engine **never blocks on I/O directly**. A page read is not a function
call that returns bytes; it is a request that *may* be pending. Why? Because
the same engine has to run on a plain file (`pread`), in a ring (`io_uring`),
in a memory buffer for tests, and — in Turso's full form — interleave many
operations across many connections without threads blocking each other. The
shape that makes all of that the *same* engine is: **operations are state
machines that yield I/O requests and are re-entered with completions.**

pyturso does not port the mechanisms (`io_uring`, an event loop, threads). It
ports the *shape*, because the shape is what makes every I/O boundary explicit
and what lets a test pause any operation at any yield point. Python gives us
this shape for free: **generators**. This doc is the bridge.

## In Turso: `IOResult`

In Rust, the engine returns [`IOResult<T>`](../../core/io/mod.rs):

```rust
pub enum IOResult<T> {
    Done(T),                  // operation complete, here's the result
    IO(IOCompletions),        // need I/O — call me again after it finishes
}
```

A function returning `IOResult` is **not** called once. The caller drives it:
get `IO(request)`, perform the I/O, call again, repeat until `Done`. An
operation that needs *several* reads is a **state machine** — it carries its
own state (how many reads done, partial buffers) across calls, because Rust
has no stackful coroutines here. The repo guide
[`docs/agent-guides/async-io-model.md`](../../docs/agent-guides/async-io-model.md)
calls this "cooperative yielding with explicit state machines instead of
async/await."

The request is a [`Completion`](../../core/io/completions.rs) — a callback
that receives `Result<(Arc<Buffer>, i32), CompletionError>`: the bytes (or a
count) on success, or a `CompletionError` on failure. Macros (`io_yield_one!`,
`return_if_io!`) thread the state machine through nested calls, and
[`CompletionGroup`](../../core/io/completions.rs) aggregates several
completions into one "wait for all" barrier.

## In pyturso: `yield` + `send()`

A Python generator is *exactly* this shape, without the boilerplate:

```python
from pyturso.io.protocol import ReadRequest, Completion

def read_page(file, page_size, page_no):
    # ≈ fn read_page(...) -> IOResult<Page>
    completion = yield ReadRequest(
        file, offset=(page_no - 1) * page_size, n=page_size
    )
    data = completion.unwrap_read()   # raises CompletionError on failure
    return decode_page(data)
```

Read it against the Rust:

| Turso (Rust) | pyturso (Python) |
|---|---|
| `IOResult::IO(completion)` (yield a request, be re-entered) | `yield Request(...)` |
| caller drives `IOResult` until `Done` | [`run_to_completion(gen)`](../../../pyturso/io/driver.py) calls `next()` then `gen.send(completion)` |
| `IOResult::Done(value)` | `return value` (caught from `StopIteration.value`) |
| `Completion` callback carries `Result<buf, err>` | the `send()` value is a [`Completion`](../../../pyturso/io/protocol.py); `unwrap_*` raises the carried error |
| `return_if_io!` (propagate IO up the stack) | `yield from` (composition) |
| `CompletionGroup` (wait for N ops) | compose generators with `yield from`; a group is just a generator that yields N times |

The mapping is faithful in *behaviour* and *intent*. What pyturso drops is the
mechanism (no event loop, no ring, no threads — see
[`what-we-dont-port.md`](what-we-dont-port.md) when it lands). What it keeps is
the property that matters: **every I/O boundary is an explicit yield point.**

## Why `yield from` is nested state machines

A generator that calls another generator uses `yield from`:

```python
def read_page(file, page_size, page_no):
    c = yield ReadRequest(file, offset=(page_no - 1) * page_size, n=page_size)
    return decode_page(c.unwrap_read())

def read_two_pages(file, page_size, a, b):
    page_a = yield from read_page(file, page_size, a)
    page_b = yield from read_page(file, page_size, b)
    return page_a, page_b
```

This is *precisely* a state machine calling a state machine. `read_two_pages`
suspends at the same yield points `read_page` does; one driver drives the
whole stack. The Rust analogue is `return_if_io!` unwrapping a nested
`IOResult` and propagating the `IO` variant up. The B-tree walk yields from a
pager read; the VDBE step yields from the B-tree walk; one driver at the top
runs them all. **Composition is free** — you never write a driver per layer.

## Where the driver lives

A driver turns a yielding generator into a value. pyturso has two, both in
[`pyturso/io/driver.py`](../../../pyturso/io/driver.py):

- **`run_to_completion(gen)`** — the everyday driver. Primes the generator,
  services each yielded request by asking its backend `File` to perform the
  I/O, `send()`s the `Completion` back, returns the generator's value. Used at
  **API boundaries only** — `statement.run()`, tools. Never inside engine
  internals; there, generators compose with `yield from` and a driver appears
  only at the very edge.

- **`StepDriver(gen)`** — the test driver. Advances one yield at a time,
  exposes `pending` (the current request), lets a test inject a failure
  completion (`fail`) or stop early (`abandon`). This is the project's
  **crash-injection and interleaving hook**: Phase 8 pauses a WAL write
  mid-frame to simulate a crash; Phase 11 interleaves two connections' yields
  to test MVCC. Both are *the same trick* — drive a generator one yield, do
  something, drive again — and both exist in Turso as the simulator and the
  yield-injection machinery (see the async-io-model guide).

## The re-entrancy invariant

Because a generator is paused *between* statements at a yield, any I/O the
backend performs at a yield point must be **re-entrant**: driving the same
generator twice from the same point must be safe, and a yield must not observe
partial state from the backend. This is why `pread`/`pwrite` are *positional*
(take an offset, no shared file cursor) — see
[`backend-matrix.md`](../reference/backend-matrix.md). The memory backend's
shared store is re-entrant for the same reason: concurrent generators on one
in-memory database must not corrupt each other's view. (pyturso is
single-threaded until the MVCC phase, so this is forward-looking — but the
property is earned now, not retrofitted.)

## What to take away

1. **Engine code yields requests; it never calls a backend.** If you see
   `os.pread` outside `posix.py`, it is a bug.
2. **`yield from` composes; one driver runs the whole stack.** Never write a
   driver per subsystem.
3. **The yield point is the only place I/O happens**, so it is the only place
   a test can inject failure or pause — `StepDriver` exists to exploit that.
4. **Errors are values until `unwrap_*`.** A failure `Completion` is data; the
   generator decides when to raise it (mirroring Rust's `?`).

## In Turso — faithfulness ledger

| Ported faithfully | Simplified | Not ported (mechanism) |
|---|---|---|
| `IOResult` shape (yield/request/resume) | `Completion` is a plain value, not a callback-bearing object | `io_uring` (Linux ring I/O) |
| `Completion` result branches (bytes/count/error) | one completion per request, no reference counting | `WinIOCP` (Windows I/O completion ports) |
| `return_if_io!` → `yield from` | driver is synchronous (services immediately) | threads / an event loop |
| `CompletionGroup` → generator composition | | file locking (`unix.rs` / `windows_lock.rs`) — deferred until multi-process matters |
| positional I/O (re-entrancy) | | VFS extension hooks (`vfs.rs`) |

Re-read `core/io/mod.rs` (the `File`/`IO` traits), `core/io/completions.rs`
(the result branches), and the async-io-model guide after the storage phase
lands — the conventions get their first real exercise there, and this doc
earns updates from what was missed.
