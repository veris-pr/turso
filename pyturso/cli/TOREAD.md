# TOREAD — cli

Short list — by Phase 12 you have read almost everything; this is polish.

- [ ] SQLite [CLI doc](https://sqlite.org/cli.html) — the UX conventions
      tursodb inherits; skim for the commands in scope.
- [ ] Rust: `cli/` at repo root — REPL loop, output modes, dot-command
      dispatch; read for behaviors worth mirroring, resist porting bells.
- [ ] Python `readline` stdlib docs (history, completion hooks).
- [ ] `testing/cli_tests/` (repo root) — how turso pins CLI behavior; the
      session-diff test you build mirrors this.
- [ ] Prereq from your own docs: `docs/api/reference/public-api.md` — the
      CLI may only touch this surface (rule zero).

## Docs you will write

`dot-commands.md` parity ledger · `output-modes.md` ·
`a-guided-pyturso-session.md` tutorial · session-diff how-to ·
`a-thin-shell.md` explanation. Status: `docs/cli/README.md`.
