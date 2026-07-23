# HOWTO — api/reference

Austere lookup material: tables, formats, catalogs. No narrative, no
persuasion — accuracy and completeness only.

The work:
1. Reference docs are written **alongside the code** and updated **in the
   same commit** as any behavior change they describe. This is a hard rule;
   a stale reference is worse than none.
2. Scope-ledger references (grammar, opcodes, functions, dot-commands) track
   every item as: supported / planned(phase N) / out-of-scope. No silent gaps.
3. Cite the Rust source for every table (file, and item name) so claims are
   checkable against the source of truth.
4. Flip the status in [../README.md](../README.md).
