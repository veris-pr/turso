# HOWTO — storage

What the module is: [README.md](README.md). Three phases of work live here:
1 (read), 7 (write), 8 (WAL). This folder gets the most calendar time of the
project; work in the smallest verifiable steps below.

## Phase 1 — read path

1. **`sqlite3_ondisk.py`**, in this order: varint decode → 100-byte header
   struct → page-type dispatch → cell pointer array → leaf table cell
   (rowid + payload) → raw record decode → interior table cell → overflow
   chain → index cells. After each step, point [tools/pagehex.py](../../tools/HOWTO.md)
   at a real fixture and *look*.
   Gotcha: page 1's cell content area starts after the 100-byte header;
   page numbering is 1-based; the rightmost pointer of interior pages lives
   in the page header, not a cell.
2. **`pager.py` (minimal)** — just `read_page(n)` through the io layer with
   `page_cache.py` in front. Resist building more; Phase 7 grows it.
3. **`btree.py` (read half)** — order: full-scan of a single leaf →
   interior descent (rewind to leftmost) → `next()` across page boundaries →
   `seek(rowid)` → overflow payload assembly → index-tree variants.
   Cursor state is explicit (page stack + cell index), because Phase 7's
   balance will invalidate cursors and you need a place to hang that rule.

**Gate:** dbdump == sqlite3 `SELECT *` on the Phase 1 fixture checklist
(`corpus/phase1_read/HOWTO.md`).

## Phase 7 — write path (the wall; take small steps)

1. `pager.py`: dirty-page tracking, `allocate_page`/`free_page` (freelist
   trunk/leaf format), flush ordering.
2. `btree.py` insert, easy cases first: leaf has room → leaf overflow into
   overflow chain → **split** (leaf, then interior propagation, then root
   split growing the tree) → delete → underflow/merge. Read the balance code
   in `core/storage/btree.rs` once per sub-step, not once for all.
3. After *every* sub-step: fixed-seed randomized insert/delete unit tests
   asserting key order + `PRAGMA integrity_check` via sqlite3 on the written
   file. Never advance on a red integrity check.
4. Draw `docs/storage/explanation/btree-balancing-in-pictures.md` as you go —
   it is a phase deliverable and the act of drawing catches bugs.

**Gate:** M3 (`PLAN.md`), corpus/phase7_writes green with ride-alongs.

## Phase 8 — WAL & transactions

1. `checksum.py` (test vectors first — generate them from a real WAL file
   sqlite3 produced). 2. `wal.py` read side: parse header/frames of a real
   sqlite3 WAL; frame-lookup (latest frame for page N before mxFrame).
3. Append + commit record. 4. Recovery on open (torn-frame detection via
   checksums). 5. Checkpoint. 6. Wire pager fetch order: cache → WAL → file.
7. Crash injection via `io.StepDriver` at the yield points listed in
   `corpus/phase8_txn/HOWTO.md`.

**Gate:** M4 recovery matrix; sqlite3 opens and reads the pyturso WAL'd db.

## Standing rules

- All I/O through generators — no `os.*` calls in this folder outside the io
  backends. - Corrupt input raises `Corrupt`. - Byte offsets appear only in
  `sqlite3_ondisk.py`; if another file needs an offset, it is missing an
  accessor here. - Reference docs (`docs/storage/reference/`) update in the
  same commit as format code.
