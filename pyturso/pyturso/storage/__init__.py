"""Storage engine: SQLite file format, pager, page cache, B-tree, WAL.

Ports core/storage/. Read path lands in Phase 1, writes in Phase 7, WAL in 8.
"""
