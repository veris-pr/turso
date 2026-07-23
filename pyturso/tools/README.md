# tools — Inspection & diffing tools

**Mirrors in spirit:** `scripts/diff.sh`, `tools/dbhash` (repo root),
the bytecode-comparison workflow in `docs/agent-guides/debugging.md`
**Phase:** 0 onward — tools are built the moment they are first needed and
never deleted; they are the project's instruments.

Every tool is a `python -m tools.<name>` entry point, stdlib-only, and usable
on *any* SQLite database file — not just pyturso-made ones. Building the
inspectors before the engine (Phase 0/1) is deliberate: you learn the format
by writing the microscope.

## Planned tools

| Tool | Phase | What it does |
|------|-------|--------------|
| `mkdb.py` | 0 | build corpus fixture DBs with stdlib sqlite3 from DDL+data scripts (deterministic, committed as scripts not binaries) |
| `dbdump.py` | 1 | walk a database file with pyturso's own reader and dump header, schema, and all rows — the M1 milestone artifact |
| `pagehex.py` | 1 | annotated hexdump of one page: colors/labels for header fields, cell pointer array, cells, varints |
| `explain_diff.py` | 5 | side-by-side EXPLAIN: `tursodb` vs pyturso for a statement; structural (not textual) alignment |
| `walinfo.py` | 8 | dump WAL header, frames, salts/checksums, commit boundaries |
| `dbcompare.py` | 7 | logical comparison of two DB files (schema + full-table dumps); wraps repo `tools/dbhash` when built |
| `trace_fmt.py` | 5+ | pretty-printer for VM `--trace` output (registers, cursors, jumps) |

## Rules

- Tools may only depend on `pyturso.*` read paths — a tool must never mutate
  the file it inspects.
- Output is stable and line-oriented so tools compose with `diff`.
- Each tool gets a how-to doc in the relevant module's Diátaxis tree
  (e.g. pagehex → `docs/storage/`).
