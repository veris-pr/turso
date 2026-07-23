# HOWTO — tests/unit

One test file per engine module, named after it (`test_storage_ondisk.py`,
`test_vdbe_builder.py`, ...). Plain pytest, no plugins.

Recipes:
- **Binary edges**: drive encode/decode with hand-built byte strings; varint
  boundaries, serial-type widths, header packing. Cite the format reference
  doc in a comment so the expected bytes are checkable.
- **Generator state machines**: use `io.driver`'s step-controlled driver to
  advance an operation yield-by-yield and assert state between steps — this
  is how crash points and re-entrancy are tested without threads.
- **Property-style**: fixed-seed random operation sequences (seed in the test
  name or a constant) asserting invariants after every step; used heavily for
  B-tree insert/delete in Phase 7.
- **Corrupt inputs**: fixture bytes that must raise `Corrupt` — never assert
  on garbage output.
- **Snapshots**: AST/EXPLAIN snapshots inline when small; regenerate via an
  explicit flag and review the diff, never auto-accept.
