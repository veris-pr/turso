# cli — pyturso REPL

**Ports:** `cli/` at the repo root (the `tursodb` binary): REPL loop,
statement termination, output modes, dot-commands
**Phase:** 12 (last — it is the victory lap that exercises everything)

## What this module is

An interactive shell over the pyturso engine, close enough to `tursodb` that a
scripted session can be diffed between the two. It is deliberately thin: any
logic beyond line handling and formatting belongs in the engine — same layering
rule the Rust CLI follows.

## Planned scope

| Piece | Mirrors | Notes |
|-------|---------|-------|
| REPL loop | `cli/` main loop | `readline` stdlib; multi-line statements, `;` termination |
| Output modes | tursodb `.mode` | `list` (default) and `table` first; others per parity table |
| Dot-commands | tursodb dot-commands | `.open`, `.schema`, `.tables`, `.mode`, `.read`, `.explain`, `.quit`; parity table in docs tracks the rest |
| `--trace` | debugging workflow | per-opcode VM trace — pyturso-specific, kept because it serves the understanding goal |
| Non-interactive | `tursodb -q db 'SQL'` | required by the differential harness for M6 session diffing |

Not ported: MCP server, sync/cloud commands, `mvcc_repl.rs` (its *scenarios*
are ported in [../pyturso/mvcc/](../pyturso/mvcc/README.md) instead).

## Exit criterion (from PLAN.md)

A scripted session file run through `cli` and through `tursodb -q` produces
diffable-equal output for the supported feature set (M6).

## Docs

Diátaxis tree: [../docs/cli/README.md](../docs/cli/README.md)
