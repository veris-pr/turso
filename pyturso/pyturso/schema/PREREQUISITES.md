# PREREQUISITES — schema

Gate before [TODO.md](TODO.md). Cites resolve in
[READING.md](../../READING.md#citation-index).

- [ ] System catalogs: every engine stores its schema *in itself*; the
      bootstrap consequence (read the catalog with the same machinery it
      describes). → CMU 15-445 catalog segment (C).
- [ ] `sqlite_schema` contract: the five columns, what `rootpage` means per
      object type, why `sql` stores original text. → SQLite File Format
      doc §schema storage (D).
- [ ] The rowid: every ordinary table is keyed by a 64-bit rowid, and
      exactly when `INTEGER PRIMARY KEY` aliases it — this module's most
      consequential rule. → SQLite `CREATE TABLE` doc, "ROWIDs and the
      INTEGER PRIMARY KEY" section (D).
- [ ] Cache invalidation shape: what a schema cookie is for, what goes
      wrong without staleness checks.
- [ ] Working prerequisites from earlier phases: Phase 1 cursor (walk page
      1) and Phase 3 parser (CREATE statements parse). Verify both green
      before starting — this module is where they meet.
