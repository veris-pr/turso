# PREREQUISITES — package root (API & assembly)

Gate before [TODO.md](TODO.md). Cites resolve in
[READING.md](../READING.md#citation-index).

## Before Phase 0 (`errors.py`)

- [ ] Python exception-hierarchy design: base class + variants, why
      catching on class beats parsing messages. → Python docs.
- [ ] SQLite's result-code taxonomy at skim depth (OK/ROW/DONE vs error
      codes) — your hierarchy mirrors its spirit. → sqlite.org result
      codes doc (D).

## Before Phase 5 (Database/Connection/Statement)

- [ ] The prepare/step/finalize lifecycle as a *protocol*: what state a
      prepared statement holds, what reset does, why step returns
      row-or-done. → SQLite C API intro (D) — the single most important
      read for this folder.
- [ ] Sessions vs the store: what belongs to a Connection (transaction
      state, schema view) vs the Database (file, pager, WAL) — be able to
      sort five example fields into the right owner. → *Architecture of a
      Database System* §process/state discussion (P); `core/connection.rs`
      skim.
- [ ] Context managers (`__enter__`/`__exit__`) and iterator protocol —
      the Pythonic face of the lifecycle.
- [ ] Working prereqs green: parser, schema, translate, vdbe skeletons
      (this folder only wires; every wire must have both ends).
