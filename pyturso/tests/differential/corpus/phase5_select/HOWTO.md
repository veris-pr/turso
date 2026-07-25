# HOWTO — corpus/phase5_select

First SQL-driven cases: one-table `SELECT cols FROM t [WHERE simple-pred]
[LIMIT n]` — the Phase 5 pipeline exactly, nothing more. Keep predicates to
single comparisons; expression breadth belongs to phase6_where.
