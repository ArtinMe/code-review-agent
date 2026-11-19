from __future__ import annotations

import pytest

from codereview.models import AgentOutput, RawFinding


class FakeLLM:
    """Returns canned answers per agent, keyed by a word in the agent's system prompt."""

    model = "fake-model"

    def __init__(
        self, answers: dict[str, list[RawFinding]] | None = None, failing: set[str] | None = None
    ) -> None:
        self.answers = answers or {}
        self.failing = failing or set()
        self.calls: list[str] = []
        self.queued: list = []  # answers for non-review calls, e.g. FixOutput
        self.prompts: list[str] = []

    def _agent(self, system: str) -> str:
        first_line = system.split("\n", 1)[0].lower()  # "Your area: Security."
        for name in ("security", "correctness", "performance", "maintainability"):
            if name in first_line:
                return name
        return "unknown"

    def generate(self, system, prompt, schema):
        """Structured calls other than reviews (the fixer): replay queued answers in order."""
        if schema is AgentOutput:
            return self.review(system, prompt)
        self.calls.append(schema.__name__)
        self.prompts.append(prompt)
        return self.queued.pop(0)

    def review(self, system: str, prompt: str) -> AgentOutput:
        agent = self._agent(system)
        self.calls.append(agent)
        if agent in self.failing:
            raise RuntimeError(f"{agent} exploded")
        return AgentOutput(findings=self.answers.get(agent, []))


def raw(
    line: int,
    quote: str,
    *,
    file: str = "snippet.py",
    severity: str = "major",
    title: str = "Problem",
    explanation: str = "It breaks.",
    confidence: float = 0.9,
    line_end: int | None = None,
) -> RawFinding:
    return RawFinding(
        file=file,
        line_start=line,
        line_end=line_end or line,
        quote=quote,
        severity=severity,
        title=title,
        explanation=explanation,
        suggestion="Fix it.",
        confidence=confidence,
    )


@pytest.fixture
def fake_llm():
    return FakeLLM
