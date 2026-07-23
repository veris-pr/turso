# TODO — tools

Build each tool at its phase (notes: [HOWTO.md](HOWTO.md)); check off with a
how-to doc linked.

- [ ] **Phase 0 — `mkdb.py`**: SQL script → fixture db via stdlib sqlite3;
      fixed `page_size`; deterministic content only; gitignored output cache.
- [ ] **Phase 1 — `pagehex.py`**: annotated page hexdump (header fields,
      cell pointer array, cell boundaries, varint spans). Build alongside
      `sqlite3_ondisk.py`, not after.
- [ ] **Phase 1 — `dbdump.py`**: header → schema list → full-table dumps
      via pyturso reader; row rendering shared with harness normalization
      (import, don't duplicate). This is the M1 artifact.
- [ ] **Phase 5 — `explain_diff.py`**: `EXPLAIN` via tursodb subprocess vs
      pyturso; structural alignment (opcode sequence, not addresses);
      marks +/-/~ lines.
- [ ] **Phase 5+ — `trace_fmt.py`**: VM trace pretty-printer; register
      filtering (`--registers r1,r5`).
- [ ] **Phase 7 — `dbcompare.py`**: schema + sorted per-table logical diff
      of two db files; `--dbhash` shells to repo `tools/dbhash`.
- [ ] **Phase 8 — `walinfo.py`**: WAL header/frames/checksums/commit
      boundaries; `--follow <pageno>` frame-lookup trace.

Standing: read-only rule, stable line output, `python -m tools.<name>`,
how-to doc per tool in the owning module's docs tree.
