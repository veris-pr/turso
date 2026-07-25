# TODO — cli (Phase 12)

Work order rationale: [HOWTO.md](HOWTO.md).

- [x] `__main__.py`: arg surface — `python -m cli [db] ['SQL']`;
      non-interactive mode first (M6 depends on it), `-q` quiet flag.
- [x] `repl.py`: readline loop; continuation prompt until `;`; dot-command
      dispatch; Ctrl-C clears buffer, Ctrl-D exits; errors printed without
      killing the session.
- [x] `output.py`: `list` mode (pipe-separated, matches harness canonical
      form) → `table` mode; NULL rendering decided + documented.
- [x] `dot_commands.py`, in order: `.quit` · `.open` · `.tables` ·
      `.schema [table]` · `.mode` · `.read file` · `.explain on|off`.
- [x] Parity table rows (docs/cli/reference/dot-commands.md) (`docs/cli/reference/dot-commands.md`) with each
      command as it lands.
- [x] Scripted-session differ (cli/session_differ.py): run a session file through `python -m cli`
      and `tursodb -q`, diff — wired as a test.
- [x] Mine testing/cli_tests/ (session differ implemented in cli/session_differ.py) (repo root) for session-script ideas; port
      the applicable ones.
- [x] **Gate:** M6 (session differ tested in test_final3.py)
