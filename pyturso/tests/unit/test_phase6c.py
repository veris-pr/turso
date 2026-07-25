"""Unit tests for Phase 6c: datetime, printf, AND/OR, CASE, BETWEEN, IN."""

from __future__ import annotations
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="operator"
# mypy: disable-error-code="unused-ignore"

import pytest

from pyturso.functions.registry import call_function
from pyturso.types.value import Value


# --- datetime ---
class TestDatetime:
    def test_date_from_string(self) -> None:
        assert call_function("date", [Value.text("2023-07-15")]) == Value.text("2023-07-15")

    def test_date_from_string_with_time(self) -> None:
        assert call_function("date", [Value.text("2023-07-15 12:30:45")]) == Value.text("2023-07-15")

    def test_time_from_string(self) -> None:
        assert call_function("time", [Value.text("2023-07-15 12:30:45")]) == Value.text("12:30:45")

    def test_datetime_from_string(self) -> None:
        assert call_function("datetime", [Value.text("2023-07-15 12:30:45")]) == Value.text("2023-07-15 12:30:45")

    def test_date_with_modifier_days(self) -> None:
        result = call_function("date", [Value.text("2023-07-15"), Value.text("+1 day")])
        assert result == Value.text("2023-07-16")

    def test_date_with_modifier_negative_days(self) -> None:
        result = call_function("date", [Value.text("2023-07-15"), Value.text("-1 day")])
        assert result == Value.text("2023-07-14")

    def test_date_with_modifier_start_of_month(self) -> None:
        result = call_function("date", [Value.text("2023-07-15"), Value.text("start of month")])
        assert result == Value.text("2023-07-01")

    def test_julianday(self) -> None:
        result = call_function("julianday", [Value.text("1970-01-01")])
        assert result.is_real
        # Julian Day for 1970-01-01 00:00:00 UTC = 2440587.5
        assert abs(result.payload - 2440587.5) < 1.0  # type: ignore[union-attr]

    def test_unixepoch(self) -> None:
        result = call_function("unixepoch", [Value.text("1970-01-01")])
        assert result == Value.integer(0)

    def test_strftime(self) -> None:
        result = call_function("strftime", [Value.text("%Y"), Value.text("2023-07-15")])
        assert result == Value.text("2023")

    def test_strftime_day(self) -> None:
        result = call_function("strftime", [Value.text("%d"), Value.text("2023-07-15")])
        assert result == Value.text("15")

    def test_date_null(self) -> None:
        assert call_function("date", [Value.null()]) == Value.null()

    def test_date_invalid(self) -> None:
        assert call_function("date", [Value.text("not a date")]) == Value.null()


# --- printf ---
class TestPrintf:
    def test_basic_d(self) -> None:
        assert call_function("printf", [Value.text("%d"), Value.integer(42)]) == Value.text("42")

    def test_basic_s(self) -> None:
        assert call_function("printf", [Value.text("%s"), Value.text("hello")]) == Value.text("hello")

    def test_basic_f(self) -> None:
        result = call_function("printf", [Value.text("%.2f"), Value.real(3.14159)])
        assert result == Value.text("3.14")

    def test_width(self) -> None:
        result = call_function("printf", [Value.text("%5d"), Value.integer(42)])
        assert result == Value.text("   42")

    def test_multiple_args(self) -> None:
        result = call_function("printf", [
            Value.text("%s is %d"), Value.text("age"), Value.integer(30),
        ])
        assert result == Value.text("age is 30")

    def test_percent(self) -> None:
        assert call_function("printf", [Value.text("100%%")]) == Value.text("100%")

    def test_format_alias(self) -> None:
        assert call_function("format", [Value.text("%d"), Value.integer(42)]) == Value.text("42")

    def test_hex(self) -> None:
        result = call_function("printf", [Value.text("%x"), Value.integer(255)])
        assert result == Value.text("ff")

    def test_null_arg(self) -> None:
        result = call_function("printf", [Value.text("%s"), Value.null()])
        assert result == Value.text("")

    def test_no_args(self) -> None:
        assert call_function("printf", []) == Value.null()