# docs/storage — Doc index

Module: [pyturso/storage/](../../pyturso/storage/README.md) ·
Rust: `core/storage/` · Repo guides: `docs/agent-guides/storage-format.md`,
`docs/agent-guides/transaction-correctness.md`

## Planned documents

### tutorials/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `read-a-db-file-byte-by-byte.md` | 1 | planned | from `xxd` on a fresh .db to dumping rows with your own code |
| `insert-a-row-watch-the-pages.md` | 7 | planned | one INSERT traced through pager, cell, and page images |
| `follow-one-commit-to-disk.md` | 8 | planned | statement → WAL frames → checkpoint, with walinfo output |

### how-to/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `inspect-a-page-with-pagehex.md` | 1 | planned | read the annotated hexdump; find a cell by hand |
| `verify-a-written-file.md` | 7 | planned | integrity_check + dbhash workflow for pyturso-written files |
| `simulate-a-crash-and-recover.md` | 8 | planned | drive the injection points; interpret the recovery matrix |

### reference/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `file-header.md` | 1 | planned | all 100 bytes, offsets, values pyturso accepts |
| `page-and-cell-layout.md` | 1 | planned | 4 page types, cell formats, pointer arrays, overflow |
| `varints-and-serial-types.md` | 1 | planned | encodings with worked byte examples |
| `freelist.md` | 7 | planned | trunk/leaf pages, allocation order |
| `wal-format.md` | 8 | planned | header, frame, salts, checksums, commit marker |

### explanation/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `why-pages-and-btrees.md` | 1 | planned | from "files are byte arrays" to ordered trees of fixed pages |
| `the-pager-as-page-authority.md` | 7 | planned | cache/WAL/file resolution order; dirty pages; who owns what |
| `btree-balancing-in-pictures.md` | 7 | planned | **mandatory phase deliverable**; split/merge drawn step by step |
| `why-wal.md` | 8 | planned | durability/concurrency trade vs rollback journal; checkpoint spectrum |

Every explanation doc ends with an "In Turso" section
([../README.md](../README.md) house rules).
