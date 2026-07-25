# HOWTO — translate/expr

Ports `core/translate/expr/` — expression compilation, used by every statement
kind. Phase 5 builds the minimum; Phase 6 completes it.

Port order (each step: read the Rust path, port, corpus cases, next):
1. Literals and column references (register loads, cursor Column ops).
2. Comparison operators **with affinity + collation resolution** — read how
   the Rust decides the applied affinity before emitting; this is where most
   parity bugs live.
3. Arithmetic and string concat, NULL propagation.
4. Logical AND/OR with short-circuit jumps and three-valued logic.
5. IS / IS NOT / ISNULL / NOTNULL.
6. CASE, BETWEEN, IN (value lists), LIKE/GLOB (via functions/string.py).
7. Function calls through the registry.

Rules: emit the same opcode families the Rust emits (check with
tools/explain_diff.py); every rule ported lands with corpus cases in
phase6_where; unsupported expressions raise clean not-supported errors.
