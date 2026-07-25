"""checkpoint — WAL checkpoint: frames → main file, WAL reset.

Ports: core/storage/wal.rs (checkpoint paths).
Phase: 8
Status: IMPLEMENTED (simplified: writes all committed WAL frames back to the
main database file, then resets the WAL).

Checkpointing moves modified pages from the WAL back to the main database
file. After a checkpoint, the WAL can be reset (truncated to just the header)
and the main file contains all committed data.

Phase 8 simplified:
  1. For each frame up to and including the last commit frame, write the
     page data back to the pager (main file).
  2. Flush the pager.
  3. Reset the WAL (clear frames, keep the header).

A full checkpoint also handles the checkpoint mode (PASSIVE/FULL/RESTART)
and concurrent readers — that's a later refinement.
"""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"

from pyturso.storage.pager import Pager
from pyturso.storage.wal import WAL

__all__ = ["checkpoint"]


def checkpoint(pager: Pager, wal: WAL) -> int:
    """Checkpoint the WAL: write committed frames back to the main file.

    Returns the number of frames checkpointed.
    """
    mx_frame = wal.mx_frame
    if mx_frame < 0:
        return 0  # nothing to checkpoint

    # Write each committed frame's page back to the pager.
    checkpointed = 0
    seen_pages: set[int] = set()
    # Iterate from the end so the latest version of each page is checkpointed.
    for i in range(mx_frame, -1, -1):
        frame = wal.frames[i]
        page_no = frame.page_number
        if page_no in seen_pages:
            continue  # already have the latest version
        seen_pages.add(page_no)
        pager.write_page(page_no, frame.page_data)
        checkpointed += 1

    # Flush the pager (write dirty pages to the main file).
    pager.flush()

    # Reset the WAL: clear all frames (keep the header).
    # The WAL's in-memory state is cleared; the on-disk WAL file retains
    # its header but the frames are logically invalidated (the next append
    # will overwrite them).
    wal._frames.clear()  # type: ignore[attr-defined]
    wal._frame_map.clear()  # type: ignore[attr-defined]

    return checkpointed