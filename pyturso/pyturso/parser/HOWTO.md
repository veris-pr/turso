# HOWTO — parser

What the module is: [README.md](README.md). Phase 3 builds the core; the
grammar then grows with every SQL-surface phase. The Rust parser is 11k LOC —
**never read it linearly**; read per-construct as you port that construct.

## Work order

1. **`token.py`** — token kinds + the keyword table from
   `sqlite/parser/src/token.rs`. Decide keyword lookup (dict) and note which
   keywords are context-sensitive (usable as identifiers) — copy that set
   from the Rust, don't guess it.
2. **`lexer.py`** — order: whitespace/comments → identifiers + quoting forms
   (`"x"`, `[x]`, `` `x` ``, and `'x'` is a *string*, not an identifier) →
   numeric literals (int, float, hex, exponent edge forms) → string/blob
   literals (`x'ab'`) → operators/punctuation → parameters (`?`, `?N`,
   `:name`). Every token carries a position for error messages.
3. **`ast/`** — nodes for the current target subset only
   (see [ast/HOWTO.md](ast/HOWTO.md)).
4. **`parser.py`** — order: expressions first via precedence climbing (get
   the precedence table from the Rust and pin it with snapshot tests), then
   `SELECT` core (columns, FROM, WHERE, ORDER BY, LIMIT), then
   INSERT/UPDATE/DELETE, then CREATE TABLE/INDEX (needed by Phase 4 to parse
   `sqlite_schema.sql`), then BEGIN/COMMIT/ROLLBACK (Phase 8).
5. **`errors.py`** — one `ParseError` with position; the harness maps it to
   the same class sqlite3 raises (`OperationalError`-equivalent).

## Per-construct loop

read the Rust path for the construct → port → AST snapshot tests (valid
inputs) + rejection tests (invalid inputs, right error class) → add the row
to `docs/parser/reference/grammar.md` (the scope ledger) → commit.

## Rules

- The parser **rejects** everything the ledger doesn't mark supported —
  a clean not-supported error. Silent misparse is the one unforgivable
  failure mode here.
- No semantic checks (unknown table, wrong arity): those belong to
  `translate/planner.py`. The parser only knows grammar.

## Verify

Snapshot tests per construct; once Phase 5 executes queries, the corpus
exercises the parser end-to-end and precedence bugs surface as wrong rows —
pin any such bug with both a snapshot test and a corpus case.
