# TODO — storage

Work order rationale: [HOWTO.md](HOWTO.md). Three phase blocks; never start
a block with the previous one red.

## Phase 1 — read path

- [ ] `sqlite3_ondisk.py::read_varint` / `write_varint` + boundary unit tests
      (1–9 bytes, ±1 at each width edge).
- [ ] Header dataclass: all 100 bytes parsed; reject bad magic (`Corrupt`).
- [ ] Page decode: page-type dispatch, page-header fields, cell pointer
      array; page-1 offset handled; `pagehex.py` shows it annotated.
- [ ] Leaf table cells: rowid varint + payload; raw record decode (serial
      types inline until `types/` lands, then refactor onto `types.record`).
- [ ] Interior table pages: keys + child pointers + rightmost pointer.
- [ ] Overflow chains: threshold math from the format doc, chain walk.
- [ ] `pager.py` minimal: `read_page(n)` through io + `page_cache.py`
      (dict cache, no eviction yet — note the debt).
- [ ] `btree.py::BTreeCursor` (table trees): `rewind` → `next` across page
      boundaries → `seek(rowid)` (binary search within page, descent across
      pages) → payload assembly incl. overflow.
- [ ] Index B-trees: cursor over index cells (record keys).
- [ ] `tools/dbdump.py` complete; **gate:** dump == sqlite3 `SELECT *` on the
      full Phase 1 fixture checklist (`corpus/phase1_read`).

## Phase 7 — write path

- [ ] Pager: dirty tracking, `allocate_page` (freelist pop, else grow),
      `free_page` (trunk/leaf format), flush ordering.
- [ ] Insert, staged: leaf-with-room → payload overflow → leaf split →
      interior propagation → root split (tree grows) — fixed-seed randomized
      test + sqlite3 `integrity_check` green after each stage.
- [ ] Delete: cell removal → free-block coalescing → underflow/balance.
- [ ] Rowid allocation (max+1 semantics; AUTOINCREMENT out of scope, ledger it).
- [ ] CREATE TABLE path: allocate root, write `sqlite_schema` row.
- [ ] `btree-balancing-in-pictures.md` drawn (phase deliverable).
- [ ] **Gate:** M3 demo + `corpus/phase7_writes` with ride-alongs green.

## Phase 8 — WAL & transactions

- [ ] `checksum.py` with test vectors extracted from a real sqlite3 WAL.
- [ ] `wal.py` read side: header/frames parse, frame-lookup map.
- [ ] Append path: frames on commit, commit record, salts.
- [ ] Recovery on open: checksum-based torn-frame cutoff.
- [ ] Checkpoint: frames → main file, WAL reset.
- [ ] Pager fetch order becomes cache → WAL → file.
- [ ] Crash-injection tests at the three yield points (`corpus/phase8_txn`).
- [ ] **Gate:** M4 recovery matrix; sqlite3 reads the pyturso WAL'd db.
