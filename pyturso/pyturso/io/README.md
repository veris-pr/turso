# pyturso.io — I/O abstraction, completions, backends

**Ports:** `core/io/` (`mod.rs`, `completions.rs`, `memory.rs`, `unix.rs`,
`clock.rs`); deliberately does **not** port `io_uring.rs`, `win_iocp.rs`,
`windows*.rs`, `vfs.rs` extension hooks
**Phase:** 1 (established first, on purpose — it sets the project's core idiom)

## What this module is

Turso's engine never blocks on I/O directly. Storage code issues read/write
requests through an `IO` trait and receives **completions**; long-running
operations are state machines that return `IOResult::IO` ("I/O pending,
re-enter me later"). That shape is what lets one engine run on io_uring,
plain POSIX, or in-memory backends — see
`docs/agent-guides/async-io-model.md`.

pyturso preserves the *shape* with Python generators — this is the single most
important convention in the port:

```python
def read_page(pager, page_no):          # ≈ fn read_page(...) -> IOResult<Page>
    buf = yield ReadRequest(file, offset=(page_no - 1) * page_size, n=page_size)
    return parse_page(buf)              # resumed with the completion via send()
```

A synchronous driver (`run_to_completion(gen, io)`) services requests
immediately for everyday use; the generator protocol still forces every I/O
boundary to be explicit, exactly like `IOResult` does in Rust. Later phases
(WAL crash injection, MVCC interleaving) exploit this: a test driver can pause
any operation at any yield point — the same trick Turso's simulator and
yield-injection machinery play.

## Planned files

| File | Ports | Notes |
|------|-------|-------|
| `protocol.py` | `core/io/mod.rs` traits | `IO`, `File` Protocols; request/`Completion` types |
| `driver.py` | — (pyturso-specific) | `run_to_completion`, plus a step-controlled driver for tests |
| `memory.py` | `core/io/memory.rs` | dict-of-pages in-RAM backend; primary test backend |
| `posix.py` | `core/io/unix.rs` (concept) | `os.pread`/`os.pwrite`-based real-file backend + fsync |
| `clock.py` | `core/io/clock.rs` | injectable time source (needed for WAL salts, datetime fns, determinism) |

## Parity notes

- Concept parity only: completion-based, explicit yield points, injectable
  backends. No async runtime, no threads, no io_uring — those are mechanism,
  not concept ([../../PLAN.md](../../PLAN.md) §2).
- File locking (`unix.rs`/`windows_lock.rs`) is deferred until multi-process
  questions matter; single process assumed throughout.

## Docs

Diátaxis tree: [../../docs/io/README.md](../../docs/io/README.md)
