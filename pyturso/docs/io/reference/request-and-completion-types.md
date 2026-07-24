# Request & completion types — reference

**Status:** current · **Phase:** 1 · **Cites:** `pyturso/io/protocol.py`;
Rust: `core/io/mod.rs` (`File`/`IO` traits, `FileSyncType`),
`core/io/completions.rs` (`Completion`, `CompletionType`, `CompletionError`).

Austere catalog of every type crossing the generator boundary. Updated in the
same commit as any change to [`pyturso/io/protocol.py`](../../pyturso/io/protocol.py).

## Requests

A generator yields a *request*: a frozen dataclass describing the operation.
Requests are dumb data — they carry the `file`, the offset, and the payload;
they never perform the I/O. A backend `File` dispatches on the concrete type.

| Type | Rust port | Fields | Success payload |
|---|---|---|---|
| `ReadRequest` | `File::pread(pos, c)` | `file: File`, `offset: int`, `n: int` | bytes read (may be short at EOF) |
| `WriteRequest` | `File::pwrite(pos, buf, c)` | `file: File`, `offset: int`, `data: bytes` | bytes written (`int`) |
| `SyncRequest` | `File::sync(c, sync_type)` | `file: File`, `sync_type: FileSyncType` | `0` |
| `TruncateRequest` | `File::truncate(len, c)` | `file: File`, `length: int` | `0` |

All requests are `@dataclass(frozen=True)` — value-equal and hashable for test
assertions (request identity = invariant).

`Request` is the union: `ReadRequest | WriteRequest | SyncRequest | TruncateRequest`.

### Field semantics

- **`file`** — the backend handle (`File` Protocol) the request targets. Every
  request names its file so a driver needs no ambient state.
- **`offset` / `length`** — byte offsets, zero-based, *positional* (never a
  shared cursor — see re-entrancy in
  [`ioresult-as-generators.md`](../explanation/ioresult-as-generators.md)).
- **`n` (ReadRequest)** — number of bytes requested. The completion may carry
  fewer (short read at EOF) or zero (at/past EOF). Never an error.
- **`data` (WriteRequest)** — the bytes to write. Empty `data` is valid
  (writes nothing, returns count `0`).

## `FileSyncType`

Ports `core::io::FileSyncType`.

| Variant | Rust | pyturso backend behaviour |
|---|---|---|
| `Fsync` | `FileSyncType::Fsync` | `os.fsync` |
| `FullFsync` | `FileSyncType::FullFsync` (macOS `F_FULLFSYNC`) | `os.fsync` (no `F_FULLFSYNC` call — see backend-matrix) |

## Completions

A driver `send()`s a `Completion` back into the generator to resume it. A
completion carries exactly one of three payloads.

| Field | Set when | Unwrap |
|---|---|---|
| `read_data: bytes \| None` | a successful `ReadRequest` | `unwrap_read() -> bytes` |
| `count: int \| None` | a successful `WriteRequest`/`SyncRequest`/`TruncateRequest` | `unwrap_count() -> int` |
| `error: CompletionError \| None` | any failed request | raises the carried error |

- `is_error` — `True` iff `error is not None`.
- `unwrap_read()` / `unwrap_count()` **raise** on a failure completion (the
  carried `CompletionError`), or raise `TypeError` if the completion is the
  wrong shape for the unwrap (a request/completion type mismatch — a
  programming error, caught loudly, not `None` as garbage).

### Special values (not falsy-traps)

- `count == 0` is **valid** (`Sync`/`Truncate` return 0). Not treated as
  missing.
- `read_data == b""` is **valid** (short read at EOF). Unwraps cleanly.

## `CompletionError`

Ports `core::CompletionError` (the subset surfaced through the generator
protocol). Defined in `pyturso/io/protocol.py` (the I/O layer's own failure
vocabulary, mirroring how Rust nests `CompletionError` inside `LimboError`).

| `kind` | Meaning | Raised by |
|---|---|---|
| `"io error"` | an `os.*` call failed (posix backend) | `pread`/`pwrite`/`fsync`/`ftruncate` |
| `"short read"` | (reserved for explicit short-read checks) | reader layer |
| `"short write"` | (reserved) | WAL |
| `"checksum mismatch"` | (reserved) | WAL recovery |

Higher layers map `CompletionError` → the right `pyturso.errors` class (e.g.
`Corrupt`, `InternalError`); the mapping lives in `pyturso.errors`.

## Protocols (structural)

| Protocol | Rust port | Methods |
|---|---|---|
| `File` | `trait File` | `pread`, `pwrite`, `psync`, `ptruncate`, `size` |
| `IO` | `trait IO` | `open_file(path, *, flags, direct)` |

Both are `@runtime_checkable` Protocols — backends conform structurally
(without inheritance); `isinstance(backend, File)` validates at construction.
`size()` is a synchronous query (not a request) used by the pager.

## Dispatch (driver side)

`pyturso/io/driver.py` dispatches a yielded request to its `file`'s method by
`isinstance`:

```python
if isinstance(req, ReadRequest):    return f.pread(req)
if isinstance(req, WriteRequest):   return f.pwrite(req)
if isinstance(req, SyncRequest):    return f.psync(req)
if isinstance(req, TruncateRequest):return f.ptruncate(req)
```

An unknown request type raises `TypeError` — exhaustiveness, not silent skip.
