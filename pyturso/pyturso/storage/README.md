# pyturso.storage — On-disk format, pager, B-tree, WAL

**Ports:** `core/storage/` — `sqlite3_ondisk.rs`, `pager.rs`, `page_cache.rs`,
`buffer_pool.rs`, `btree.rs`, `wal.rs`, `checksum.rs`
**Phases:** 1 (read path) · 7 (write path) · 8 (WAL & transactions)
**This is the heart of the project and gets the most calendar time.**

## What this module is

Everything between "bytes in a file" and "a cursor over rows". The database
file is SQLite-format — pyturso reads and writes *real* `.db` files that
`sqlite3` and `tursodb` accept, which is what makes the whole port verifiable.

```
                 ┌────────────── storage ──────────────┐
 vdbe cursors ──►│ btree ──► pager ──► page_cache ──►  │──► io backends
                 │             │                       │
                 │            wal  (frames, checkpoint)│
                 └─────────────────────────────────────┘
```

Layer responsibilities, bottom-up:

- **`sqlite3_ondisk.py`** (`sqlite3_ondisk.rs`) — pure format knowledge, no
  state: the 100-byte header, page layouts (interior/leaf × table/index),
  cell formats, varints, overflow chains, freelist pages. If a byte offset
  is mentioned anywhere in pyturso, it lives here.
- **`pager.py`** (`pager.rs`) — the page authority: fetch page N (cache → WAL
  → main file), mark dirty, allocate/free pages (freelist), flush, and drive
  commit. Owns the transaction read/write state.
- **`page_cache.py`** (`page_cache.rs`) — in-memory cache of decoded pages
  with an eviction policy; `buffer_pool.py` (`buffer_pool.rs`) — raw buffer
  reuse (may collapse into the cache; decision recorded in the docs).
- **`btree.py`** (`btree.rs`) — the structure: `BTreeCursor` for
  rewind/next/seek over table (rowid-keyed) and index (record-keyed) trees;
  Phase 7 adds insert/delete with cell overflow, page split, and **balance**
  — the single hardest algorithm in the port.
- **`wal.py`** (`wal.rs`) + `checksum.py` (`checksum.rs`) — write-ahead log:
  frame format, salts/checksums, commit records, read-path frame lookup,
  checkpoint back into the main file, recovery on open.

Not ported (recorded here so absence is a decision, not an oversight):
`encryption.rs`, `shared_wal_coordination.rs`, `slot_bitmap.rs`,
`subjournal.rs`, `database.rs` multi-DB attach plumbing, `state_machines.rs`
formalism (generators play that role) — revisit at Phase 8/11 boundaries.

## Invariants to carry over (from the Rust and `docs/agent-guides/`)

- A page is never half-valid: decode fully or raise; corrupt input raises
  `Corrupt`, never returns garbage (Turso principle: *crash > corrupt*).
- Every byte written is either in the WAL or the main file — never lost in a
  cache; commit ordering is what makes crash recovery provable (Phase 8 gate).
- B-tree ops never hold references across a balance; cursors re-seek —
  the Rust encodes this in ownership, pyturso encodes it in cursor state
  validity rules documented in the module docs.

## Docs

Diátaxis tree: [../../docs/storage/README.md](../../docs/storage/README.md) —
includes the mandatory "B-tree balancing, in pictures" explanation
(Phase 7 deliverable).
