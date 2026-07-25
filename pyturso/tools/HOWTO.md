# HOWTO — tools

What this folder is: [README.md](README.md). Tools are built the moment a
phase first needs them (the table in README gives the phase per tool) and are
never allowed to rot — they are the project's instruments.

## Rules for any tool

1. `python -m tools.<name>`, argparse, stdlib only.
2. **Read-only** on inspected files — a tool must never mutate its subject.
   (`mkdb.py` creates *new* fixture files; that is its one job.)
3. Stable, line-oriented output so tools compose with `diff`/`grep`; version
   any format change consciously (the differential workflows depend on it).
4. Tools may import `pyturso.*` read paths; engine code never imports tools.
5. Each tool ships with a how-to doc in the relevant module's Diátaxis tree
   (pagehex → docs/storage/how-to/, explain_diff → docs/translate/how-to/).

## Build notes per tool

- **`mkdb.py` (Phase 0):** input is a plain SQL script; executes it via
  stdlib sqlite3 into a target path. Deterministic: fixed `PRAGMA page_size`,
  no wall-clock content. Fixture scripts are committed; fixture binaries are
  not (rebuilt on demand into a gitignored cache).
- **`dbdump.py` (Phase 1):** grows with the reader — start with header
  fields, add schema listing, then full-table dumps. Its output vs sqlite3
  `SELECT *` is the Phase 1 gate, so keep its row rendering identical to the
  harness's canonical form (import the same normalization code).
- **`pagehex.py` (Phase 1):** hexdump with a right-hand annotation column
  (field names, cell boundaries, varint spans). Build it *while* writing
  `sqlite3_ondisk.py` — it pays for itself the first time a decode is off by
  one byte.
- **`explain_diff.py` (Phase 5):** runs `EXPLAIN <sql>` via tursodb
  subprocess and via pyturso; aligns structurally (by opcode sequence, not
  addresses — addresses will differ); marks insert/delete/change lines.
- **`dbcompare.py` (Phase 7):** logical twin comparison: schema objects, then
  per-table sorted dumps; `--dbhash` flag shells to the repo's `tools/dbhash`
  when built.
- **`walinfo.py` (Phase 8):** header, per-frame page/commit info, checksum
  verify; a `--follow` of frame-lookup for one page number is worth the ten
  extra lines when debugging recovery.
- **`trace_fmt.py` (Phase 5+):** consumes the VM's trace stream; aligns
  register writes under their opcode; `--registers r1,r5` filtering.
