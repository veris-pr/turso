# TODO — schema (Phase 4)

Work order rationale: [HOWTO.md](HOWTO.md).

- [x] `objects.py`: `Column` (name, declared type, affinity, primary-key
      info), `Table` (name, columns, rootpage, rowid-alias column index or
      None), `Index` (name, table, columns + sort orders + collations,
      rootpage), `Schema` (name-keyed maps, schema cookie).
- [x] `load.py`: cursor over page 1 → iterate `sqlite_schema` rows → parse
      `sql` with the Phase 3 parser → materialize objects; NULL-`sql`
      internal rows (autoindexes) represented without parsing.
- [x] Rowid-alias detection ported exactly from `core/schema.rs` — unit
      tests for each spelling *before* implementing (see HOWTO gotcha).
- [x] Unparseable stored `sql` raises `Corrupt`-class — test with a doctored
      fixture.
- [x] `is_stale()` seam: cookie captured at load; full wiring deferred to
      Phase 8 (leave a pointer comment + doc note, not code).
- [x] Cross-check tests vs sqlite3 on fixtures with: quoted/mixed-case
      names, multi-column DESC indexes, IPK spellings, autoindexes —
      `PRAGMA table_info` / `index_list` / raw `sqlite_schema` agreement.
- [x] WITHOUT ROWID + generated columns: clean rejection + ledger rows.
- [x] Reference doc `object-model.md` + `rowid-alias-rules.md` in the same
      commits as the code they describe.

Exit: Phase 4 criteria in PLAN.md (object model agrees with sqlite3 on all
covered attributes across the fixture set).
