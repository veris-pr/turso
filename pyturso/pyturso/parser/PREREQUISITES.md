# PREREQUISITES — parser

Gate before [TODO.md](TODO.md). Cites resolve in
[READING.md](../../READING.md#citation-index).

- [ ] Tokenization vs parsing: what each stage owns and why they're
      separate. → *Crafting Interpreters* ch. 4 (T, free).
- [ ] Grammars informally: productions, terminals/non-terminals — enough
      to read SQLite's syntax diagrams as a grammar. → *Crafting
      Interpreters* ch. 5.
- [ ] Recursive descent: one function per rule, lookahead, how it maps to
      the call stack. → *Crafting Interpreters* ch. 6.
- [ ] Operator precedence & associativity, and the precedence-climbing
      technique for expressions — the single most load-bearing technique
      in this module. → *Crafting Interpreters* ch. 6 (and its "parsing
      expressions" discussion).
- [ ] ASTs: trees of dumb data nodes; why behavior stays out of them.
      → *Crafting Interpreters* ch. 5; this repo's `parser/ast/HOWTO.md`.
- [ ] SQL's lexical quirks, stated from memory: four identifier-quoting
      forms, `'x'` is a string not an identifier, keywords that can be
      identifiers, blob literals. → SQLite Language docs (D).
- [ ] Error reporting: why tokens carry positions, error class vs message.
