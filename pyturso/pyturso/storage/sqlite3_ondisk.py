"""sqlite3_ondisk — pure format knowledge: header, page/cell layouts, varints, overflow.

Ports: core/storage/sqlite3_ondisk.rs
Phase: 1 (read path — varints first; header/page/cell come in later items)
Status: varints IMPLEMENTED (read_varint, write_varint, varint_len); the rest
of the format (100-byte header, page decode, cells, overflow chains) lands in
the following Phase 1 TODO items.

Pure format knowledge, no state. If a byte offset is mentioned anywhere in
pyturso, it lives here (storage/HOWTO standing rule). This module never does
I/O directly — it decodes byte buffers the io layer produces.
"""

from __future__ import annotations

from pyturso.errors import Corrupt

__all__ = ["read_varint", "write_varint", "varint_len",
           "HEADER_SIZE", "HEADER_MAGIC", "Version", "TextEncoding",
           "DatabaseHeader", "parse_header",
           "PageType", "PageHeader", "parse_page_header",
           "cell_pointer_offsets",
           "LEAF_HEADER_SIZE", "INTERIOR_HEADER_SIZE", "CELL_PTR_SIZE",
           "TableLeafCell", "parse_table_leaf_cell",
           "TableInteriorCell", "parse_table_interior_cell",
           "Record", "parse_record", "read_serial_value", "serial_type_size",
           "OVERFLOW_HEADER_SIZE",
           "payload_overflow_threshold_max", "payload_overflow_threshold_min",
           "payload_overflows",
           "IndexLeafCell", "parse_index_leaf_cell",
           "IndexInteriorCell", "parse_index_interior_cell"]

#: Maximum varint length in bytes (SQLite varints are 1–9 bytes).
MAX_VARINT_LEN: int = 9


def read_varint(buf: bytes) -> tuple[int, int]:
    """Decode a SQLite varint from the start of ``buf``.

    Ports ``core::sqlite3_ondisk::read_varint``. SQLite varint encoding:
    bytes 1–8 each carry 7 payload bits (high bit = continuation); an optional
    9th byte carries a full 8 bits, giving 64 bits total.

    Args:
        buf: bytes with at least one varint at the start.

    Returns:
        ``(value, n_bytes)`` — the decoded value and how many bytes it spans.

    Raises:
        Corrupt: ``buf`` is too short to hold a varint, or the varint is
            encoded in 9 bytes but its top 8 bits are zero (a value < 2**56
            must not use 9 bytes — that encoding is invalid; ports the Rust
            ``bail_corrupt_error!("Invalid varint")``).
    """
    v: int = 0
    for i in range(8):
        if i >= len(buf):
            raise Corrupt("Invalid varint")
        c = buf[i]
        v = (v << 7) + (c & 0x7F)
        if (c & 0x80) == 0:
            return v, i + 1
    # 9th byte: full 8 bits. A 9-byte varint must encode a value >= 2**56, so
    # the accumulated top 8 bits (v >> 48) must be non-zero — otherwise it is
    # a wasteful/invalid encoding.
    if len(buf) < 9:
        raise Corrupt("Invalid varint")
    if (v >> 48) == 0:
        raise Corrupt("Invalid varint")
    v = (v << 8) + buf[8]
    return v, 9


def varint_len(value: int) -> int:
    """Bytes needed to encode ``value`` as a varint (1–9).

    Ports ``core::sqlite3_ondisk::varint_len``.
    """
    if value < 0:
        raise ValueError(f"varint value must be non-negative, got {value}")
    if value <= 0x7F:
        return 1
    if value > (1 << 56) - 1:
        return 9
    # bits needed, then ceil(bits / 7).
    bits = value.bit_length()
    return (bits + 6) // 7


def write_varint(buf: bytearray, value: int) -> int:
    """Encode ``value`` into ``buf`` as a varint; return bytes written.

    Ports ``core::sqlite3_ondisk::write_varint``. Writes into ``buf[0:9]``;
    ``buf`` must be at least :data:`MAX_VARINT_LEN` long (caller-sized; ports
    the Rust ``&mut [u8]`` contract).

    Args:
        buf: a writable buffer (``bytearray``) of length >= 9.
        value: the non-negative integer to encode.

    Returns:
        The number of bytes written (1–9).

    Raises:
        ValueError: ``value`` is negative, or ``buf`` is too short.
    """
    if value < 0:
        raise ValueError(f"varint value must be non-negative, got {value}")
    if len(buf) < MAX_VARINT_LEN:
        raise ValueError(f"buf must be >= {MAX_VARINT_LEN} bytes, got {len(buf)}")

    # 1 byte: 0..0x7f.
    if value <= 0x7F:
        buf[0] = value & 0x7F
        return 1

    # 2 bytes: 0x80..0x3fff.
    if value <= 0x3FFF:
        buf[0] = ((value >> 7) & 0x7F) | 0x80
        buf[1] = value & 0x7F
        return 2

    # 9 bytes: value > 2**56 - 1 (top 8 bits set).
    if value & (0xFF_000000 << 32):  # value > (1<<56)-1
        buf[8] = value & 0xFF
        v = value >> 8
        for i in range(7, -1, -1):
            buf[i] = (v & 0x7F) | 0x80
            v >>= 7
        return 9

    # 3–8 bytes: build little-endian with continuation bits, then reverse so
    # the high-continuation byte is first and the terminal byte carries no
    # continuation (matches the Rust write_varint general path).
    encoded: bytearray = bytearray()
    v = value
    while v != 0:
        encoded.append(0x80 | (v & 0x7F))
        v >>= 7
    encoded[0] &= 0x7F  # terminal byte: no continuation
    n = len(encoded)
    for i in range(n):
        buf[i] = encoded[n - 1 - i]
    return n


# ---------------------------------------------------------------------------
# Database header — ports core/storage/sqlite3_ondisk.rs DatabaseHeader.
# The 100-byte header at the start of page 1 (every SQLite-format file).
# All multi-byte fields are big-endian (SQLite on-disk convention).
# Layout documented inline per field; verified against the Rust struct.
# ---------------------------------------------------------------------------
#: The magic string at header offset 0 (16 bytes, NUL-terminated).
HEADER_MAGIC: bytes = b"SQLite format 3\x00"

#: The header is exactly 100 bytes (Rust ``const _CHECK: assert SIZE == 100``).
HEADER_SIZE: int = 100

#: Page-size bounds (ports PageSize::MIN / MAX).
PAGE_SIZE_MIN: int = 512
PAGE_SIZE_MAX: int = 65536


class Version:
    """File format read/write version (ports ``core::Version``).

    Stored as a single byte at header offsets 18/19: 1=legacy, 2=WAL, 255=MVCC.
    Kept as a plain int (not Enum) to preserve unknown values verbatim, so an
    invalid byte surfaces as data rather than being lost; the ``.wal`` /
    ``.legacy`` helpers classify.
    """

    LEGACY: int = 1
    WAL: int = 2
    MVCC: int = 255

    @staticmethod
    def is_wal(raw: int) -> bool:
        return raw == Version.WAL

    @staticmethod
    def is_legacy(raw: int) -> bool:
        return raw == Version.LEGACY


class TextEncoding:
    """Text encoding (ports ``core::TextEncoding``).

    Stored as a u32 BE at header offset 56: 0=unset(read as UTF-8), 1=UTF-8,
    2=UTF-16le, 3=UTF-16be. Kept as a plain int to preserve unknown values;
    ``is_utf8`` follows SQLite's "unset means UTF-8" rule.
    """

    UNSET: int = 0
    UTF8: int = 1
    UTF16LE: int = 2
    UTF16BE: int = 3

    @staticmethod
    def is_utf8(raw: int) -> bool:
        # SQLite treats an empty file's zero encoding as UTF-8.
        return raw in (TextEncoding.UTF8, TextEncoding.UNSET)


class DatabaseHeader:
    """The 100-byte SQLite database header, parsed. Ports ``DatabaseHeader``.

    All fields are decoded big-endian. ``parse_header`` validates the magic and
    page size and raises :class:`pyturso.errors.Corrupt` on bad input; other
    fields are carried verbatim (SQLite tolerates some legacy/unknown values).
    """

    __slots__ = (
        "page_size", "write_version", "read_version", "reserved_space",
        "max_embed_frac", "min_embed_frac", "leaf_frac", "change_counter",
        "database_size", "freelist_trunk_page", "freelist_pages",
        "schema_cookie", "schema_format", "default_page_cache_size",
        "vacuum_mode_largest_root_page", "text_encoding", "user_version",
        "incremental_vacuum_enabled", "application_id", "reserved_padding",
        "version_valid_for", "version_number",
    )

    def __init__(self, *, page_size: int, write_version: int,
                 read_version: int, reserved_space: int,
                 max_embed_frac: int, min_embed_frac: int, leaf_frac: int,
                 change_counter: int, database_size: int,
                 freelist_trunk_page: int, freelist_pages: int,
                 schema_cookie: int, schema_format: int,
                 default_page_cache_size: int,
                 vacuum_mode_largest_root_page: int,
                 text_encoding: int, user_version: int,
                 incremental_vacuum_enabled: int, application_id: int,
                 reserved_padding: bytes, version_valid_for: int,
                 version_number: int) -> None:
        self.page_size: int = page_size
        self.write_version: int = write_version
        self.read_version: int = read_version
        self.reserved_space: int = reserved_space
        self.max_embed_frac: int = max_embed_frac
        self.min_embed_frac: int = min_embed_frac
        self.leaf_frac: int = leaf_frac
        self.change_counter: int = change_counter
        self.database_size: int = database_size
        self.freelist_trunk_page: int = freelist_trunk_page
        self.freelist_pages: int = freelist_pages
        self.schema_cookie: int = schema_cookie
        self.schema_format: int = schema_format
        self.default_page_cache_size: int = default_page_cache_size
        self.vacuum_mode_largest_root_page: int = vacuum_mode_largest_root_page
        self.text_encoding: int = text_encoding
        self.user_version: int = user_version
        self.incremental_vacuum_enabled: int = incremental_vacuum_enabled
        self.application_id: int = application_id
        self.reserved_padding: bytes = reserved_padding
        self.version_valid_for: int = version_valid_for
        self.version_number: int = version_number

    def usable_page_size(self) -> int:
        """Usable bytes per page: page_size minus reserved trailing space.

        Ports ``DatabaseHeader::usable_space``.
        """
        return self.page_size - self.reserved_space


def parse_header(buf: bytes) -> DatabaseHeader:
    """Parse the 100-byte header from ``buf[0:100]``.

    Args:
        buf: at least ``HEADER_SIZE`` (100) bytes; only the first 100 are read.

    Returns:
        The decoded :class:`DatabaseHeader`.

    Raises:
        Corrupt: the magic string does not match ("File is not a database"),
            ``buf`` is shorter than 100 bytes, or the page-size field is not a
            valid SQLite page size (power of two in 512..65536, or the value 1
            meaning 65536).
    """
    if len(buf) < HEADER_SIZE:
        raise Corrupt(f"header too short: {len(buf)} bytes, need {HEADER_SIZE}")
    if buf[0:16] != HEADER_MAGIC:
        raise Corrupt("File is not a database")

    raw_page_size = int.from_bytes(buf[16:18], "big")
    page_size = _decode_page_size(raw_page_size)

    return DatabaseHeader(
        page_size=page_size,
        write_version=buf[18],
        read_version=buf[19],
        reserved_space=buf[20],
        max_embed_frac=buf[21],
        min_embed_frac=buf[22],
        leaf_frac=buf[23],
        change_counter=int.from_bytes(buf[24:28], "big"),
        database_size=int.from_bytes(buf[28:32], "big"),
        freelist_trunk_page=int.from_bytes(buf[32:36], "big"),
        freelist_pages=int.from_bytes(buf[36:40], "big"),
        schema_cookie=int.from_bytes(buf[40:44], "big"),
        schema_format=int.from_bytes(buf[44:48], "big"),
        default_page_cache_size=int.from_bytes(buf[48:52], "big"),
        vacuum_mode_largest_root_page=int.from_bytes(buf[52:56], "big"),
        text_encoding=int.from_bytes(buf[56:60], "big"),
        user_version=int.from_bytes(buf[60:64], "big", signed=True),
        incremental_vacuum_enabled=int.from_bytes(buf[64:68], "big"),
        application_id=int.from_bytes(buf[68:72], "big", signed=True),
        reserved_padding=bytes(buf[72:92]),
        version_valid_for=int.from_bytes(buf[92:96], "big"),
        version_number=int.from_bytes(buf[96:100], "big"),
    )


def _decode_page_size(raw: int) -> int:
    """Decode the on-disk page-size u16 into actual bytes (ports PageSize).

    The stored u16 value ``1`` means 65536 (does not fit in 2 bytes). Otherwise
    the value must be a power of two in [512, 65536]; anything else is corrupt.
    """
    if raw == 1:
        return PAGE_SIZE_MAX
    if raw < PAGE_SIZE_MIN or raw > PAGE_SIZE_MAX or (raw & (raw - 1)) != 0:
        raise Corrupt(f"invalid page size in database header: {raw}")
    return raw


# ---------------------------------------------------------------------------
# Page decode — ports core/storage/sqlite3_ondisk.rs PageType +
# core/storage/pager.rs PageInner (the read-side page header + cell pointer
# array). Page 1's content starts at offset 100 (after the db header);
# all other pages start at offset 0. All fields are big-endian.
# ---------------------------------------------------------------------------
#: Cell-pointer size: 2 bytes (u16 BE). Ports CELL_PTR_SIZE_BYTES.
CELL_PTR_SIZE: int = 2

#: Leaf page header size: 8 bytes. Ports LEAF_PAGE_HEADER_SIZE_BYTES.
LEAF_HEADER_SIZE: int = 8

#: Interior page header size: 12 bytes (leaf header + 4-byte rightmost ptr).
#: Ports INTERIOR_PAGE_HEADER_SIZE_BYTES.
INTERIOR_HEADER_SIZE: int = 12

#: Sentinel: the on-disk cell-content-area value 0 means 65536 (ports the
#: ``if offset == 0 { PageSize::MAX }`` convention).
_CELL_CONTENT_ZERO_SENTINEL: int = 65536


class PageType:
    """B-tree page type (ports ``core::PageType``).

    The single byte at page-content offset 0 identifies the page variant.
    Kept as plain int constants (not Enum) to mirror the Rust ``TryFrom<u8>``
    shape: an invalid byte raises ``Corrupt`` via :func:`parse_page_header`.
    """

    INDEX_INTERIOR: int = 2
    TABLE_INTERIOR: int = 5
    INDEX_LEAF: int = 10
    TABLE_LEAF: int = 13

    @staticmethod
    def is_table(raw: int) -> bool:
        return raw in (PageType.TABLE_INTERIOR, PageType.TABLE_LEAF)

    @staticmethod
    def is_interior(raw: int) -> bool:
        return raw in (PageType.INDEX_INTERIOR, PageType.TABLE_INTERIOR)

    @staticmethod
    def is_leaf(raw: int) -> bool:
        return raw in (PageType.INDEX_LEAF, PageType.TABLE_LEAF)


class PageHeader:
    """Parsed B-tree page header. Ports the read side of ``PageInner``.

    Fields (all big-endian, offsets relative to the *page content* start —
    i.e. after the 100-byte db header on page 1, 0 otherwise):

    | Offset | Size | Field |
    |--------|------|-------|
    | 0 | 1 | page type (``PageType`` byte) |
    | 1 | 2 | first freeblock offset (0 = none) |
    | 3 | 2 | cell count |
    | 5 | 2 | cell content area start (0 = 65536) |
    | 7 | 1 | fragmented free bytes |
    | 8 | 4 | rightmost pointer (interior pages only; absent on leaf) |

    ``page_no`` is 1-based (page 1 carries the db header); it determines the
    content offset (100 for page 1, 0 otherwise) — ports ``PageInner::offset``.
    """

    __slots__ = (
        "page_no", "raw_type", "first_freeblock", "cell_count",
        "cell_content_start", "fragmented_free_bytes", "rightmost_pointer",
    )

    def __init__(self, *, page_no: int, raw_type: int,
                 first_freeblock: int, cell_count: int,
                 cell_content_start: int, fragmented_free_bytes: int,
                 rightmost_pointer: int | None) -> None:
        self.page_no: int = page_no
        self.raw_type: int = raw_type
        self.first_freeblock: int = first_freeblock
        self.cell_count: int = cell_count
        self.cell_content_start: int = cell_content_start
        self.fragmented_free_bytes: int = fragmented_free_bytes
        self.rightmost_pointer: int | None = rightmost_pointer

    @property
    def is_interior(self) -> bool:
        return PageType.is_interior(self.raw_type)

    @property
    def is_leaf(self) -> bool:
        return PageType.is_leaf(self.raw_type)

    @property
    def is_table(self) -> bool:
        return PageType.is_table(self.raw_type)

    @property
    def header_size(self) -> int:
        """Bytes the page header itself occupies (8 leaf / 12 interior)."""
        return INTERIOR_HEADER_SIZE if self.is_interior else LEAF_HEADER_SIZE


def _content_offset(page_no: int) -> int:
    """Where page content starts within the raw page buffer (ports offset()).

    Page 1 carries the 100-byte database header; every other page starts at 0.
    """
    return HEADER_SIZE if page_no == 1 else 0


def parse_page_header(buf: bytes, page_no: int) -> PageHeader:
    """Parse a B-tree page header from ``buf`` (one full page).

    Args:
        buf: the raw page bytes (at least ``page_size`` long; only the header
            fields are read).
        page_no: the 1-based page number (determines the 100-byte offset for
            page 1).

    Returns:
        The decoded :class:`PageHeader`.

    Raises:
        Corrupt: the page-type byte is not a valid ``PageType``, or the buffer
            is too short to hold the header.
    """
    off = _content_offset(page_no)
    if len(buf) < off + LEAF_HEADER_SIZE:
        raise Corrupt(f"page {page_no}: buffer too short for header")

    raw_type = buf[off]
    if raw_type not in (PageType.INDEX_INTERIOR, PageType.TABLE_INTERIOR,
                        PageType.INDEX_LEAF, PageType.TABLE_LEAF):
        raise Corrupt(f"Invalid page type: {raw_type}")

    first_freeblock = int.from_bytes(buf[off + 1 : off + 3], "big")
    cell_count = int.from_bytes(buf[off + 3 : off + 5], "big")
    raw_content = int.from_bytes(buf[off + 5 : off + 7], "big")
    cell_content_start = _CELL_CONTENT_ZERO_SENTINEL if raw_content == 0 else raw_content
    fragmented = buf[off + 7]

    rightmost_pointer: int | None = None
    if PageType.is_interior(raw_type):
        if len(buf) < off + INTERIOR_HEADER_SIZE:
            raise Corrupt(f"page {page_no}: buffer too short for interior header")
        rightmost_pointer = int.from_bytes(buf[off + 8 : off + 12], "big")

    return PageHeader(
        page_no=page_no,
        raw_type=raw_type,
        first_freeblock=first_freeblock,
        cell_count=cell_count,
        cell_content_start=cell_content_start,
        fragmented_free_bytes=fragmented,
        rightmost_pointer=rightmost_pointer,
    )


def cell_pointer_offsets(buf: bytes, header: PageHeader) -> list[int]:
    """Read the cell-pointer array; return each cell's offset within the page.

    The array starts right after the page header (offset + header_size) and
    contains ``header.cell_count`` u16 BE values, each a byte offset from the
    *start of the page* (not the content area) to the cell. Ports
    ``PageInner::cell_pointer_array_offset`` + the per-cell read in
    ``cell_get``.

    Raises:
        Corrupt: the buffer is too short to hold the full pointer array.
    """
    off = _content_offset(header.page_no)
    array_start = off + header.header_size
    array_end = array_start + header.cell_count * CELL_PTR_SIZE
    if len(buf) < array_end:
        raise Corrupt(
            f"page {header.page_no}: cell pointer array extends beyond buffer"
        )
    offsets: list[int] = []
    for i in range(header.cell_count):
        ptr = int.from_bytes(
            buf[array_start + i * CELL_PTR_SIZE : array_start + i * CELL_PTR_SIZE + 2],
            "big",
        )
        offsets.append(ptr)
    return offsets

# ---------------------------------------------------------------------------
# Leaf table cells — ports core/storage/sqlite3_ondisk.rs TableLeafCell +
# the TableLeaf branch of read_btree_cell. A table-leaf cell is:
#
#   payload_size (varint)  rowid (varint)  payload (local bytes)
#
# Overflow is handled in a later TODO item (overflow chains); here the
# payload is the *local* portion — the first_overflow_page is decoded but
# not followed.
# ---------------------------------------------------------------------------
class TableLeafCell:
    """A decoded table-leaf B-tree cell.

    Ports ``core::TableLeafCell``. ``payload`` is the *local* (on-page) payload
    bytes; ``payload_size`` is the *total* payload including overflow (may be
    larger than ``len(payload)``). ``first_overflow_page`` is ``None`` when the
    payload fits entirely on the page.
    """

    __slots__ = ("rowid", "payload", "payload_size", "first_overflow_page")

    def __init__(self, *, rowid: int, payload: bytes, payload_size: int,
                 first_overflow_page: int | None) -> None:
        self.rowid: int = rowid
        self.payload: bytes = payload
        self.payload_size: int = payload_size
        self.first_overflow_page: int | None = first_overflow_page


def parse_table_leaf_cell(
    page: bytes, cell_offset: int, usable_size: int
) -> TableLeafCell:
    """Decode a table-leaf cell at ``cell_offset`` within ``page``.

    Args:
        page: the raw page bytes.
        cell_offset: byte offset of the cell within the page (from
            :func:`cell_pointer_offsets`).
        usable_size: usable page size (page_size - reserved_space).

    Returns:
        The decoded :class:`TableLeafCell` with local payload.

    Raises:
        Corrupt: the cell extends beyond the page, or a varint is truncated.

    Note:
        Overflow threshold math is ported from
        ``payload_overflow_threshold_max`` / ``_min`` + ``payload_overflows``
        in a later TODO item (overflow chains). Here, if the payload fits
        on the page (the common case for small rows), the local payload is
        the full payload. When overflow is implemented, this function will
        extract the first_overflow_page and trim the local payload.
    """
    pos = cell_offset
    # payload_size varint (total, including overflow).
    payload_size, n = read_varint(page[pos:])
    pos += n
    # rowid varint.
    rowid, n = read_varint(page[pos:])
    pos += n

    # For now (before overflow chains land): if the payload fits on the page,
    # take it all. When it doesn't, raise — the overflow TODO handles it.
    if payload_size > len(page) - pos:
        raise Corrupt(
            f"payload overflow not yet supported (payload_size={payload_size}, "
            f"available={len(page) - pos})"
        )
    payload = page[pos : pos + payload_size]
    return TableLeafCell(
        rowid=rowid,
        payload=payload,
        payload_size=payload_size,
        first_overflow_page=None,
    )


# ---------------------------------------------------------------------------
# Record decode — ports core/storage/sqlite3_ondisk.rs read_value +
# SerialType. A record is a header (serial-type varints) followed by the
# values in order. This is the *raw* decode (serial types inline); it will be
# refactored onto ``types.record`` when the types module lands.
# ---------------------------------------------------------------------------
class Record:
    """A decoded record: the serial types + the values.

    ``serial_types`` is the list of serial-type codes; ``values`` is the
    decoded Python values (``int`` / ``float`` / ``str`` / ``bytes`` / ``None``).
    """

    __slots__ = ("serial_types", "values")

    def __init__(self, serial_types: list[int], values: list[object]) -> None:
        self.serial_types: list[int] = serial_types
        self.values: list[object] = values


def serial_type_size(st: int) -> int:
    """Bytes a value of serial type ``st`` occupies on disk.

    Ports ``SerialType::size()``. The SQLite serial-type encoding:
      - 0: NULL (0 bytes)
      - 1: i8 (1)
      - 2: i16 (2)
      - 3: i24 (3)
      - 4: i32 (4)
      - 5: i48 (6)
      - 6: i64 (8)
      - 7: f64 (8)
      - 8: const 0 (0)
      - 9: const 1 (0)
      - >=12 even: BLOB ((st - 12) // 2 bytes)
      - >=13 odd: TEXT ((st - 13) // 2 bytes)
      - 10, 11: reserved (corrupt if encountered)
    """
    if st <= 0:
        return 0
    if st <= 4:
        return st  # 1,2,3,4
    if st == 5:
        return 6
    if st <= 7:
        return 8  # 6→i64 8 bytes, 7→f64 8 bytes
    if st <= 9:
        return 0  # 8,9 → const 0/1, 0 bytes
    # st >= 12
    return (st - 12) // 2 if st % 2 == 0 else (st - 13) // 2


def read_serial_value(buf: bytes, serial_type: int) -> tuple[object, int]:
    """Decode one value of ``serial_type`` from ``buf``.

    Ports ``read_value``. Returns ``(value, n_bytes)``. Raises ``Corrupt`` on
    a truncated value, an invalid serial type (10/11), or a too-short buffer.
    """
    import struct

    if serial_type == 0:
        return None, 0
    if serial_type == 1:
        if len(buf) < 1:
            raise Corrupt("Invalid UInt8 value")
        return int.from_bytes(buf[0:1], "big", signed=True), 1
    if serial_type == 2:
        if len(buf) < 2:
            raise Corrupt("Invalid BEInt16 value")
        return int.from_bytes(buf[0:2], "big", signed=True), 2
    if serial_type == 3:
        if len(buf) < 3:
            raise Corrupt("Invalid BEInt24 value")
        b = buf[0:3]
        sign = 0xFF if b[0] & 0x80 else 0x00
        return int.from_bytes(bytes([sign, b[0], b[1], b[2]]), "big", signed=True), 3
    if serial_type == 4:
        if len(buf) < 4:
            raise Corrupt("Invalid BEInt32 value")
        return int.from_bytes(buf[0:4], "big", signed=True), 4
    if serial_type == 5:
        if len(buf) < 6:
            raise Corrupt("Invalid BEInt48 value")
        b = buf[0:6]
        sign = 0xFF if b[0] & 0x80 else 0x00
        return int.from_bytes(bytes([sign, sign, b[0], b[1], b[2], b[3], b[4], b[5]]),
                              "big", signed=True), 6
    if serial_type == 6:
        if len(buf) < 8:
            raise Corrupt("Invalid BEInt64 value")
        return int.from_bytes(buf[0:8], "big", signed=True), 8
    if serial_type == 7:
        if len(buf) < 8:
            raise Corrupt("Invalid BEFloat64 value")
        return struct.unpack(">d", buf[0:8])[0], 8
    if serial_type == 8:
        return 0, 0
    if serial_type == 9:
        return 1, 0
    if serial_type in (10, 11):
        raise Corrupt(f"Invalid serial type: {serial_type}")
    # BLOB (even >=12) or TEXT (odd >=13).
    size = serial_type_size(serial_type)
    if len(buf) < size:
        raise Corrupt(f"value too short for serial type {serial_type}")
    if serial_type % 2 == 0:
        return bytes(buf[0:size]), size
    # TEXT: decode as UTF-8 (SQLite's default encoding).
    return buf[0:size].decode("utf-8"), size


def parse_record(payload: bytes) -> Record:
    """Decode a record (header + values) from ``payload``.

    A SQLite record is:
      - header_size varint (bytes in the header, including this varint)
      - N serial-type varints
      - N values (in order, each ``serial_type_size(st)`` bytes)

    Ports the record decode path in ``core/storage/sqlite3_ondisk.rs``. The
    raw values are returned as Python objects; type affinity / coercion is
    deferred to the ``types`` module (Phase 2).
    """
    header_size, n = read_varint(payload)
    pos = n
    serial_types: list[int] = []
    while pos < header_size:
        st, n = read_varint(payload[pos:])
        serial_types.append(st)
        pos += n
    if pos != header_size:
        raise Corrupt(
            f"record header size mismatch: declared {header_size}, "
            f"consumed {pos}"
        )
    # Values follow the header.
    value_pos = header_size
    values: list[object] = []
    for st in serial_types:
        val, n = read_serial_value(payload[value_pos:], st)
        values.append(val)
        value_pos += n
    return Record(serial_types=serial_types, values=values)


# ---------------------------------------------------------------------------
# Interior table cells — ports core/storage/sqlite3_ondisk.rs TableInteriorCell
# + the TableInterior branch of read_btree_cell. An interior table cell is:
#
#   left_child_page (u32 BE, 4 bytes)  rowid (varint)
#
# The rightmost child pointer (the child for keys > all cell keys) lives in
# the page header at offset 8 — already parsed by parse_page_header as
# rightmost_pointer. It is NOT a cell.
# ---------------------------------------------------------------------------
class TableInteriorCell:
    """A decoded interior table B-tree cell.

    Ports ``core::TableInteriorCell``. ``left_child_page`` is the 1-based page
    number of the child subtree containing all rowids <= ``rowid``.
    """

    __slots__ = ("left_child_page", "rowid")

    def __init__(self, *, left_child_page: int, rowid: int) -> None:
        self.left_child_page: int = left_child_page
        self.rowid: int = rowid


def parse_table_interior_cell(
    page: bytes, cell_offset: int
) -> TableInteriorCell:
    """Decode an interior table cell at ``cell_offset`` within ``page``.

    Args:
        page: the raw page bytes.
        cell_offset: byte offset of the cell within the page (from
            :func:`cell_pointer_offsets`).

    Returns:
        The decoded :class:`TableInteriorCell`.

    Raises:
        Corrupt: the cell extends beyond the page, or the rowid varint is
            truncated.
    """
    pos = cell_offset
    if pos + 4 > len(page):
        raise Corrupt(
            f"interior cell at offset {cell_offset} extends beyond page "
            f"({len(page)} bytes)"
        )
    left_child_page = int.from_bytes(page[pos : pos + 4], "big")
    pos += 4
    rowid, _ = read_varint(page[pos:])
    return TableInteriorCell(left_child_page=left_child_page, rowid=rowid)


# ---------------------------------------------------------------------------
# Overflow chains — ports core/storage/sqlite3_ondisk.rs payload_overflows,
# payload_overflow_threshold_max/min (in btree.rs), and read_payload.
#
# When a cell's payload exceeds the max-local threshold, only a portion stays
# on the page; the rest flows into a chain of overflow pages. Each overflow
# page starts with a 4-byte BE next-page pointer (0 = end of chain); the
# remaining bytes are payload data. The threshold math determines how much
# stays local.
# ---------------------------------------------------------------------------

#: Bytes of overhead per overflow page (the 4-byte next-page pointer).
OVERFLOW_HEADER_SIZE: int = 4


def payload_overflow_threshold_max(raw_type: int, usable_size: int) -> int:
    """Max bytes of payload that can stay on the page without overflowing.

    Ports ``payload_overflow_threshold_max`` in btree.rs. Table pages use
    ``usable_size - 35``; index pages use ``((usable_size - 12) * 64 / 255) - 23``.
    """
    if PageType.is_table(raw_type):
        return usable_size - 35
    return ((usable_size - 12) * 64 // 255) - 23


def payload_overflow_threshold_min(raw_type: int, usable_size: int) -> int:
    """Min bytes of payload kept local when the cell overflows.

    Ports ``payload_overflow_threshold_min`` in btree.rs. Same formula for
    all page types: ``((usable_size - 12) * 32 / 255) - 23``.
    """
    return ((usable_size - 12) * 32 // 255) - 23


def payload_overflows(
    payload_size: int,
    max_local: int,
    min_local: int,
    usable_size: int,
) -> tuple[bool, int]:
    """Determine whether a payload overflows and how many bytes stay local.

    Ports ``payload_overflows`` in sqlite3_ondisk.rs. Returns ``(overflows,
    local_bytes)``. When ``overflows`` is False, ``local_bytes`` is 0 (the
    caller should take ``min(payload_size, available)``). When True,
    ``local_bytes`` is the number of payload bytes on the page (followed by
    the 4-byte first-overflow-page pointer).

    The formula (from the SQLite file format spec):
      - if payload_size <= max_local: no overflow.
      - else: space_left = min_local + (payload_size - min_local) % (usable_size - 4)
        - if space_left > max_local: space_left = min_local
      - local = space_left + 4 (the +4 is for the overflow page pointer)
    """
    if payload_size <= max_local:
        return (False, 0)
    space_left = min_local + (payload_size - min_local) % (usable_size - OVERFLOW_HEADER_SIZE)
    if space_left > max_local:
        space_left = min_local
    return (True, space_left + OVERFLOW_HEADER_SIZE)


# ---------------------------------------------------------------------------
# Index cells — ports core/storage/sqlite3_ondisk.rs IndexLeafCell /
# IndexInteriorCell + the IndexLeaf/IndexInterior branches of read_btree_cell.
#
# Index cells carry the record key as payload (no separate rowid — the key IS
# the payload). Interior index cells have a left_child_page before the payload.
# Overflow is handled the same as table cells (threshold math + chain).
# ---------------------------------------------------------------------------
class IndexLeafCell:
    """A decoded index-leaf B-tree cell.

    Ports ``core::IndexLeafCell``. ``payload`` is the local (on-page) record
    key; ``payload_size`` is the total (including overflow).
    """

    __slots__ = ("payload", "payload_size", "first_overflow_page")

    def __init__(self, *, payload: bytes, payload_size: int,
                 first_overflow_page: int | None) -> None:
        self.payload: bytes = payload
        self.payload_size: int = payload_size
        self.first_overflow_page: int | None = first_overflow_page


class IndexInteriorCell:
    """A decoded interior index B-tree cell.

    Ports ``core::IndexInteriorCell``. ``left_child_page`` is the child
    subtree; ``payload`` is the local key.
    """

    __slots__ = ("left_child_page", "payload", "payload_size",
                 "first_overflow_page")

    def __init__(self, *, left_child_page: int, payload: bytes,
                 payload_size: int,
                 first_overflow_page: int | None) -> None:
        self.left_child_page: int = left_child_page
        self.payload: bytes = payload
        self.payload_size: int = payload_size
        self.first_overflow_page: int | None = first_overflow_page


def parse_index_leaf_cell(
    page: bytes, cell_offset: int, usable_size: int
) -> IndexLeafCell:
    """Decode an index-leaf cell at ``cell_offset`` within ``page``.

    Format: ``payload_size (varint) → payload (local bytes)``.
    """
    pos = cell_offset
    payload_size, n = read_varint(page[pos:])
    pos += n
    if payload_size > len(page) - pos:
        raise Corrupt(
            f"index leaf overflow not yet supported (payload_size={payload_size}, "
            f"available={len(page) - pos})"
        )
    payload = page[pos : pos + payload_size]
    return IndexLeafCell(
        payload=payload,
        payload_size=payload_size,
        first_overflow_page=None,
    )


def parse_index_interior_cell(
    page: bytes, cell_offset: int, usable_size: int
) -> IndexInteriorCell:
    """Decode an interior index cell at ``cell_offset`` within ``page``.

    Format: ``left_child_page (u32 BE, 4 bytes) → payload_size (varint)
    → payload (local bytes)``.
    """
    pos = cell_offset
    if pos + 4 > len(page):
        raise Corrupt(
            f"index interior cell at offset {cell_offset} extends beyond page"
        )
    left_child_page = int.from_bytes(page[pos : pos + 4], "big")
    pos += 4
    payload_size, n = read_varint(page[pos:])
    pos += n
    if payload_size > len(page) - pos:
        raise Corrupt(
            f"index interior overflow not yet supported (payload_size={payload_size}, "
            f"available={len(page) - pos})"
        )
    payload = page[pos : pos + payload_size]
    return IndexInteriorCell(
        left_child_page=left_child_page,
        payload=payload,
        payload_size=payload_size,
        first_overflow_page=None,
    )
