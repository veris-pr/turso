# READING.md — the levelling-up plan

A reading roadmap from full-stack developer to systems developer who can
contribute to Turso — in the spirit of
[PingCAP's talent-plan](https://github.com/pingcap/talent-plan/blob/master/courses/rust/docs/lesson-plan.md):
each level has a goal, an anchor resource, supporting material, and a
checkpoint. Levels are **paced against the build phases in
[PLAN.md](PLAN.md)** — you read a thing when you are about to need it, and the
module `TOREAD.md` files select the exact subset per module.

## How to use this plan

- **Build-first, read-just-ahead.** Don't front-load months of reading; read
  the level (or the slice a `TOREAD.md` names) right before the phase that
  needs it. Reading sticks when the code makes it concrete.
- **Anchor + support.** Per level: one anchor you actually finish, support
  you dip into, blogs/talks as dessert.
- **Checkpoints are honest.** Each level ends with "you can now…" — if you
  can't, the level isn't done, no matter how many pages went by.
- **Two parallel tracks** run alongside everything: Rust (Level R) and the
  Turso repo itself (Level T).

## The map

| Level | Theme | Anchor | Paced with phases |
|---|---|---|---|
| R | Rust, continuously | The Rust Book → Rust for Rustaceans | parallel, always |
| 1 | The machine | CS:APP + CMU 15-213 | 0–3 (background) |
| 2 | The operating system | OSTEP + MIT 6.1810 | 1–2, persistence parts before 7–8 |
| 3 | Database fundamentals | CMU 15-445 + *Database Internals* | 1–6 |
| 4 | Storage engines deep | *Modern B-Tree Techniques* + SQLite internals docs | 7–8 |
| 5 | Transactions, recovery, MVCC | 15-445 txn lectures + 15-721 selections | 8, 11 |
| 6 | The craft: how DB people test & debug | SQLite "How It's Tested" + DST talks | 0, then always |
| T | Turso itself | repo `docs/agent-guides/` + blog + source | every phase |

---

## Level R — Rust (parallel track)

**Goal:** read `core/` fluently; eventually write it. pyturso is the concept
vehicle; contribution happens in Rust.

- **Anchor:** [The Rust Programming Language](https://doc.rust-lang.org/book/)
  (free) — cover to cover, with [Rustlings](https://github.com/rust-lang/rustlings)
  as finger exercises. Then **Rust for Rustaceans** (Jon Gjengset) — the
  intermediate book, read slowly across the whole project.
- **Video:** Jon Gjengset's
  [Crust of Rust](https://www.youtube.com/playlist?list=PLqbS7AVVErFiWDOAVrPt7aYmnuuOLYvOa)
  series — lifetimes, smart pointers, iterators, async; watch an episode when
  the corresponding concept blocks you in `core/`.
- **Practice:** [PingCAP talent-plan](https://github.com/pingcap/talent-plan)
  Practical Networked Applications course (builds a KV store in Rust — a
  miniature of this whole project, in the target language);
  [Too Many Linked Lists](https://rust-unofficial.github.io/too-many-lists/)
  for ownership intuition.
- **Habit that matters most:** every time a `TOREAD.md` sends you to a Rust
  file, read it for real — the per-module reading *is* the Rust course.

**Checkpoint:** you can read `core/storage/pager.rs` top to bottom and
explain each `IOResult` return; you can write a small CLI tool in Rust
without fighting the borrow checker for a day.

## Level 1 — The machine

**Goal:** know what memory, caches, and syscalls cost, and what the compiler
and CPU do with your code — the floor every systems argument stands on.

- **Anchor:** **Computer Systems: A Programmer's Perspective** (CS:APP,
  Bryant & O'Hallaron, 3rd ed) — chapters 1–6 and 9 minimum (representation,
  machine code, memory hierarchy, virtual memory). Skip the y86 depths.
- **Video:** CMU **15-213** lecture recordings (the course the book was
  written for — search "15-213 CMU lectures"; recordings are public).
- **Support:** Ulrich Drepper, *What Every Programmer Should Know About
  Memory* (free PDF) — §3–4 on caches; skim the rest.
- **Gentler alternative** if CS:APP stalls: *Nand2Tetris* part 1 (Coursera)
  to build the mental model bottom-up, then return to CS:APP ch. 5–6, 9.

**Checkpoint:** you can explain why sequential scans of a page beat pointer
chasing, what a TLB miss is, and why a 4 KiB page is the unit of everything
in this project.

## Level 2 — The operating system

**Goal:** files, syscalls, buffering, and crash behavior — the ground truth
under the pager and WAL.

- **Anchor:** **OSTEP** — *Operating Systems: Three Easy Pieces* (Remzi &
  Andrea Arpaci-Dusseau, free at
  [pages.cs.wisc.edu/~remzi/OSTEP](https://pages.cs.wisc.edu/~remzi/OSTEP/)).
  Virtualization + concurrency parts at normal pace; the **persistence
  chapters (I/O devices → hard disks → files & directories → FFS → crash
  consistency → journaling → LFS) are mandatory and re-read before Phases
  7–8** — they are the closest thing to a textbook for this project's hardest
  parts.
- **Video:** MIT **6.1810** (formerly 6.S081) Operating System Engineering —
  public lectures + xv6 labs. Do at least the file-system lectures; the xv6
  FS code is a beautifully small journaling FS to read.
- **Reference:** *The Linux Programming Interface* (Kerrisk) — not read, but
  consulted: ch. on file I/O, `fsync`/`fdatasync`, mmap.
- **Blogs:** Dan Luu, ["Files are hard"](https://danluu.com/file-consistency/)
  — read before Phase 8, then read the paper it summarizes: *All File
  Systems Are Not Created Equal* (OSDI '14).

**Checkpoint:** you can explain what `fsync` does and doesn't guarantee, what
a torn write is, and how a journal turns multi-block updates atomic — before
you build the WAL, not after.

## Level 3 — Database fundamentals

**Goal:** the standard architecture of a SQL engine, so Turso's shape reads
as "of course" rather than mystery.

- **Anchor course:** CMU **15-445/645 Intro to Database Systems** (Andy
  Pavlo; full lectures on YouTube, notes/slides public). Watch paced:
  storage + buffer pool lectures with Phase 1; B+-tree lectures with
  Phases 1/7; sorting/aggregation with Phase 10; query execution + planning
  with Phases 5/9; concurrency + recovery with Phases 8/11.
- **Anchor book:** **Database Internals** (Alex Petrov) — Part I (storage
  engines: B-trees, file formats, WAL) maps almost 1:1 onto this project.
  Part II (distributed) is optional dessert.
- **SQLite's own docs** (canonical for this project, all on sqlite.org):
  [Architecture](https://sqlite.org/arch.html) ·
  [File Format](https://sqlite.org/fileformat2.html) ·
  [The VDBE](https://sqlite.org/opcode.html) ·
  [Atomic Commit](https://sqlite.org/atomiccommit.html) ·
  [WAL](https://sqlite.org/wal.html) ·
  [Query Optimizer Overview](https://sqlite.org/optoverview.html) ·
  [Query Planner: Next-Gen](https://sqlite.org/queryplanner-ng.html).
- **Papers:** *Architecture of a Database System* (Hellerstein, Stonebraker,
  Hamilton, 2007) — the survey; *SQLite: Past, Present, and Future*
  (VLDB 2022) — SQLite's own story, directly relevant to why Turso exists.
- **Practice parallels** (optional but excellent): cstack's
  [db_tutorial](https://cstack.github.io/db_tutorial/) (SQLite-from-scratch
  in C — a preview of your Phases 1/7 in miniature); CMU's BusTub projects
  if you want graded-style exercises.

**Checkpoint:** you can draw the whole pipeline (parse → plan → optimize →
execute → storage) from memory, and for any pyturso module name its SQLite
and 15-445 counterpart.

## Level 4 — Storage engines deep

**Goal:** enough B-tree and file-format depth to survive Phase 7 (balancing)
and Phase 8 (WAL) with understanding rather than trial-and-error.

- **Anchor:** Goetz Graefe, *Modern B-Tree Techniques* (Foundations & Trends,
  2011; free PDF via author/university copies) — ch. 1–3 before Phase 7;
  the rest is reference.
- **Re-reads, now for real:** SQLite File Format doc (every word this time),
  OSTEP crash-consistency + journaling chapters, repo
  `docs/agent-guides/storage-format.md` and `transaction-correctness.md`.
- **Support:** *Database Internals* ch. on B-tree implementation details
  (splits, merges, rebalancing, sibling pointers); *Use The Index, Luke*
  (Markus Winand, free online) for index intuition that Phase 9 will spend.

**Checkpoint:** you can hand-decode a B-tree page from a hexdump, and
whiteboard a leaf split including what the parent gets.

## Level 5 — Transactions, recovery, MVCC

**Goal:** isolation and durability as precise mechanisms, for Phases 8 & 11.

- **Anchor:** 15-445 lectures on concurrency control, two-phase locking,
  MVCC, and recovery (ARIES lecture) — then CMU **15-721 Advanced Database
  Systems** (Pavlo, YouTube) selected lectures: MVCC design decisions,
  latching, index concurrency.
- **Papers:** *An Empirical Evaluation of In-Memory Multi-Version Concurrency
  Control* (Wu et al., VLDB 2017) — the MVCC design-space map; ARIES (Mohan
  et al.) is optional/heavy — the 15-445 recovery lecture + OSTEP journaling
  covers what Phase 8 needs.
- **Support:** Jepsen's [consistency models map](https://jepsen.io/consistency)
  to place "snapshot isolation" precisely; repo `docs/agent-guides/mvcc.md`
  as the Turso-specific spec.

**Checkpoint:** you can state what anomalies snapshot isolation permits
(write skew) and how first-committer-wins works — and show both in a pyturso
Phase 11 scenario script.

## Level 6 — The craft: testing & debugging like a DB engineer

**Goal:** absorb the testing culture Turso practices — it is as much the
"systems developer" skill as any algorithm.

- **Anchor:** [How SQLite Is Tested](https://sqlite.org/testing.html) — read
  at Phase 0, re-read at Phase 7; it reframes what "serious" means.
- **Talks:** Will Wilson, *Testing Distributed Systems with Deterministic
  Simulation* (FoundationDB, Strange Loop 2014) — the idea behind Turso's
  simulator and this project's StepDriver; TigerBeetle's simulation-testing
  talks/posts for a modern take.
- **Repo:** `docs/agent-guides/testing.md` and `debugging.md`;
  `testing/simulator/` source once Phase 8's crash injection makes it
  meaningful.

**Checkpoint:** given a divergence, your reflex is: minimize → pin with a
corpus case → read the Rust → fix → keep the case. (This is
[HOWTO.md](HOWTO.md)'s divergence protocol — it should feel natural, not
procedural.)

## Level T — Turso itself (parallel track)

- **Repo guides** (`docs/agent-guides/`): each module `TOREAD.md` schedules
  them; by Phase 8 you should have read all eight.
- **Blog & story:** the Turso blog's posts on rewriting SQLite in Rust
  (the Limbo announcement and follow-ups) and their deterministic-simulation
  posts; the team's *In Search of a Faster SQLite* research paper for the
  async-I/O rationale behind `IOResult`.
- **Community:** the repo's issues/discussions and Discord; read merged PRs
  touching files you just ported — real diffs in code you now understand are
  the best advanced reading in existence.
- **Contribution on-ramp** (start ~Phase 5, don't wait for Phase 12):
  `.sqltest` conformance additions → `bindings/python` issues → small
  `core/` fixes in modules you've ported. Follow `CONTRIBUTING.md` and
  `docs/agent-guides/pr-workflow.md`.

---

## Citation index

Every resource in this plan, one line each — enough to find the exact
edition/playlist yourself. (T) textbook · (C) university course · (P) paper ·
(D) primary docs · (B) blog/talk · (X) exercises.

**Rust**
- Klabnik & Nichols — *The Rust Programming Language* (T, free official)
- Jon Gjengset — *Rust for Rustaceans* (T, No Starch Press)
- Jon Gjengset — *Crust of Rust* (B, YouTube series)
- rust-lang — *Rustlings* (X)
- PingCAP — *talent-plan*, Practical Networked Applications in Rust (X)
- Aria Beingessner — *Learning Rust With Entirely Too Many Linked Lists* (T, free)

**Machine**
- Bryant & O'Hallaron — *Computer Systems: A Programmer's Perspective*, 3rd ed (T) + CMU **15-213** (C)
- Ulrich Drepper — *What Every Programmer Should Know About Memory* (P)
- Nisan & Schocken — *The Elements of Computing Systems* / Nand2Tetris (T/C, optional)

**Operating systems**
- Remzi & Andrea Arpaci-Dusseau — *Operating Systems: Three Easy Pieces* (OSTEP) (T, free)
- MIT **6.1810** (ex-6.S081), Operating System Engineering — xv6 (C)
- Michael Kerrisk — *The Linux Programming Interface* (T, reference)
- Dan Luu — *Files are hard* (B)
- Pillai et al. — *All File Systems Are Not Created Equal* (P, OSDI 2014)

**Databases**
- Andy Pavlo — CMU **15-445/645** Intro to Database Systems (C); CMU **15-721** Advanced Database Systems (C)
- Alex Petrov — *Database Internals* (T, O'Reilly)
- sqlite.org — Architecture · File Format · Datatypes · VDBE opcodes · Atomic Commit · WAL · Query Optimizer Overview · Next-Gen Query Planner · CLI · How SQLite Is Tested (D)
- Hellerstein, Stonebraker & Hamilton — *Architecture of a Database System* (P, 2007)
- Gaffney, Hipp et al. — *SQLite: Past, Present, and Future* (P, VLDB 2022)
- cstack (Connor Stack) — *db_tutorial: Let's Build a Simple Database* (X, free)
- Markus Winand — *Use The Index, Luke* / *SQL Performance Explained* (T, free online)
- Goetz Graefe — *Modern B-Tree Techniques* (P/monograph, Foundations & Trends 2011)
- Wu, Arulraj, Lin, Xian & Pavlo — *An Empirical Evaluation of In-Memory Multi-Version Concurrency Control* (P, VLDB 2017)
- Mohan et al. — *ARIES: A Transaction Recovery Method…* (P, TODS 1992, optional)
- Kyle Kingsbury (aphyr/Jepsen) — consistency models map (B)
- Bob Nystrom — *Crafting Interpreters* (T, free online — parser module only)

**Craft**
- Will Wilson (FoundationDB) — *Testing Distributed Systems with Deterministic Simulation* (B, Strange Loop 2014)
- TigerBeetle (Joran Dirk Greef) — simulation-testing talks/posts (B)

**Turso**
- Turso blog — Limbo announcement + deterministic-simulation posts (B)
- Pekka Enberg et al. — *In Search of a Faster SQLite* (P, Turso team research paper)
- This repo — `docs/agent-guides/` (D), `CONTRIBUTING.md`, merged PRs (D)

## Where TODO / TOREAD fit

Every module folder carries:

- **`TODO.md`** — the precise, checkbox-level build list for that module,
  phase by phase (a refinement of its HOWTO's work order).
- **`TOREAD.md`** — the module's curriculum: the exact slices of this plan,
  the repo guides, the Rust files, and the *earlier pyturso Diátaxis docs*
  to (re)read before and during each stage. Reading an item off a TOREAD
  list is project work, same as code.
