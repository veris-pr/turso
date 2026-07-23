# HOWTO — tests/differential

Build and operate the three-way harness (design in [README.md](README.md)).

Build order (Phase 0):
1. Engine adapters: `sqlite3` in-process; `tursodb` subprocess (env
   `TURSODB_BIN`, else `cargo run -q --bin tursodb -- -q` from repo root);
   pyturso in-process behind the same adapter interface.
2. Normalization layer — one canonical rendering (see README rules). Write it
   as pure functions with unit tests; normalization bugs masquerade as parity
   bugs and waste days.
3. Comparator (multiset vs ordered) + reporter (per-case verdict:
   PASS / DIVERGENT / NOT-IMPLEMENTED / ORACLE-DISAGREEMENT / ERROR).
4. Corpus discovery + `-k`-style filtering; nonzero exit on red for CI use.

Operating:
- Add cases per the corpus HOWTOs; regenerate expectations only via the
  harness flag; review diffs.
- ORACLE-DISAGREEMENT (sqlite3 vs tursodb) -> quarantine the case and
  investigate; a real turso divergence is an upstream bug report
  (see repo CONTRIBUTING.md) — the contribution pipeline, not noise.
- Phase 11 adds the scripted two-connection mode with turso as the only
  oracle.
