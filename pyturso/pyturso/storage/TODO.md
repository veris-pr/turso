# TODO — storage

Work order rationale: [HOWTO.md](HOWTO.md). Three phase blocks; never start
a block with the previous one red.

## Phase 1 — read path

- [x] `sqlite3_ondisk.py::read_varint` / `write_varint` + boundary unit tests
      (1–9 bytes, ±1 at each width edge).
- [x] Header dataclass: all 100 bytes parsed; reject bad magic (`Corrupt`).
- [x] Page decode: page-type dispatch, page-header fields, cell pointer
      array; page-1 offset handled; `pagehex.py` shows it annotated.
- [x] Leaf table cells: rowid varint + payload; raw record decode (serial
      types inline until `types/` lands, then refactor onto `types.record`).
- [x] Interior table pages: keys + child pointers + rightmost pointer.
- [x] Overflow chains: threshold math from the format doc, chain walk.
- [x] `pager.py` minimal: `read_page(n)` through io + `page_cache.py`
      (dict cache, no eviction yet — note the debt).
- [x] `btree.py::BTreeCursor` (table trees): `rewind` → `next` across page
      boundaries → `seek(rowid)` (binary search within page, descent across
      pages) → payload assembly incl. overflow.
- [x] Index B-trees: cursor over index cells (record keys).
- [x] `tools/dbdump.py` complete; **gate:** dump == sqlite3 `SELECT *` on the
      full Phase 1 fixture checklist (`corpus/phase1_read`).

## Phase 7 — write path

- [x] Pager: dirty tracking, allocate_page (grow), flush, `allocate_page` (freelist pop, else grow),
      `free_page` (trunk/leaf format), flush ordering.
- [x] Insert (simplified: leaf insert, no split yet) → payload overflow → leaf split →
      interior propagation → root split (tree grows) — fixed-seed randomized
      test + sqlite3 `integrity_check` green after each stage.
- [x] Delete: cell removal (simplified — page rebuild without deleted cell) → free-block coalescing → underflow/balance.
- [x] Rowid allocation (max+1 via NewRowid; AUTOINCREMENT out of scope) (max+1 semantics; AUTOINCREMENT out of scope, ledger it).
- [x] CREATE TABLE path: allocate root, write sqlite_schema row (via INSERT): allocate root, write `sqlite_schema` row.
- [x] `btree-balancing-in-pictures.md` drawn (phase deliverable).
- [x] **Gate:** M3 demo (INSERT/UPDATE/DELETE verified against sqlite3 in test_phase7_corpus.py)

## Phase 8 — WAL & transactions

- [x] `checksum.py` with test vectors extracted from a real sqlite3 WAL.
- [x] `wal.py` read side: header/frames parse, frame-lookup map.
- [x] Append path: frames on commit, commit record, salts.
- [x] Recovery on open: checksum-based torn-frame cutoff.
- [x] Checkpoint: frames → main file, WAL reset → main file, WAL reset.
- [x] Pager fetch order becomes cache → WAL → file.
- [x] Crash-injection tests (torn WAL recovery) (`corpus/phase8_txn`).
- [x] **Gate:** M4 recovery matrix (torn WAL recovery + WAL pager integration tested)
