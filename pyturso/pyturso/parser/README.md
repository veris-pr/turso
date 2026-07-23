# pyturso.parser — Tokenizer, lexer, AST, parser

**Ports:** `sqlite/parser/src/` — `token.rs`, `lexer.rs`, `ast.rs` + `ast/`,
`parser.rs`, `error.rs`
**Phase:** 3 (grammar coverage then grows with every SQL-surface phase)

## What this module is

SQL text → abstract syntax tree, by hand-written recursive descent, exactly as
Turso does it (Turso replaced the original lemon/yacc-generated parser with an
11k-LOC recursive-descent one — porting it teaches you how production parsers
are actually structured).

```
"SELECT a FROM t WHERE b > 1"
   │ tokenizer/lexer (token.py, lexer.py)
   ▼
[KW_SELECT, Id("a"), KW_FROM, Id("t"), KW_WHERE, Id("b"), GT, Integer(1)]
   │ parser.py (one function per grammar construct)
   ▼
Select(columns=[Expr.Id("a")], from_=Table("t"),
       where=Binary(GT, Id("b"), Literal(1)))
```

- **`token.py`** (`token.rs`) — token kinds, keyword table (SQL keywords are
  context-sensitive — `ORDER` is a keyword only in some positions),
  identifier quoting rules (`"x"`, `[x]`, `` `x` ``), literals.
- **`lexer.py`** (`lexer.rs`) — text → token stream: string/blob literals,
  numeric literal forms, comments, error positions.
- **`ast.py` / `ast/`** — frozen dataclasses for every node; the vocabulary
  shared with `translate/`. Node names mirror the Rust enums so cross-reading
  the translator is mechanical.
- **`parser.py`** (`parser.rs`) — recursive descent with correct expression
  precedence (via precedence climbing), per-statement entry points. Ported
  construct-by-construct as phases demand, tracked in the grammar reference
  doc — never "the whole file at once".

## Parity notes

- The grammar reference doc is the scope ledger: each construct is
  supported / planned(phase N) / out-of-scope. The parser must *reject*
  what it does not support with a clean error — silent misparse is the one
  unforgivable failure mode.
- Error *class* parity with sqlite3 (`sqlite3.OperationalError: near "..."`)
  is asserted by the differential corpus; exact message text is not.
- AST snapshot tests (parse → repr → compare) are the fast unit-level check;
  behavioral verification comes from the corpus once Phase 5 executes queries.

## Docs

Diátaxis tree: [../../docs/parser/README.md](../../docs/parser/README.md)
