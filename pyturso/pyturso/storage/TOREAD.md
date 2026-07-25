# TOREAD — storage

The heaviest curriculum of the project. Levels refer to
[../../READING.md](../../READING.md).

## Before Phase 1 (read path)

- [ ] SQLite [File Format doc](https://sqlite.org/fileformat2.html) — first
      full pass (§1–2 carefully: header, pages, cells, varints, records).
- [ ] Repo guide: `docs/agent-guides/storage-format.md`.
- [ ] READING L3: CMU 15-445 storage lectures (pages/heap files) and
      B+-tree lecture — enough to know the vocabulary.
- [ ] *Database Internals* Part I, B-tree basics chapters (structure &
      navigation; implementation details wait for Phase 7).
- [ ] Prereq from earlier module: `docs/io/explanation/ioresult-as-generators.md`
      (your own keystone doc).
- Rust, per TODO stage (not upfront): `core/storage/sqlite3_ondisk.rs`
  (decode paths) → `core/storage/pager.rs` (fetch path only) →
  `core/storage/btree.rs` (traversal/seek paths only).

## Before Phase 7 (write path)

- [ ] READING L4 anchor: *Modern B-Tree Techniques* ch. 1–3.
- [ ] *Database Internals* B-tree implementation chapters (splits, merges,
      rebalancing).
- [ ] SQLite File Format doc: freelist + pointer-map sections; re-read cell
      overflow threshold math.
- [ ] 15-445 B+-tree design lecture (again — it lands differently now).
- [ ] Rust: `core/storage/btree.rs` balance code — one sub-step at a time,
      per the HOWTO; `core/storage/pager.rs` allocate/free + dirty paths.

## Before Phase 8 (WAL)

- [ ] SQLite [Atomic Commit](https://sqlite.org/atomiccommit.html) — the
      single best document on commit durability anywhere; then
      [WAL doc](https://sqlite.org/wal.html).
- [ ] Repo guide: `docs/agent-guides/transaction-correctness.md`.
- [ ] READING L2 re-read: OSTEP crash-consistency + journaling chapters.
- [ ] Dan Luu "Files are hard" (second read) + *All File Systems Are Not
      Created Equal* (OSDI '14).
- [ ] Rust: `core/storage/wal.rs`, `core/storage/checksum.rs`.

## Docs you will write

Phase 1: file-header / page-layout / varint reference docs, B-tree
explanation, pagehex how-to, byte-by-byte tutorial. Phase 7:
`btree-balancing-in-pictures.md` (mandatory), freelist reference,
verify-a-written-file how-to. Phase 8: WAL reference, `why-wal.md`,
crash-recovery how-to, commit tutorial. (Status table: `docs/storage/README.md`.)
