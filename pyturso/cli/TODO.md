# TODO — cli (Phase 12)

Work order rationale: [HOWTO.md](HOWTO.md).

- [ ] `__main__.py`: arg surface — `python -m cli [db] ['SQL']`;
      non-interactive mode first (M6 depends on it), `-q` quiet flag.
- [ ] `repl.py`: readline loop; continuation prompt until `;`; dot-command
      dispatch; Ctrl-C clears buffer, Ctrl-D exits; errors printed without
      killing the session.
- [ ] `output.py`: `list` mode (pipe-separated, matches harness canonical
      form) → `table` mode; NULL rendering decided + documented.
- [ ] `dot_commands.py`, in order: `.quit` · `.open` · `.tables` ·
      `.schema [table]` · `.mode` · `.read file` · `.explain on|off`.
- [ ] Parity table rows (`docs/cli/reference/dot-commands.md`) with each
      command as it lands.
- [ ] Scripted-session differ: run a session file through `python -m cli`
      and `tursodb -q`, diff — wired as a test.
- [ ] Mine `testing/cli_tests/` (repo root) for session-script ideas; port
      the applicable ones.
- [ ] **Gate:** M6 — sample sessions diff clean for the supported set.
