# PREREQUISITES — tools

Gate before [TODO.md](TODO.md). Tools ride on their owning module's
knowledge (see [TOREAD.md](TOREAD.md)); the gate here is craft basics.

- [ ] argparse: subcommand-less single-purpose CLIs with flags. → Python
      docs.
- [ ] subprocess: run, capture, timeout, exit codes (explain_diff/dbcompare
      drive tursodb this way). → Python docs.
- [ ] Composable output discipline: why stable line-oriented stdout matters
      (`diff`/`grep` are the downstream consumers), diagnostics to stderr.
- [ ] Hexdump literacy (again — pagehex *produces* one; you must be able
      to sanity-check it by hand against `xxd`). → CS:APP ch. 2.
- [ ] Per tool, the owning module's PREREQUISITES gate applies at build
      time: pagehex/dbdump → [storage's](../pyturso/storage/PREREQUISITES.md)
      Phase 1 gate; walinfo → its Phase 8 gate; explain_diff →
      [vdbe's](../pyturso/vdbe/PREREQUISITES.md) gate.
