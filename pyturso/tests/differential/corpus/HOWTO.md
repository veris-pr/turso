# HOWTO — corpus

Each subdirectory is a phase's behavioral corpus; its HOWTO states what
belongs there. Shared rules:

1. A case is a plain `.sql` script; front-matter comments carry metadata:
   `-- setup: fixture=<script>` (built via tools/mkdb.py) and
   `-- expect-error: <ErrorClass>` for error cases.
2. Cases assert *behavior*, so they must be sqlite3-valid too — if sqlite3
   and tursodb disagree on a case, quarantine it under `_quarantine/` with a
   note; if turso's divergence looks unintended, report it upstream (that is
   the contribution pipeline working).
3. Expected outputs are never hand-written: the harness records the oracle's
   normalized output. Regenerate via the harness flag, review the diff.
4. Ordered comparison only when the query has ORDER BY; multiset otherwise
   (the harness enforces this).
5. A case that a phase's code cannot yet run is fine — red gates are the
   phase's to-do list, and NOT-IMPLEMENTED is a distinct, honest status.
