# PREREQUISITES — cli

Gate before [TODO.md](TODO.md). Light — by Phase 12 the engine knowledge is
in place; this is interface craft.

- [ ] Terminal I/O basics: stdin/stdout/stderr separation, line buffering,
      why prompts go where they go; Python `readline` module capabilities.
      → Python docs.
- [ ] REPL loop anatomy: read → detect complete statement → eval → print →
      handle interrupt without dying. Study one: the sqlite3 shell itself.
      → SQLite CLI doc (D).
- [ ] Statement termination vs dot-commands: two grammars sharing a prompt;
      how the real shells disambiguate.
- [ ] Exit codes and quiet modes for scriptability (the session-diff
      harness consumes them).
- [ ] Working prereq green: the public API frozen enough that the CLI
      never needs engine internals (rule zero of [HOWTO.md](HOWTO.md)).
