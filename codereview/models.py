"""Data shapes shared across the pipeline.

``AgentOutput`` / ``RawFinding`` are what a model is asked to return (and are
used as the structured-output schema). Everything else is produced by our own
code after the model has answered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "major", "minor"]

SEVERITY_WEIGHT: dict[str, float] = {"critical": 3.0, "major": 2.0, "minor": 1.0}


class RawFinding(BaseModel):
    """One issue as reported by a specialist agent."""

    file: str = Field(description="Path of the file, exactly as shown in the input.")
    line_start: int = Field(description="First line number of the problem, from the input.")
    line_end: int = Field(
        description="Last line number of the problem (same as start if one line)."
    )
    quote: str = Field(description="The exact code on the cited line(s), copied verbatim.")
    severity: Severity
    title: str = Field(description="Short name of the issue, under 10 words.")
    explanation: str = Field(description="Why this is a problem, in 1-3 sentences.")
    suggestion: str = Field(description="Concrete fix: replacement code or a precise instruction.")
    confidence: float = Field(description="Probability from 0 to 1 that this is a real problem.")


class AgentOutput(BaseModel):
    findings: list[RawFinding]


# ---------------------------------------------------------------------------
# Input


@dataclass
class SourceLine:
    number: int  # line number in the new version of the file
    text: str
    changed: bool  # True for lines added/modified by the change under review


@dataclass
class SourceFile:
    path: str
    lines: list[SourceLine]
    language: str = "text"

    def line_map(self) -> dict[int, SourceLine]:
        return {line.number: line for line in self.lines}

    @property
    def changed_numbers(self) -> set[int]:
        return {line.number for line in self.lines if line.changed}


@dataclass
class ReviewInput:
    files: list[SourceFile]
    kind: Literal["snippet", "diff"] = "snippet"
    title: str = ""


# ---------------------------------------------------------------------------
# Output


@dataclass
class Finding:
    file: str
    line_start: int
    line_end: int
    severity: str
    title: str
    explanation: str
    suggestion: str
    confidence: float
    agents: list[str]
    quote: str = ""
    reanchored: bool = False

    @property
    def priority(self) -> float:
        return SEVERITY_WEIGHT[self.severity] * self.confidence

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "severity": self.severity,
            "title": self.title,
            "explanation": self.explanation,
            "suggestion": self.suggestion,
            "confidence": round(self.confidence, 3),
            "agents": self.agents,
            "quote": self.quote,
            "reanchored": self.reanchored,
        }


@dataclass
class AgentRun:
    agent: str
    findings_returned: int = 0
    seconds: float = 0.0
    error: str | None = None
    cached: bool = False


@dataclass
class GroundingStats:
    kept: int = 0
    reanchored: int = 0
    dropped_ungrounded: int = 0
    dropped_out_of_scope: int = 0
    dropped_low_confidence: int = 0
    merged_duplicates: int = 0


@dataclass
class Review:
    findings: list[Finding]
    score: float
    agents: list[AgentRun]
    stats: GroundingStats
    files_reviewed: int
    lines_reviewed: int
    seconds: float
    dropped: list[dict] = field(default_factory=list)

    @property
    def partial(self) -> bool:
        return any(run.error for run in self.agents)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "partial": self.partial,
            "files_reviewed": self.files_reviewed,
            "lines_reviewed": self.lines_reviewed,
            "seconds": round(self.seconds, 2),
            "findings": [f.to_dict() for f in self.findings],
            "agents": [
                {
                    "agent": run.agent,
                    "findings_returned": run.findings_returned,
                    "seconds": round(run.seconds, 2),
                    "error": run.error,
                    "cached": run.cached,
                }
                for run in self.agents
            ],
            "stats": vars(self.stats),
            "dropped": self.dropped,
        }
