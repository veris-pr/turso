# HOWTO — parser/ast

Ports `sqlite/parser/src/ast.rs` + `ast/`. The AST is the vocabulary shared
between parser and translate — get the shapes right and both sides stay
mechanical.

The work, per construct being added to the grammar:
1. Read the matching Rust enum/struct in `ast.rs` first; mirror its name and
   field names in a **frozen dataclass** (`expr.py`, `stmt.py`, or `ddl.py`).
2. No behavior on nodes: no eval, no emission, no name resolution — those
   belong to `translate/`. `__repr__` (dataclass default) must stay stable;
   snapshot tests depend on it.
3. Every node lands in the AST-node catalog
   (`docs/parser/reference/ast-nodes.md`) in the same commit, with its Rust
   counterpart named.

Done when: the construct parses to a snapshot-tested node and the catalog row
exists.
