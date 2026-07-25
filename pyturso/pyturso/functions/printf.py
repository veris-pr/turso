"""printf — printf/format subset.

Ports: core/functions/printf.rs.
Phase: 6
Status: IMPLEMENTED (subset: %d, %s, %f, %x, %%, width/precision).

SQLite's printf uses C-style format specifiers. This implementation covers
the common subset: ``%d`` (integer), ``%s`` (string), ``%f`` (float),
``%x`` (hex), ``%%`` (literal percent), with optional width and precision.
"""

from __future__ import annotations
# mypy: disable-error-code="arg-type"
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="operator"
# mypy: disable-error-code="index"
# mypy: disable-error-code="union-attr"

import re

from pyturso.types.value import Value

from .registry import registry

__all__ = ["_register_printf"]


def _register_printf() -> None:
    registry.register("printf", -1, _fn_printf)
    registry.register("format", -1, _fn_printf)  # alias


def _fn_printf(args: list[Value]) -> Value:
    if not args:
        return Value.null()
    fmt_v = args[0]
    if fmt_v.is_null:
        return Value.null()
    fmt = fmt_v.payload if fmt_v.is_text else str(fmt_v.payload)  # type: ignore[union-attr]
    rest = args[1:]

    result: list[str] = []
    i = 0
    arg_idx = 0
    n = len(fmt)
    while i < n:
        ch = fmt[i]
        if ch == "%":
            i += 1
            if i >= n:
                result.append("%")
                break
            # Parse flags/width/precision.
            spec_start = i
            # Flags
            while i < n and fmt[i] in "-+0 #":
                i += 1
            # Width
            while i < n and fmt[i].isdigit():
                i += 1
            # Precision
            if i < n and fmt[i] == ".":
                i += 1
                while i < n and fmt[i].isdigit():
                    i += 1
            # Conversion specifier
            if i >= n:
                result.append(fmt[spec_start:])
                break
            conv = fmt[i]
            i += 1
            spec = "%" + fmt[spec_start:i]

            if conv == "%":
                result.append("%")
            elif conv in ("d", "i"):
                if arg_idx < len(rest):
                    v = rest[arg_idx]
                    arg_idx += 1
                    if v.is_null:
                        result.append("")
                    else:
                        try:
                            result.append(spec % int(v.payload))  # type: ignore[arg-type]
                        except (ValueError, TypeError):
                            result.append(spec % 0)
            elif conv == "s":
                if arg_idx < len(rest):
                    v = rest[arg_idx]
                    arg_idx += 1
                    if v.is_null:
                        result.append("")
                    else:
                        s = v.payload if v.is_text else str(v.payload)  # type: ignore[union-attr]
                        result.append(spec % s)
            elif conv == "f" or conv == "e" or conv == "g":
                if arg_idx < len(rest):
                    v = rest[arg_idx]
                    arg_idx += 1
                    if v.is_null:
                        result.append("")
                    else:
                        try:
                            result.append(spec % float(v.payload))  # type: ignore[arg-type]
                        except (ValueError, TypeError):
                            result.append(spec % 0.0)
            elif conv in ("x", "X", "o"):
                if arg_idx < len(rest):
                    v = rest[arg_idx]
                    arg_idx += 1
                    if v.is_null:
                        result.append("")
                    else:
                        try:
                            result.append(spec % int(v.payload))  # type: ignore[arg-type]
                        except (ValueError, TypeError):
                            result.append(spec % 0)
            elif conv == "c":
                if arg_idx < len(rest):
                    v = rest[arg_idx]
                    arg_idx += 1
                    if v.is_null:
                        result.append("")
                    else:
                        try:
                            result.append(chr(int(v.payload)))  # type: ignore[arg-type]
                        except (ValueError, TypeError):
                            pass
            else:
                # Unknown specifier — pass through.
                result.append(spec)
        else:
            result.append(ch)
            i += 1

    return Value.text("".join(result))


# Register on import.
_register_printf()