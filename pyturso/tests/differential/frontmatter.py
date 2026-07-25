"""frontmatter — parse ``--`` directive headers atop a corpus case.

Ports: the corpus front-matter format in tests/differential/corpus/HOWTO.md
(``-- setup: fixture=<script>`` / ``-- expect-error: <ErrorClass>``) and the
README example with trailing human notes.
Phase: 0
Status: IMPLEMENTED.

A corpus case is a plain ``.sql`` script whose leading ``--`` comment lines may
carry metadata directives. This module parses only that header block and returns
the rest of the file as the SQL body, so the harness can build the fixture and
set expectations before running the engines.

Directive grammar (one per line, at the very top of the file, contiguous)::

    -- setup: fixture=<script-name>[  (any human note)]
    -- expect-error: <ErrorClass>[  (any human note)]

  - The directive block is the maximal run of ``-- <key>: <rest>`` lines at the
    top. The first line that is not such a directive (a bare comment, a blank
    line, or SQL) ends the block; it and everything after is the SQL body.
  - Trailing ``( ... )`` parentheticals and surrounding whitespace are stripped
    from values, so human notes (as in the README example) do not pollute them.
  - Unknown directive keys are ignored (forward-compatible), not an error — the
    corpus is the controlled surface and a new directive landing before its
    parser is wired should not break older harness runs.

The two known directives:
  - ``setup`` → ``fixture=<name>``. The name is resolved to a path by the
    harness (it knows the corpus + fixture-cache directories; ``tools.mkdb``
    builds the binary). No path resolution here — this module is pure text.
  - ``expect-error`` → a comparison-class name from ``pyturso.errors``
    (``COMPARISON_CLASSES``). Validation against that vocabulary is the
    reporter's job; parsing returns the raw string so a typo surfaces as a
    harness error, not a silent parse miss.
"""

from __future__ import annotations

import re

__all__ = ["FrontMatter", "parse_frontmatter"]

#: A directive line: ``--`` <key> ``:`` <rest>. Key is ``[a-z][a-z-]*`` (the
#: two known keys ``setup`` and ``expect-error``, plus room for more).
_DIRECTIVE_RE: re.Pattern[str] = re.compile(
    r"^--\s*([a-z][a-z-]*)\s*:\s*(.*?)\s*$"
)

#: Trailing parenthetical human note, e.g. ``fixture=people.sql  (built by …)``.
#: Stripped from the value so it never reaches the harness.
_TRAILING_NOTE_RE: re.Pattern[str] = re.compile(r"\s*\([^)]*\)\s*$")

#: The known directive keys.
_KEY_SETUP: str = "setup"
_KEY_EXPECT_ERROR: str = "expect-error"


class FrontMatter:
    """Parsed front-matter of a corpus case.

    Both fields are ``None`` when the directive is absent (the common case for
    a case that needs no fixture and expects no error).
    """

    __slots__ = ("fixture", "expect_error")

    def __init__(
        self,
        *,
        fixture: str | None = None,
        expect_error: str | None = None,
    ) -> None:
        self.fixture: str | None = fixture
        self.expect_error: str | None = expect_error

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"FrontMatter(fixture={self.fixture!r}, "
            f"expect_error={self.expect_error!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FrontMatter):
            return NotImplemented
        return (
            self.fixture == other.fixture
            and self.expect_error == other.expect_error
        )


def parse_frontmatter(sql_text: str) -> tuple[FrontMatter, str]:
    """Parse the leading front-matter block of ``sql_text``.

    Returns ``(frontmatter, sql_body)`` where ``sql_body`` is the file contents
    from the first non-directive line onward (preserving newlines so statement
    splitting sees the original text). A file with no directives yields the
    default :class:`FrontMatter` and the whole text as the body.
    """
    # Normalize CRLF so the directive match and body split are line-ending
    # agnostic; the body keeps '\n' uniformly.
    text = sql_text.replace("\r\n", "\n").replace("\r", "\n")

    fixture: str | None = None
    expect_error: str | None = None
    body_start = 0

    for line in text.split("\n"):
        m = _DIRECTIVE_RE.match(line)
        if m is None:
            break  # first non-directive line ends the header block
        key, raw_value = m.group(1), m.group(2)
        value = _TRAILING_NOTE_RE.sub("", raw_value).strip()
        if key == _KEY_SETUP:
            fixture = _parse_fixture_value(value)
        elif key == _KEY_EXPECT_ERROR:
            expect_error = value or None
        # Unknown keys: ignored (forward-compatible).

        # Advance body_start past this line + its newline.
        body_start += len(line) + 1

    body = text[body_start:]
    return FrontMatter(fixture=fixture, expect_error=expect_error), body


def _parse_fixture_value(value: str) -> str | None:
    """Extract the ``<name>`` from ``fixture=<name>``.

    Returns ``None`` if the value is empty or not in the ``fixture=`` form;
    a malformed setup directive is ignored (the harness will then run with no
    fixture, which is a detectable harness error rather than a parse crash).
    """
    if not value.startswith("fixture="):
        return None
    name = value[len("fixture=") :].strip()
    return name or None
