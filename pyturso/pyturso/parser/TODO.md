# TODO — parser (Phase 3, then grows per phase)

Work order rationale: [HOWTO.md](HOWTO.md).

- [x] `token.py`: token-kind enum; keyword table copied from
      `sqlite/parser/src/token.rs` incl. the may-be-identifier set.
- [x] `lexer.py`: whitespace + `--`/`/* */` comments → identifiers + all
      four quoting forms → numeric literals (int/float/hex/exponent) →
      string and `x'..'` blob literals → operators/punct → parameters
      (`?`, `?N`, `:name`). Positions on every token.
- [x] Lexer unit tests incl. rejection cases (unterminated string, bad hex).
- [x] `ast/expr.py`, `ast/stmt.py`, `ast/ddl.py`: frozen dataclasses for the
      Phase 3 subset only (see ast/HOWTO.md rules).
- [x] `parser.py` expressions: precedence-climbing with the table from the
      Rust; snapshot tests per precedence level; COLLATE and unary edges.
- [x] `parser.py` SELECT core: result columns (+ `*`, aliases), FROM (single
      table + alias), WHERE, ORDER BY (ASC/DESC), LIMIT/OFFSET.
- [x] `parser.py` DML: INSERT (VALUES lists), UPDATE, DELETE.
- [x] `parser.py` DDL: CREATE TABLE (column defs, INTEGER PRIMARY KEY forms,
      basic constraints parsed-and-kept), CREATE INDEX — needed by Phase 4.
- [x] BEGIN/COMMIT/ROLLBACK (landing with Phase 8).
- [x] `errors.py`: `ParseError(position, token)`; rejection tests assert
      error class parity with sqlite3 via the corpus once Phase 5 runs.
- [x] `docs/parser/reference/grammar.md` scope ledger — a row per construct,
      updated every commit that touches the grammar.

Exit: every corpus statement parses to a stable snapshot; invalid SQL is
rejected with the right class; grammar ledger has no silent gaps.
