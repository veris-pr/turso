# TOREAD — tools

Tools ride on the owning module's reading — no curriculum of their own.
Per tool, the relevant slice:

- `mkdb.py`: Python stdlib `sqlite3` module docs (executescript, PRAGMAs at
  connect time).
- `pagehex.py` / `dbdump.py`: the storage TOREAD Phase 1 list — the format
  doc *is* the tool spec.
- `explain_diff.py` / `trace_fmt.py`: vdbe TOREAD (opcode doc + explain
  format); `scripts/diff.sh` at repo root for the pattern being mirrored.
- `dbcompare.py`: repo `tools/dbhash` source (what "logical content" hashes).
- `walinfo.py`: the storage TOREAD Phase 8 list (WAL format section).

One general read, worth it early:

- [ ] READING L6: *How SQLite Is Tested* §on test harnesses and coverage —
      why serious projects grow an instrument shed; this folder is yours.
