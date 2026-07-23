# HOWTO — corpus/phase1_read

Cases for the Phase 1 file-format reader. No SQL execution yet: each case
pairs a fixture (built by tools/mkdb.py from a committed script) with an
assertion that pyturso's dump equals `SELECT * FROM <t>` via sqlite3.

Coverage checklist (mirrors the Phase 1 exit criteria in ../../../../PLAN.md):
multi-page tables · every serial type incl. 8/9 constants · overflow payloads ·
interior pages at 2+ levels · index B-trees · empty tables · freelist present.
