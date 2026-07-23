# HOWTO — from_sqltest

Behavioral cases ported from `sqlite/conformance/sqlite-sqltests/` (repo root).

1. Pick a `.sqltest` file relevant to the current phase; add a row to
   [MANIFEST.md](MANIFEST.md) *first* (status: in-progress).
2. Port only behavioral content: SQL in, rows/error out. Skip directives that
   exercise Rust/harness mechanics; note skips in the manifest row.
3. Keep provenance: one corpus file per source file, same base name, header
   comment citing the source path.
4. Set the manifest status: ported / partial (say what's missing) /
   skipped (say why). The manifest is the scope ledger — no silent gaps.
