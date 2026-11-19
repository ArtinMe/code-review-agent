"""Check every finding against the code before showing it to anyone.

Models sometimes cite a line that doesn't exist, quote code that isn't there,
or point one or two lines away from the real problem. A finding survives only
if its quote can be found in the file:

1. Quote found on the cited lines -> kept as is.
2. Quote found within ``SEARCH_WINDOW`` lines -> kept, line numbers corrected.
3. Otherwise -> dropped as ungrounded.

In a diff, a finding must also touch at least one added line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Finding, RawFinding, ReviewInput, SourceFile

SEARCH_WINDOW = 3
MIN_QUOTE_CHARS = 3

_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    return _WS.sub(" ", text).strip()


@dataclass
class GroundingResult:
    finding: Finding | None
    reason: str  # "kept", "reanchored", "ungrounded", "out_of_scope"


def _span_text(file: SourceFile, start: int, end: int) -> str:
    by_number = file.line_map()
    return " ".join(by_number[n].text for n in range(start, end + 1) if n in by_number)


def _locate(file: SourceFile, quote: str, start: int, end: int) -> tuple[int, int] | None:
    """Find the quote, preferring the cited span, then nearby spans."""
    needle = normalize(quote)
    if len(needle) < MIN_QUOTE_CHARS:
        return None
    if needle in normalize(_span_text(file, start, end)):
        return start, end
    numbers = sorted(file.line_map())
    if not numbers:
        return None
    height = max(0, end - start)
    # try spans of the same height at increasing distance from the citation
    for distance in range(1, SEARCH_WINDOW + 1):
        for shift in (-distance, distance):
            s, e = start + shift, end + shift
            if s < numbers[0] or e > numbers[-1]:
                continue
            if needle in normalize(_span_text(file, s, e)):
                return s, e
    # a multi-line quote cited as one line: grow the span
    for extra in range(1, SEARCH_WINDOW + 1):
        s, e = max(numbers[0], start - extra), min(numbers[-1], start + height + extra)
        if needle in normalize(_span_text(file, s, e)):
            return s, e
    return None


def ground(raw: RawFinding, agent: str, review_input: ReviewInput) -> GroundingResult:
    file = next((f for f in review_input.files if f.path == raw.file), None)
    if file is None and len(review_input.files) == 1:
        file = review_input.files[0]  # models sometimes rename a pasted snippet's file
    if file is None:
        return GroundingResult(None, "ungrounded")

    start, end = sorted((raw.line_start, raw.line_end))
    located = _locate(file, raw.quote, start, end)
    if located is None:
        return GroundingResult(None, "ungrounded")
    new_start, new_end = located

    if review_input.kind == "diff":
        touched = set(range(new_start, new_end + 1))
        if not touched & file.changed_numbers:
            return GroundingResult(None, "out_of_scope")

    reanchored = (new_start, new_end) != (start, end)
    finding = Finding(
        file=file.path,
        line_start=new_start,
        line_end=new_end,
        severity=raw.severity,
        title=raw.title.strip(),
        explanation=raw.explanation.strip(),
        suggestion=raw.suggestion.strip(),
        confidence=min(1.0, max(0.0, raw.confidence)),
        agents=[agent],
        quote=raw.quote.strip(),
        reanchored=reanchored,
    )
    return GroundingResult(finding, "reanchored" if reanchored else "kept")
