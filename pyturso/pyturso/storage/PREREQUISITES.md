# PREREQUISITES — storage

Gate before [TODO.md](TODO.md), split by phase block. Cites resolve in
[READING.md](../../READING.md#citation-index).

## Before Phase 1 (read path)

- [ ] Why databases use fixed-size pages (I/O granularity, addressing,
      caching) — not just "they do". → CMU 15-445 storage lectures (C);
      OSTEP hard-disk chapter.
- [ ] B-trees conceptually: why ordered trees of wide nodes beat binary
      trees on disk; interior vs leaf; what a search does. → 15-445 B+-tree
      lecture (C); *Database Internals* Part I (T).
- [ ] Variable-length integer encodings: why they exist, how a
      continuation-bit scheme works. → SQLite File Format doc §varint (D).
- [ ] Hexdump literacy (project-wide gate, but this is where it bites):
      given `xxd` output and the format doc, find a field by offset.
      → CS:APP ch. 2; practice on a real `.db` file.
- [ ] The project's io convention (generators) — built and understood, or
      this module can't start. → [../io/](../io/PREREQUISITES.md) + its
      keystone doc.

## Before Phase 7 (write path)

- [ ] B-tree mutation: insert into a full node, split, propagation to
      parent, root split (tree grows *up*); delete/underflow at concept
      level. → Graefe *Modern B-Tree Techniques* chs. 1–2 (P); *Database
      Internals* B-tree implementation chapters.
- [ ] Free-space management concepts: freelists, fragmentation inside a
      page. → SQLite File Format doc §freelist (D).

## Before Phase 8 (WAL)

- [ ] Crash consistency: torn writes, write reordering, what `fsync`
      actually promises, and the journaling idea (write intent → make
      durable → apply). → OSTEP crash-consistency + journaling chapters
      (T) — mandatory, not skimmable.
- [ ] Rollback journal vs write-ahead log: the trade, at whiteboard depth.
      → SQLite *Atomic Commit* doc (D), then *WAL* doc (D).
- [ ] Checksums for torn-frame detection: why recovery can trust a frame.
      → SQLite WAL doc §checksums.

Phase 7's balance code is the project's wall — walking into it without the
Graefe chapters is how weeks get lost.
