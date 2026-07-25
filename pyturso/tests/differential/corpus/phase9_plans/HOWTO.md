# HOWTO — corpus/phase9_plans

Planner cases, two kinds: behavioral (joins, index-reachable predicates —
rows must match the oracles) and structural (EXPLAIN-based assertions that a
given query uses an index / elides a sort). Every behavioral case must also
pass with the optimizer force-disabled.
