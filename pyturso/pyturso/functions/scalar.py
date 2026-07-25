"""scalar — initial scalar function set, registered on import.

Ports: core/functions/string.rs, core/functions/math.rs, core/function.rs.
Phase: 6
Status: IMPLEMENTED (batch 1: length, upper, lower, abs, typeof, coalesce,
ifnull, nullif, min, max, round, hex).

Each function takes a list of :class:`Value` arguments and returns a single
:class:`Value`. NULL inputs produce NULL outputs (SQLite's NULL propagation),
except for ``coalesce``/``ifnull`` which are NULL-skipping by design.
"""

from __future__ import annotations
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="arg-type"
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="index"
# mypy: disable-error-code="operator"

import math as _math
import struct

from pyturso.types.value import StorageClass, Value

from .registry import registry


def _register() -> None:
    """Register the initial scalar function set."""
    r = registry

    # --- string functions ---
    r.register("length", 1, _fn_length)
    r.register("upper", 1, _fn_upper)
    r.register("lower", 1, _fn_lower)
    r.register("hex", 1, _fn_hex)

        # --- string functions batch 2 ---
    r.register("substr", -1, _fn_substr)
    r.register("trim", -1, _fn_trim)
    r.register("ltrim", -1, _fn_ltrim)
    r.register("rtrim", -1, _fn_rtrim)
    r.register("replace", 3, _fn_replace)
    r.register("instr", 2, _fn_instr)
    r.register("quote", 1, _fn_quote)
    r.register("char", -1, _fn_char)
    r.register("unicode", 1, _fn_unicode)

    # --- LIKE/GLOB ---
    from .like import like_function, glob_function
    r.register("like", -1, like_function)
    r.register("glob", 2, glob_function)

    # --- math functions ---
    r.register("abs", 1, _fn_abs)
    r.register("round", -1, _fn_round)
    r.register("ceil", 1, _fn_ceil)
    r.register("ceiling", 1, _fn_ceil)
    r.register("floor", 1, _fn_floor)
    r.register("sign", 1, _fn_sign)
    r.register("sqrt", 1, _fn_sqrt)
    r.register("pow", 2, _fn_pow)
    r.register("power", 2, _fn_pow)

    # --- type functions ---
    r.register("typeof", 1, _fn_typeof)

    # --- NULL-handling functions ---
    r.register("coalesce", -1, _fn_coalesce)
    r.register("ifnull", 2, _fn_ifnull)
    r.register("nullif", 2, _fn_nullif)

    # --- min/max (scalar forms) ---
    r.register("min", -1, _fn_min)
    r.register("max", -1, _fn_max)


# --- string functions ---

def _fn_length(args: list[Value]) -> Value:
    v = args[0]
    if v.is_null:
        return Value.null()
    if v.is_text:
        return Value.integer(len(v.payload))  # type: ignore[arg-type]
    if v.is_blob:
        return Value.integer(len(v.payload))  # type: ignore[arg-type]
    # Numeric → convert to text first.
    return Value.integer(len(str(v.payload)))


def _fn_upper(args: list[Value]) -> Value:
    v = args[0]
    if v.is_null:
        return Value.null()
    if v.is_text:
        return Value.text(v.payload.upper())  # type: ignore[union-attr]
    return Value.text(str(v.payload).upper())


def _fn_lower(args: list[Value]) -> Value:
    v = args[0]
    if v.is_null:
        return Value.null()
    if v.is_text:
        return Value.text(v.payload.lower())  # type: ignore[union-attr]
    return Value.text(str(v.payload).lower())


def _fn_hex(args: list[Value]) -> Value:
    v = args[0]
    if v.is_null:
        return Value.null()
    if v.is_blob:
        return Value.text(v.payload.hex().upper())  # type: ignore[union-attr]
    if v.is_integer:
        # SQLite hex(int) = hex of the 8-byte big-endian representation.
        i = v.payload  # type: ignore[assignment]
        if i == 0:
            return Value.text("0")
        # Use 8-byte signed representation (SQLite uses 64-bit).
        try:
            return Value.text(i.to_bytes(8, "big", signed=True).hex().upper().lstrip("0"))
        except OverflowError:
            return Value.text(str(i))  # fallback for values outside i64
    return Value.text(str(v.payload).encode().hex().upper())


# --- string functions batch 2 ---

def _fn_substr(args: list[Value]) -> Value:
    """substr(s, start[, length]) — 1-based, negative start counts from end."""
    s = args[0]
    if s.is_null:
        return Value.null()
    text = s.payload if s.is_text else str(s.payload)  # type: ignore[union-attr]
    start_v = args[1]
    if start_v.is_null:
        return Value.null()
    start = int(start_v.payload)  # type: ignore[assignment]
    if len(args) > 2:
        length_v = args[2]
        if length_v.is_null:
            return Value.null()
        length = int(length_v.payload)  # type: ignore[assignment]
    else:
        length = len(text)  # to end

    # SQLite: 1-based; negative start counts from end.
    if start < 0:
        start = len(text) + start + 1  # -1 = last char
    if start < 1:
        start = 1
    # Adjust for 1-based indexing.
    start_idx = start - 1
    if start_idx >= len(text):
        return Value.text("")
    end_idx = start_idx + length
    return Value.text(text[start_idx:end_idx])


def _fn_trim(args: list[Value]) -> Value:
    """trim(s[, chars]) — trim chars from both ends (default: spaces)."""
    v = args[0]
    if v.is_null:
        return Value.null()
    text = v.payload if v.is_text else str(v.payload)  # type: ignore[union-attr]
    chars = args[1].payload if len(args) > 1 and not args[1].is_null else None  # type: ignore[union-attr]
    if chars is None:
        return Value.text(text.strip())
    return Value.text(text.strip(chars))


def _fn_ltrim(args: list[Value]) -> Value:
    v = args[0]
    if v.is_null:
        return Value.null()
    text = v.payload if v.is_text else str(v.payload)  # type: ignore[union-attr]
    chars = args[1].payload if len(args) > 1 and not args[1].is_null else None  # type: ignore[union-attr]
    if chars is None:
        return Value.text(text.lstrip())
    return Value.text(text.lstrip(chars))


def _fn_rtrim(args: list[Value]) -> Value:
    v = args[0]
    if v.is_null:
        return Value.null()
    text = v.payload if v.is_text else str(v.payload)  # type: ignore[union-attr]
    chars = args[1].payload if len(args) > 1 and not args[1].is_null else None  # type: ignore[union-attr]
    if chars is None:
        return Value.text(text.rstrip())
    return Value.text(text.rstrip(chars))


def _fn_replace(args: list[Value]) -> Value:
    """replace(s, pattern, replacement) — replace all occurrences."""
    s, pat, repl = args[0], args[1], args[2]
    if s.is_null or pat.is_null or repl.is_null:
        return Value.null()
    text = s.payload if s.is_text else str(s.payload)  # type: ignore[union-attr]
    pattern = pat.payload if pat.is_text else str(pat.payload)  # type: ignore[union-attr]
    replacement = repl.payload if repl.is_text else str(repl.payload)  # type: ignore[union-attr]
    if pattern == "":
        return Value.text(text)  # SQLite: empty pattern → no change
    return Value.text(text.replace(pattern, replacement))


def _fn_instr(args: list[Value]) -> Value:
    """instr(haystack, needle) — 1-based position, 0 if not found."""
    h, n = args[0], args[1]
    if h.is_null or n.is_null:
        return Value.null()
    hay = h.payload if h.is_text else str(h.payload)  # type: ignore[union-attr]
    needle = n.payload if n.is_text else str(n.payload)  # type: ignore[union-attr]
    if needle == "":
        return Value.integer(1)  # SQLite: empty needle → 1
    pos = hay.find(needle)
    return Value.integer(pos + 1 if pos >= 0 else 0)


def _fn_quote(args: list[Value]) -> Value:
    """quote(v) — SQL literal representation."""
    v = args[0]
    if v.is_null:
        return Value.text("NULL")
    if v.is_integer:
        return Value.text(str(v.payload))
    if v.is_real:
        return Value.text("%.15g" % float(v.payload))  # type: ignore[arg-type]
    if v.is_text:
        # Single-quote-escape the string.
        s = v.payload.replace("'", "''")  # type: ignore[union-attr]
        return Value.text("'" + s + "'")
    if v.is_blob:
        return Value.text("x'" + v.payload.hex() + "'")  # type: ignore[union-attr]
    return Value.text("NULL")


def _fn_char(args: list[Value]) -> Value:
    """char(n1, n2, ...) — convert Unicode code points to a string."""
    chars: list[str] = []
    for v in args:
        if v.is_null:
            continue
        if v.is_integer:
            chars.append(chr(int(v.payload)))  # type: ignore[arg-type]
        else:
            try:
                chars.append(chr(int(str(v.payload))))
            except (ValueError, OverflowError):
                pass
    return Value.text("".join(chars))


def _fn_unicode(args: list[Value]) -> Value:
    """unicode(s) — code point of the first character."""
    v = args[0]
    if v.is_null:
        return Value.null()
    text = v.payload if v.is_text else str(v.payload)  # type: ignore[union-attr]
    if not text:
        return Value.null()
    return Value.integer(ord(text[0]))


# --- math functions ---

def _fn_abs(args: list[Value]) -> Value:
    v = args[0]
    if v.is_null:
        return Value.null()
    if v.is_integer:
        i = v.payload  # type: ignore[assignment]
        # SQLite: abs of i64 min (-2^63) overflows → returns 2^63 as REAL.
        if i == -(2**63):
            return Value.real(float(2**63))
        return Value.integer(abs(i))
    if v.is_real:
        return Value.real(abs(v.payload))  # type: ignore[arg-type]
    if v.is_text or v.is_blob:
        # SQLite coerces text to numeric; if not numeric, returns 0.
        try:
            return Value.integer(abs(int(str(v.payload))))
        except (ValueError, TypeError):
            try:
                return Value.real(abs(float(str(v.payload))))
            except (ValueError, TypeError):
                return Value.integer(0)
    return Value.null()


def _fn_round(args: list[Value]) -> Value:
    v = args[0]
    if v.is_null:
        return Value.null()
    digits = 0
    if len(args) > 1 and not args[1].is_null:
        digits = int(args[1].payload)  # type: ignore[assignment]
    # Convert to float.
    if v.is_integer:
        f = float(v.payload)  # type: ignore[arg-type]
    elif v.is_real:
        f = float(v.payload)  # type: ignore[arg-type]
    else:
        try:
            f = float(str(v.payload))
        except (ValueError, TypeError):
            return Value.real(0.0)
    # SQLite round uses C's round (round half away from zero, not bankers').
    factor = 10 ** digits
    rounded = _math.floor(abs(f) * factor + 0.5) / factor
    if f < 0:
        rounded = -rounded
    # If no digits and the result is integral, return as INTEGER (SQLite does this).
    if digits == 0 and rounded == int(rounded):
        return Value.integer(int(rounded))
    return Value.real(rounded)


def _fn_ceil(args: list[Value]) -> Value:
    v = args[0]
    if v.is_null:
        return Value.null()
    import math as _m
    f = _to_float_val(v)
    return Value.integer(int(_m.ceil(f)))


def _fn_floor(args: list[Value]) -> Value:
    v = args[0]
    if v.is_null:
        return Value.null()
    import math as _m
    f = _to_float_val(v)
    return Value.integer(int(_m.floor(f)))


def _fn_sign(args: list[Value]) -> Value:
    v = args[0]
    if v.is_null:
        return Value.null()
    f = _to_float_val(v)
    if f > 0:
        return Value.integer(1)
    if f < 0:
        return Value.integer(-1)
    return Value.integer(0)


def _fn_sqrt(args: list[Value]) -> Value:
    v = args[0]
    if v.is_null:
        return Value.null()
    import math as _m
    f = _to_float_val(v)
    if f < 0:
        return Value.null()
    return Value.real(_m.sqrt(f))


def _fn_pow(args: list[Value]) -> Value:
    base, exp = args[0], args[1]
    if base.is_null or exp.is_null:
        return Value.null()
    import math as _m
    return Value.real(_m.pow(_to_float_val(base), _to_float_val(exp)))


def _to_float_val(v: Value) -> float:
    """Convert a Value to float for math functions."""
    if v.is_integer:
        return float(v.payload)  # type: ignore[arg-type]
    if v.is_real:
        return float(v.payload)  # type: ignore[arg-type]
    try:
        return float(str(v.payload))
    except (ValueError, TypeError):
        return 0.0


# --- type functions ---

def _fn_typeof(args: list[Value]) -> Value:
    v = args[0]
    if v.is_null:
        return Value.text("null")
    if v.is_integer:
        return Value.text("integer")
    if v.is_real:
        return Value.text("real")
    if v.is_text:
        return Value.text("text")
    if v.is_blob:
        return Value.text("blob")
    return Value.text("null")


# --- NULL-handling functions ---

def _fn_coalesce(args: list[Value]) -> Value:
    for v in args:
        if not v.is_null:
            return v
    return Value.null()


def _fn_ifnull(args: list[Value]) -> Value:
    if args[0].is_null:
        return args[1]
    return args[0]


def _fn_nullif(args: list[Value]) -> Value:
    # NULLIF(a, b) = NULL if a == b (structural, same storage class), else a.
    if args[0] == args[1]:
        return Value.null()
    return args[0]


# --- min/max (scalar forms: return the min/max of the arguments) ---

def _fn_min(args: list[Value]) -> Value:
    from pyturso.types.compare import compare_values
    best: Value | None = None
    for v in args:
        if v.is_null:
            return Value.null()  # SQLite: min(NULL, ...) = NULL
        if best is None or compare_values(v, best) < 0:
            best = v
    return best if best is not None else Value.null()


def _fn_max(args: list[Value]) -> Value:
    from pyturso.types.compare import compare_values
    best: Value | None = None
    for v in args:
        if v.is_null:
            return Value.null()  # SQLite: max(NULL, ...) = NULL
        if best is None or compare_values(v, best) > 0:
            best = v
    return best if best is not None else Value.null()


# Register on import.
_register()