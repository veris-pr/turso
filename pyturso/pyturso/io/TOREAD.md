# TOREAD — io

Read before/while working [TODO.md](TODO.md). Levels refer to
[../../READING.md](../../READING.md).

## Before starting

- [ ] Repo guide: `docs/agent-guides/async-io-model.md` — **the** document
      this module ports; read twice.
- [ ] READING Level 2: OSTEP "I/O Devices" chapter (36) — what a completion
      *is* at the hardware level.
- [ ] Python docs: generators & `send()`/`throw()`/`yield from`
      (docs.python.org "Generators", PEP 342, PEP 380) — the mechanism you
      are standing the whole convention on.
- [ ] READING Level T: the team's *In Search of a Faster SQLite* paper /
      Turso blog on async I/O — the *why* behind `IOResult`.

## Rust source (read for shape, then port)

- [ ] `core/io/mod.rs` — the `IO`/`File` traits and `IOResult`.
- [ ] `core/io/completions.rs` — completion types.
- [ ] `core/io/memory.rs`, `core/io/unix.rs` — the two backends you mirror.
- [ ] Skim only: `core/io/io_uring.rs` — see what real async buys; you are
      deliberately not porting it (note what you notice for
      `docs/io/explanation/what-we-dont-port.md`).

## Before `posix.py`

- [ ] READING Level 2: TLPI file-I/O chapter sections on `pread`/`pwrite`
      and `fsync` vs `fdatasync`.
- [ ] Dan Luu, "Files are hard" — first read (you will re-read at Phase 8).

## Docs you will write (Diátaxis deliverables, from docs/io/README.md)

`ioresult-as-generators.md` (keystone) · `what-we-dont-port.md` ·
both reference docs · tutorial `drive-a-generator-through-io.md`.
