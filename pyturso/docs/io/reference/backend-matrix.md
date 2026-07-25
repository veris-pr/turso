# Backend matrix — reference

**Status:** current · **Phase:** 1 · **Cites:** `pyturso/io/memory.py`,
`pyturso/io/posix.py`; Rust: `core/io/memory.rs`, `core/io/unix.rs`.

The two pyturso I/O backends, side by side. Both conform to the
[`File`](../../pyturso/io/protocol.py) Protocol; the differences are
capabilities and semantics. Updated in the same commit as any backend change.

## Capability matrix

| Capability | `MemoryFile` / `MemoryIO` | `PosixFile` / `PosixIO` |
|---|---|---|
| Backing store | `bytearray` per file (RAM) | OS file (`os.open` fd) |
| Persistence | process-lifetime only | real file on disk |
| File identity on re-open | **shared store** (same name → same bytes) | new fd, same OS file |
| `size()` | `len(store)` | `os.fstat().st_size` |
| Speed | primary **test** backend (fast, deterministic) | real I/O backend |
| `direct` (O_DIRECT) arg | accepted, ignored | accepted, ignored (no kernel direct-IO) |
| Reference ports | `core/io/memory.rs` (`MemStore`) | `core/io/unix.rs` (`UnixFile`) |

## Behaviour parity (both backends)

These are protocol guarantees — every backend *must* satisfy them, and the
unit suites assert them on both:

- **Short read at EOF**: `pread` past/at EOF returns fewer bytes (or `b""`),
  never an error. Matches `os.pread`. (`MemStore::read_into`,
  `libc::pread`.)
- **Zero-fill holes**: reading a never-written region returns zeros.
  (`MemStore`'s bytearray zero-inits; posix holes read as zeros from the OS.)
- **Write extends**: writing past the current size grows the file.
  (`MemStore::write_at` updates `size`; `os.pwrite` extends.)
- **Positional I/O**: every read/write names an explicit offset — no shared
  file cursor. This is the **re-entrancy invariant** (see
  [`ioresult-as-generators.md`](../explanation/ioresult-as-generators.md)):
  driving the same generator from the same point twice is safe, and
  concurrent generators don't corrupt each other's offset.
- **`size` is synchronous**: not a request — a direct query the pager uses.
- **Error → `CompletionError`**: a failed `os.*` call (posix) becomes a
  `CompletionError(kind="io error")`; the memory backend has no failure mode
  (RAM ops don't fail).

## `FileSyncType` semantics

| Variant | `MemoryFile.psync` | `PosixFile.psync` |
|---|---|---|
| `Fsync` | no-op (returns `0`) | `os.fsync(fd)` |
| `FullFsync` | no-op (returns `0`) | `os.fsync(fd)` |

**Known simplification:** Rust's `unix.rs` calls `F_FULLFSYNC` on macOS for
`FullFsync` (flushes the disk write cache; regular `fsync` may not). pyturso
calls `os.fsync` for *both* variants on all platforms — the distinction is a
macOS-specific mechanism with no behavioural effect on Linux, and the project
pins concept parity, not mechanism (pyturso/io/README.md). The TODO reference
`backend-matrix.md` records this; revisit only if a macOS durability
corpus case distinguishes them.

## File identity (the one real divergence)

| | Memory | Posix |
|---|---|---|
| `open_file("a")` then `open_file("a")` | **same** `bytearray` store (both handles see each other's writes) | two **independent** fds into the **same** OS file (writes visible to both via the file) |

The memory backend shares the store so a pager and a WAL can hold one
in-memory database through two handles — matching SQLite's "one backing store
per name". The posix backend does it the OS way: the file is the shared
backing; each handle is its own fd. Both satisfy the protocol; tests that
assert shared-store semantics must use `MemoryIO`.

## When to use which

| Need | Backend |
|---|---|
| Fast, deterministic unit tests (no tmp files, no cleanup) | `MemoryIO` |
| Testing real-file behaviour (persistence, fd semantics) | `PosixIO` (tmp file via pytest `tmp_path`) |
| A test that must pause I/O mid-flight | either — `StepDriver` works on any backend |
| Future: a corrupt-input / partial-write test | `MemoryIO` (inject failure via `StepDriver.fail`) |

## Not ported (mechanism, not concept)

Deferred backends / capabilities (see
[`ioresult-as-generators.md`](../explanation/ioresult-as-generators.md)):

- `io_uring` (`core/io/io_uring.rs`) — Linux ring I/O.
- `WinIOCP` (`core/io/win_iocp.rs`) — Windows I/O completion ports.
- File locking (`core/io/unix.rs` / `windows_lock.rs`) — until multi-process
  questions matter; single process assumed.
- VFS extension hooks (`core/io/vfs.rs`).
- `MemoryYieldIO` (`core/io/memory_yield.rs`) — Rust's forced-yield test
  backend; pyturso's `StepDriver` provides the same capability differently.
