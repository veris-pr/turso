# HOWTO — cli

What the module is: [README.md](README.md). Phase 12 — the victory lap.
Rule zero: the CLI contains no engine logic; if a feature needs engine
support, add it to the `pyturso` package first.

## Work order

1. **`__main__.py`** — argument surface mirroring what the differential
   workflow needs first: `python -m cli <db> '<SQL>'` non-interactive mode
   (M6 depends on it), then interactive default.
2. **`repl.py`** — `readline`-based loop: prompt/continuation prompt,
   statement accumulation until `;`, dot-command detection (line starts with
   `.` outside a statement), Ctrl-C clears the buffer, Ctrl-D exits. Read
   the tursodb REPL loop in `cli/` (repo root) for the behaviors worth
   mirroring; skip its bells until the parity table demands them.
3. **`output.py`** — `list` mode first (pipe-separated — also what the
   harness normalizes to), then `table`. Exact spacing rules go in
   `docs/cli/reference/output-modes.md` as they are decided.
4. **`dot_commands.py`** — in order of usefulness: `.quit`, `.open`,
   `.tables`, `.schema`, `.mode`, `.read`, `.explain`. Each lands with its
   row in the dot-command parity table (scope ledger).

## Verify

- Scripted-session diffing: a `.txt` session file fed to both
  `python -m cli` and `tursodb -q`, outputs diffed
  (`docs/cli/how-to/diff-a-session-against-tursodb.md`). That workflow *is*
  the M6 exit criterion.
- `testing/cli_tests/` (repo root) shows the kind of CLI behaviors turso
  itself pins — mine it for session-script ideas.
