# TOREAD — parser

Levels refer to [../../READING.md](../../READING.md).

## Before starting

- [ ] Crafting Interpreters (Bob Nystrom, free online), ch. 4–6 — scanning,
      representing code, and *parsing expressions by precedence climbing*:
      the exact techniques this module uses, taught better than anywhere
      else. (One-off addition to the READING plan, parser-specific.)
- [ ] SQLite [Language docs](https://sqlite.org/lang.html) syntax diagrams —
      the grammar you are subsetting; keep open while porting.
- [ ] READING L3: 15-445 lecture's brief treatment of parsing — mostly to
      notice how *little* time DB courses spend here (parsing is the easy
      third of a database; don't gold-plate it).

## Rust source (per-construct, never linearly)

- [ ] `sqlite/parser/src/token.rs` — keyword table (copy, don't retype from
      memory).
- [ ] `sqlite/parser/src/lexer.rs` — literal edge cases live here.
- [ ] `sqlite/parser/src/ast.rs` + `ast/` — node shapes to mirror.
- [ ] `sqlite/parser/src/parser.rs` — open the function for the construct
      you are porting today; 11k LOC is a reference manual, not a novel.
- [ ] `sqlite/parser/src/error.rs` — error reporting shape.

## While building

- [ ] Python `re`-free discipline: the lexer is hand-rolled like the Rust
      one — no regex; if tempted, re-read the Rust lexer's approach.

## Docs you will write

`grammar.md` (ledger) · `ast-nodes.md` · `tokens-and-literals.md` ·
`operator-precedence.md` · `why-recursive-descent.md` explanation ·
`from-sql-text-to-ast.md` tutorial. Status: `docs/parser/README.md`.
