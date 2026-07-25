"""Unit tests for tests.differential.frontmatter — corpus case header parsing.

Verified against: tests/differential/corpus/HOWTO.md directive format and the
README example with trailing human notes.
"""

from __future__ import annotations

from tests.differential.frontmatter import FrontMatter, parse_frontmatter


# --- no front-matter (the common case) ------------------------------------
class TestNoFrontMatter:
    def test_plain_sql_passes_through(self) -> None:
        sql = "SELECT 1;\nSELECT 2;\n"
        fm, body = parse_frontmatter(sql)
        assert fm == FrontMatter()
        assert body == sql

    def test_empty_file(self) -> None:
        fm, body = parse_frontmatter("")
        assert fm == FrontMatter()
        assert body == ""

    def test_bare_comment_is_not_a_directive(self) -> None:
        # A `--` line with no `key:` form ends the header → it's body.
        fm, body = parse_frontmatter("-- just a note\nSELECT 1;")
        assert fm == FrontMatter()
        assert body == "-- just a note\nSELECT 1;"


# --- setup: fixture=... ---------------------------------------------------
class TestSetup:
    def test_fixture_directive(self) -> None:
        fm, body = parse_frontmatter("-- setup: fixture=people.sql\nSELECT 1;")
        assert fm.fixture == "people.sql"
        assert body == "SELECT 1;"

    def test_fixture_with_trailing_human_note_stripped(self) -> None:
        # The README example carries a trailing (built by …) note.
        fm, _ = parse_frontmatter(
            "-- setup: fixture=people.sql        (built by tools/mkdb.py)\n"
            "SELECT 1;"
        )
        assert fm.fixture == "people.sql"

    def test_fixture_with_subdir(self) -> None:
        fm, _ = parse_frontmatter("-- setup: fixture=phase1/people.sql\nSELECT 1;")
        assert fm.fixture == "phase1/people.sql"


# --- expect-error ---------------------------------------------------------
class TestExpectError:
    def test_expect_error_directive(self) -> None:
        fm, body = parse_frontmatter(
            "-- expect-error: OperationalError\nSELECT bad;"
        )
        assert fm.expect_error == "OperationalError"
        assert body == "SELECT bad;"

    def test_expect_error_with_trailing_note_stripped(self) -> None:
        fm, _ = parse_frontmatter(
            "-- expect-error: IntegrityError   (error-class case)\nSELECT 1;"
        )
        assert fm.expect_error == "IntegrityError"


# --- combined header + body round-trip ------------------------------------
class TestCombined:
    def test_both_directives_then_body(self) -> None:
        # Mirrors the README example shape.
        sql = (
            "-- setup: fixture=people.sql\n"
            "-- expect-error: OperationalError\n"
            "SELECT name FROM people WHERE age >= 30;\n"
        )
        fm, body = parse_frontmatter(sql)
        assert fm.fixture == "people.sql"
        assert fm.expect_error == "OperationalError"
        assert body == "SELECT name FROM people WHERE age >= 30;\n"

    def test_directives_separated_by_blank_line(self) -> None:
        # A blank line is not a directive → ends the header. So the blank line
        # and everything after is body. (Header is contiguous directives.)
        fm, body = parse_frontmatter(
            "-- setup: fixture=p.sql\n"
            "\n"
            "-- expect-error: OperationalError\n"
            "SELECT 1;"
        )
        assert fm.fixture == "p.sql"
        assert fm.expect_error is None  # the blank line ended the header
        assert body == "\n-- expect-error: OperationalError\nSELECT 1;"


# --- robustness -----------------------------------------------------------
class TestRobustness:
    def test_unknown_directive_ignored(self) -> None:
        # Forward-compat: a new directive key doesn't break parsing.
        fm, body = parse_frontmatter(
            "-- setup: fixture=p.sql\n-- todo: later\nSELECT 1;"
        )
        assert fm.fixture == "p.sql"
        assert body == "SELECT 1;"

    def test_crlf_line_endings(self) -> None:
        fm, body = parse_frontmatter("-- setup: fixture=p.sql\r\nSELECT 1;\r\n")
        assert fm.fixture == "p.sql"
        assert body == "SELECT 1;\n"

    def test_malformed_setup_ignored(self) -> None:
        # `setup:` without `fixture=` → ignored (harness surfaces the gap).
        fm, _ = parse_frontmatter("-- setup: notafixture\nSELECT 1;")
        assert fm.fixture is None

    def test_empty_setup_value(self) -> None:
        fm, _ = parse_frontmatter("-- setup: fixture=\nSELECT 1;")
        assert fm.fixture is None
