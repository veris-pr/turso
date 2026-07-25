"""value — the tagged Value type (NULL/INTEGER/REAL/TEXT/BLOB).

Ports: core/types.rs (``Value``, ``ValueType``, ``Numeric``).
Phase: 2
Status: IMPLEMENTED.

SQLite uses *manifest typing*: types live on **values**, not columns. Every
value that flows through the engine is one of five storage classes:

  - ``NULL``   — no value
  - ``INTEGER`` — a 64-bit signed integer (i64)
  - ``REAL``   — a 64-bit IEEE float (f64)
  - ``TEXT``   — a UTF-8 string
  - ``BLOB``   — raw bytes

pyturso represents these as a frozen dataclass :class:`Value` with a
:class:`StorageClass` tag and a payload. This mirrors the Rust
``Value``/``Numeric`` shape (``Null | Numeric(Integer(i64) | Float(f64)) |
Text | Blob``) while being idiomatic Python: pattern-matching on the tag,
not on nested enums.

**Equality does not cross-coerce**: ``Value.integer(1) != Value.real(1.0)``
and ``Value.text("10") != Value.integer(10)``. SQLite *does* cross-compare
in some contexts (e.g. ``WHERE x = 10`` with ``x`` holding ``"10"``), but
that is *affinity* — explicit coercion applied by the comparison layer
(:mod:`pyturso.types.compare`), not by the value type itself. Keeping the
value type's equality strict makes the coercion points explicit, mirroring
the Rust where ``Value`` equality is structural and coercion is a separate
step.

Python ``int`` is unbounded — i64 bounds are **not** enforced here (the
:mod:`pyturso.types.numeric` module handles i64 emulation/overflow-to-REAL
at the points where the Rust does i64 arithmetic). A ``Value.integer``
constructed with a value outside i64 range is still a valid ``Value`` object;
the bounds check happens when serializing or doing arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union

__all__ = ["StorageClass", "Value"]


class StorageClass(str, Enum):
    """The five SQLite storage classes. ``str`` mixin for ``typeof()`` output."""

    NULL = "NULL"
    INTEGER = "INTEGER"
    REAL = "REAL"
    TEXT = "TEXT"
    BLOB = "BLOB"

    # SQLite's typeof() uses these lowercase names.
    @property
    def typeof(self) -> str:
        """The ``typeof(x)`` SQL function output for this storage class."""
        return {
            StorageClass.NULL: "null",
            StorageClass.INTEGER: "integer",
            StorageClass.REAL: "real",
            StorageClass.TEXT: "text",
            StorageClass.BLOB: "blob",
        }[self]


@dataclass(frozen=True)
class Value:
    """A tagged SQLite value. One of the five storage classes.

    Construct via the classmethods (:meth:`null`, :meth:`integer`,
    :meth:`real`, :meth:`text`, :meth:`blob`) — the ``storage_class`` and
    payload are set together so they can never disagree. The payload type
    matches the class:

      - ``NULL``   → ``None``
      - ``INTEGER`` → ``int``
      - ``REAL``   → ``float``
      - ``TEXT``   → ``str``
      - ``BLOB``   → ``bytes``

    Equality is **structural within the same storage class only**:
    ``Value.integer(1) == Value.integer(1)`` but
    ``Value.integer(1) != Value.real(1.0)``. Cross-class comparison (which
    SQLite does in affinity contexts) is :mod:`pyturso.types.compare`'s job.
    """

    storage_class: StorageClass
    payload: Union[int, float, str, bytes, None]

    # --- constructors -----------------------------------------------------
    @classmethod
    def null(cls) -> Value:
        """The NULL value (payload ``None``)."""
        return cls(storage_class=StorageClass.NULL, payload=None)

    @classmethod
    def integer(cls, value: int) -> Value:
        """An INTEGER value (payload ``int``)."""
        return cls(storage_class=StorageClass.INTEGER, payload=value)

    @classmethod
    def real(cls, value: float) -> Value:
        """A REAL value (payload ``float``)."""
        return cls(storage_class=StorageClass.REAL, payload=value)

    @classmethod
    def text(cls, value: str) -> Value:
        """A TEXT value (payload ``str``)."""
        return cls(storage_class=StorageClass.TEXT, payload=value)

    @classmethod
    def blob(cls, value: bytes) -> Value:
        """A BLOB value (payload ``bytes``)."""
        return cls(storage_class=StorageClass.BLOB, payload=value)

    # --- queries -----------------------------------------------------------
    def type_of(self) -> StorageClass:
        """Return the storage class (ports ``Value::value_type``)."""
        return self.storage_class

    @property
    def is_null(self) -> bool:
        return self.storage_class is StorageClass.NULL

    @property
    def is_integer(self) -> bool:
        return self.storage_class is StorageClass.INTEGER

    @property
    def is_real(self) -> bool:
        return self.storage_class is StorageClass.REAL

    @property
    def is_text(self) -> bool:
        return self.storage_class is StorageClass.TEXT

    @property
    def is_blob(self) -> bool:
        return self.storage_class is StorageClass.BLOB

    @property
    def is_numeric(self) -> bool:
        """INTEGER or REAL (ports ``Numeric`` membership)."""
        return self.storage_class in (StorageClass.INTEGER, StorageClass.REAL)

    # --- equality (structural, no cross-coercion) -------------------------
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Value):
            return NotImplemented
        return (
            self.storage_class == other.storage_class
            and self.payload == other.payload
        )

    def __hash__(self) -> int:
        return hash((self.storage_class, self.payload))