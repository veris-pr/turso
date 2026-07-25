# PREREQUISITES — io

Gate before [TODO.md](TODO.md). Cites resolve in
[READING.md](../../READING.md#citation-index).

- [ ] Python generators at *protocol* depth: what `send(x)` returns, where
      execution resumes, how `throw()` surfaces inside the generator, what
      `yield from` delegates (incl. return values). Write a toy
      two-step generator and drive it by hand before starting. → PEP 342,
      PEP 380; Python reference.
- [ ] Blocking vs non-blocking I/O, and what a *completion-based* model is
      (submit request → get completion) vs a readiness model — you are
      modeling the former. → OSTEP ch. "I/O Devices"; skim "Lord of the
      io_uring"-style intros for flavor.
- [ ] The syscalls being wrapped: `pread`/`pwrite` (offset-explicit, why
      that matters vs seek+read), `fsync` and what it does/doesn't
      guarantee. → TLPI file-I/O chapter (T); OSTEP persistence intro.
- [ ] Why re-entrancy: what it means for an operation to suspend at an I/O
      point and be resumed later, and why the engine wants that shape. →
      repo `docs/agent-guides/async-io-model.md` (this is the module's
      spec; read it before the gate, not after).
- [ ] Injectable time: why `time.time()` in engine code destroys test
      determinism. → no reading needed — but be able to argue it.

Can't check the generator box? Stop — everything in this module and every
later module builds on it. One evening with PEP 342 + experiments pays for
the whole project.
