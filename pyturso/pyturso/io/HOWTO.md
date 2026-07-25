# HOWTO — io

What the module is: [README.md](README.md). Phase 1, and deliberately the
*first* engine code written: it establishes the generator convention every
later module uses.

## Work order

1. **`protocol.py`** — read `core/io/mod.rs` + `completions.rs` for the
   shapes, then define: request dataclasses (`ReadRequest`, `WriteRequest`,
   `SyncRequest`, `TruncateRequest`), completion payloads, and the
   `File`/`IO` Protocols. Keep requests dumb data.
2. **`memory.py`** — dict-of-offsets backend. Ten lines of logic; its job is
   to make the protocol real and the tests fast.
3. **`driver.py`** — two drivers:
   `run_to_completion(gen, io)` (services each yielded request immediately,
   `send()`s the completion back, returns the generator's return value), and
   `StepDriver` (advances one yield at a time, exposes the pending request,
   lets tests inject failures or stop — this is the crash/interleaving hook
   the whole project leans on later).
4. **`posix.py`** — `os.pread`/`os.pwrite`/`os.fsync`. Decide and document
   fsync semantics (data vs metadata) in the backend-matrix reference doc.
5. **`clock.py`** — `Clock` protocol + real and fixed implementations.

## The convention to establish (copy into the keystone doc)

```python
def read_page(file, page_size, page_no):
    data = yield ReadRequest(file, offset=(page_no - 1) * page_size, n=page_size)
    return decode_page(data)
```

- Engine code **never** calls a backend directly — it yields requests.
- A generator that calls another generator uses `yield from` (composition ==
  nested state machines, same as Rust state machines calling state machines).
- Convenience wrappers (`run_to_completion`) live at API boundaries
  (statement.run(), tools), never inside engine internals.

## Verify

Unit tests drive `read_page`-style generators through `StepDriver`: assert
the exact request sequence, inject a failure completion mid-way, assert clean
error propagation. If testing this feels awkward now, fix it now — Phases 8
and 11 depend on this driver being pleasant.

## Write the keystone doc now

`docs/io/explanation/ioresult-as-generators.md` gets drafted in this phase
while the analogy is fresh, with the "In Turso" section citing
`core/io/mod.rs` and `docs/agent-guides/async-io-model.md`.
