# PREREQUISITES — mvcc

Gate before [TODO.md](TODO.md). This phase is deliberately reading-heavy;
the gate is correspondingly the largest. Cites resolve in
[READING.md](../../READING.md#citation-index).

- [ ] ACID isolation levels and their anomalies (dirty read, non-repeatable
      read, phantom, write skew) — definitions from memory, with an example
      schedule each. → CMU 15-445 concurrency lectures (C).
- [ ] Snapshot isolation precisely: what it guarantees, and that it is
      *not* serializable — write skew is the wedge; be able to construct a
      write-skew schedule on paper. → Jepsen consistency-models map (B);
      15-445.
- [ ] MVCC core idea: versions instead of locks; readers never block
      writers; what a "snapshot" technically is (a visibility predicate
      over versions). → 15-721 MVCC lecture (C); Wu et al. VLDB 2017 (P).
- [ ] The design axes from the survey: version storage, ordering
      (newest-to-oldest vs oldest-to-newest), garbage collection — enough
      to place Turso's choices when reading `core/mvcc/`.
- [ ] First-committer-wins vs first-writer-wins conflict handling.
- [ ] Working prereqs green: Phases 7–8 complete (you cannot version what
      you cannot durably write); `io.StepDriver` fluency (the scheduler is
      built on it).
- [ ] Repo spec read: `docs/agent-guides/mvcc.md` incl. limitations list.
