"""Merge, filter, rank and score findings, without asking a model.

The first version used a fifth model call to "synthesize" the agents'
reports. That made the final report impossible to test and occasionally
dropped real issues. This step is plain code: same input, same output.
"""

from __future__ import annotations

import re

from .models import SEVERITY_WEIGHT, Finding

MIN_CONFIDENCE = 0.5
TITLE_SIMILARITY = 0.25
EXPLANATION_SIMILARITY = 0.25
LINE_SLACK = 1

# Points subtracted from 10 per finding, scaled by confidence.
SCORE_PENALTY = {"critical": 3.0, "major": 1.5, "minor": 0.5}

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "of", "in", "on", "to", "for", "and", "or", "is", "not", "with"}


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def similarity(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _overlaps(a: Finding, b: Finding) -> bool:
    return (
        a.file == b.file
        and a.line_start <= b.line_end + LINE_SLACK
        and b.line_start <= a.line_end + LINE_SLACK
    )


def _same_issue(a: Finding, b: Finding) -> bool:
    """Two findings describe one issue if they overlap and say the same thing.

    Titles are compared, not explanations: explanations share generic words
    ("input", "value", "function") and made distinct neighbouring issues look
    alike. Explanations only count when both findings cite exactly the same lines.
    """
    if not _overlaps(a, b):
        return False
    if similarity(a.title, b.title) >= TITLE_SIMILARITY:
        return True
    same_span = (a.line_start, a.line_end) == (b.line_start, b.line_end)
    return same_span and similarity(a.explanation, b.explanation) >= EXPLANATION_SIMILARITY


def _combine(a: Finding, b: Finding) -> Finding:
    """Keep the stronger report; agreement between agents raises confidence."""
    primary, other = (a, b) if a.priority >= b.priority else (b, a)
    severity = max(a.severity, b.severity, key=lambda s: SEVERITY_WEIGHT[s])
    # independent agreement: P(at least one is right)
    confidence = 1 - (1 - a.confidence) * (1 - b.confidence)
    return Finding(
        file=primary.file,
        line_start=min(a.line_start, b.line_start),
        line_end=max(a.line_end, b.line_end),
        severity=severity,
        title=primary.title,
        explanation=primary.explanation,
        suggestion=primary.suggestion or other.suggestion,
        confidence=confidence,
        agents=sorted(set(a.agents) | set(b.agents)),
        quote=primary.quote,
        reanchored=primary.reanchored,
    )


def merge(findings: list[Finding]) -> tuple[list[Finding], int]:
    """Collapse duplicates. Returns the merged list and how many were merged away."""
    merged: list[Finding] = []
    folded = 0
    for finding in sorted(findings, key=lambda f: -f.priority):
        for i, existing in enumerate(merged):
            if _same_issue(existing, finding):
                merged[i] = _combine(existing, finding)
                folded += 1
                break
        else:
            merged.append(finding)
    return merged, folded


def rank(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (-f.priority, f.file, f.line_start))


def score(findings: list[Finding]) -> float:
    penalty = sum(SCORE_PENALTY[f.severity] * f.confidence for f in findings)
    return round(max(0.0, 10.0 - penalty), 1)
