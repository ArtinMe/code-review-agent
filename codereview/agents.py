"""The specialist reviewers.

Each agent gets the same numbered code and a narrow brief. Keeping briefs
narrow makes agents disagree less about scope and makes it possible to
measure each one separately in the evaluation harness.
"""

from __future__ import annotations

from dataclasses import dataclass

# Bump when any prompt changes, so cached answers from older prompts aren't reused.
PROMPT_VERSION = "2"

COMMON_RULES = """
You are one reviewer on a code review panel. Report only problems inside your
own area; other reviewers cover the rest.

Rules:
- Cite real line numbers from the input. Never invent a line.
- "quote" must be the exact code from the cited line(s), copied character for
  character (leading spaces may be omitted).
- If the input is a diff, only report problems on lines marked with "+".
  Unmarked lines are context.
- Report a problem only if you can explain how it causes a concrete failure,
  vulnerability or measurable cost. Do not report style preferences, missing
  comments, or speculative issues.
- Severity: "critical" = exploitable or causes wrong results/crashes in normal
  use; "major" = real bug or risk under realistic conditions; "minor" = small
  but real issue.
- confidence is your probability (0 to 1) that a senior engineer would agree
  this is a real problem.
- Clean code is common. If there is nothing in your area, return an empty
  findings list. An empty list is a good answer.
"""


@dataclass(frozen=True)
class Agent:
    name: str
    label: str
    brief: str

    def system_prompt(self) -> str:
        return (
            f"Your area: {self.label}.\n{self.brief.strip()}\n{COMMON_RULES}\n"
            f"(prompt version {PROMPT_VERSION})"
        )


AGENTS: tuple[Agent, ...] = (
    Agent(
        name="security",
        label="Security",
        brief="""
You review code for security vulnerabilities: injection (SQL, command, path
traversal, template), cross-site scripting, hardcoded secrets or credentials,
unsafe deserialization, missing authentication or authorization checks,
insecure randomness for security purposes, and sensitive data exposure.
""",
    ),
    Agent(
        name="correctness",
        label="Correctness",
        brief="""
You review code for logic errors that produce wrong results or crashes:
off-by-one errors, wrong conditions or operators, null/None dereferences,
unhandled error paths, misuse of language semantics (mutable default
arguments, identity vs equality, async functions not awaited), race
conditions on shared state, and resource leaks.
""",
    ),
    Agent(
        name="performance",
        label="Performance",
        brief="""
You review code for performance problems with a real cost at realistic input
sizes: accidentally quadratic loops, repeated work inside loops, N+1 database
or network calls, loading whole datasets into memory unnecessarily, and
blocking calls on hot paths. Ignore micro-optimizations.
""",
    ),
    Agent(
        name="maintainability",
        label="Maintainability",
        brief="""
You review code for maintainability problems that are likely to cause future
bugs: errors swallowed silently (bare except, empty catch), duplicated logic
that must be kept in sync, misleading names that contradict behaviour, and
dead code that hides intent. Ignore formatting and naming taste.
""",
    ),
)

AGENTS_BY_NAME = {agent.name: agent for agent in AGENTS}


def build_prompt(rendered_code: str, kind: str, title: str = "") -> str:
    header = "Review this pull request diff." if kind == "diff" else "Review this code."
    if title:
        header += f" Title: {title!r}."
    return f"{header}\n\n{rendered_code}\n"
