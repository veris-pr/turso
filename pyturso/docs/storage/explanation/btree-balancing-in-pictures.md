# B-tree Balancing, in Pictures

**Status:** current · **Phase:** 7 (deliverable)

> If you can't draw it, you don't understand it. This doc explains B-tree
> page splitting and balancing with ASCII diagrams.

## The problem

When a leaf page is full and a new cell needs to be inserted, the page must
split. This is the fundamental operation that keeps B-trees balanced.

## Leaf page split

Before split (page is full):

```
Page 2 (leaf, 5 cells):
┌────────────────────────────┐
│ Header: type=13, count=5   │
│ Cell ptrs: [48, 44, 40, 36, 32] │
│ ...                        │
│ [cell5] [cell4] [cell3] [cell2] [cell1] │
│ ...                        │
└────────────────────────────┘
```

After split (cells redistributed across two pages):

```
Page 2 (leaf, 3 cells — left half):
┌────────────────────────────┐
│ Header: type=13, count=3   │
│ Cell ptrs: [48, 44, 40]    │
│ ...                        │
│ [cell3] [cell2] [cell1]    │
│ ...                        │
└────────────────────────────┘

Page 3 (leaf, 2 cells — right half):
┌────────────────────────────┐
│ Header: type=13, count=2   │
│ Cell ptrs: [48, 44]        │
│ ...                        │
│ [cell5] [cell4]            │
│ ...                        │
└────────────────────────────┘
```

## Interior page update

The parent interior page gets a new entry pointing to the new page:

```
Page 1 (interior, was: 1 entry + rightmost):
┌────────────────────────────────┐
│ Header: type=5, count=1        │
│ Rightmost ptr: 2               │
│ Cell: [child=2, key=cell3.rowid] │
└────────────────────────────────┘

After split (2 entries + rightmost):
┌────────────────────────────────┐
│ Header: type=5, count=2        │
│ Rightmost ptr: 3               │
│ Cell: [child=2, key=cell3.rowid] │
│ Cell: [child=3, key=cell4.rowid] │
└────────────────────────────────┘
```

## Root split (tree grows)

When the root page itself splits, a new root is created:

```
Before (root is a full leaf):
Page 1 (leaf, full)

After (new interior root + two leaf children):
Page 1 (interior root, count=1, rightmost=3)
  → child=2 (leaf, left half)
  → child=3 (leaf, right half)
```

The tree grows by one level. This is the only operation that increases the
tree's height.

## pyturso's simplified approach

pyturso's `btree_balance.py` implements the leaf split:
1. `needs_split(page_data, page_no, page_size, new_cell_size)` — checks if
   the page is too full.
2. `split_leaf_page(pager, page_no, page_data)` — splits the page in half,
   allocates a new page for the right half, writes both back.
3. `rebuild_leaf_page(cells, page_size, page_no)` — rebuilds a page from a
   list of cells (used by both split and the insert path).

The full Rust balancing algorithm is more sophisticated:
- It considers sibling pages for cell redistribution (not just splitting).
- It handles overflow cells (cells too large for a single page).
- It uses a multi-page balance pass that processes up to 3 sibling pages
  simultaneously.
- It handles underflow (when a page is too empty after a delete) by
  merging with a sibling or redistributing cells.

pyturso's simplified version is correct for the common case (small-to-medium
tables that fit within a few pages). The full algorithm is a future refinement.