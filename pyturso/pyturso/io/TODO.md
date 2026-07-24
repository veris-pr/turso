# TODO — io (Phase 1)

Work order rationale: [HOWTO.md](HOWTO.md). Check items off in order; each
lands with its test in the same commit.

- [x] `protocol.py`: `ReadRequest`, `WriteRequest`, `SyncRequest`,
      `TruncateRequest` dataclasses (file, offset, length/data) + completion
      payload types + `File` and `IO` Protocols.
- [x] `memory.py`: `MemoryFile`/`MemoryIO` — bytes-backed, supports all four
      requests; out-of-range reads return short data exactly like `os.pread`
      (decide + document in backend-matrix doc).
- [x] `driver.py::run_to_completion(gen, io)` — services yields, `send()`s
      completions, propagates raised errors, returns the generator's value.
- [x] `driver.py::StepDriver` — `pending()` exposes the current request;
      `step(completion=None)` advances one yield; `fail(exc)` injects an
      error completion; `abandon()` closes the generator.
- [x] Unit tests: a toy two-read generator driven by StepDriver — assert
      request sequence, injected-failure propagation, and clean close.
- [x] `posix.py`: `os.open`/`pread`/`pwrite`/`fsync`/`ftruncate`-backed File;
      same unit suite runs against memory and posix backends (tmp files).
- [x] `clock.py`: `Clock` Protocol + `SystemClock` + `FixedClock`.
- [x] Convention documented: draft
      `docs/io/explanation/ioresult-as-generators.md` (keystone doc) with the
      "In Turso" section; flip its status row.
- [x] Reference docs: `request-and-completion-types.md`, `backend-matrix.md`.

Exit: Phase 1 storage code can be written without ever touching `os.*`
directly, and a test can pause any I/O mid-flight.
