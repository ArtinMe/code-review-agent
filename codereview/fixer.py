"""Turn a verified review into a corrected file.

The model is asked to fix exactly the reported findings and nothing else.
Its answer is then checked by code, not trusted:

- it must not be empty or identical to the input;
- it must not contain placeholder lines ("...", "# rest unchanged") that the
  input didn't have, which would mean a fragment instead of a whole file;
- Python output must parse (``ast.parse``); a syntax error gets one retry
  with the error shown to the model, then the fix is refused.

A file that parses is not proof the fix is right, so the result reports
precisely what was checked.
"""

from __future__ import annotations

import ast
import difflib
import io
import re
import tokenize
from dataclasses import dataclass

from pydantic import BaseModel, Field

from .llm import LLMClient
from .models import Finding

MAX_FINDINGS = 20

SYSTEM = """
You fix code after a code review. You receive a file and a list of verified
problems in it.

Rules:
- Fix every listed problem. Change nothing else: keep names, structure,
  formatting, comments and public behaviour that the problems don't require
  changing.
- Never invent names the file doesn't contain: no new column, table, field,
  function or variable names you would have to guess. If a fix needs one,
  choose a fix that doesn't (for example, keep reading a value by its
  existing position) and say what the reader should confirm. Suggested fixes
  from reviewers may contain such guessed names; don't copy them.
- Return the complete file, not a fragment, with no placeholders like "...".
- For each problem, say in one sentence what you changed. If a problem can't
  be fixed inside this file, say so instead of guessing.
"""


class Change(BaseModel):
    finding: str = Field(description="Title of the problem this change addresses.")
    change: str = Field(description="One sentence: what was changed and why.")


class FixOutput(BaseModel):
    fixed_code: str = Field(description="The complete corrected file.")
    changes: list[Change]


class FixError(RuntimeError):
    pass


@dataclass
class FixResult:
    fixed_code: str
    changes: list[Change]
    diff: list[dict]
    checks: list[str]
    to_confirm: list[str]

    def to_dict(self) -> dict:
        return {
            "fixed_code": self.fixed_code,
            "changes": [c.model_dump() for c in self.changes],
            "diff": self.diff,
            "checks": self.checks,
            "to_confirm": self.to_confirm,
        }


def line_diff(before: str, after: str) -> list[dict]:
    """Line-level diff as {op, old, new, text}; op is ' ', '-' or '+'."""
    a, b = before.splitlines(), after.splitlines()
    out: list[dict] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            out += [
                {"op": " ", "old": i1 + k + 1, "new": j1 + k + 1, "text": a[i1 + k]}
                for k in range(i2 - i1)
            ]
            continue
        out += [{"op": "-", "old": i + 1, "new": None, "text": a[i]} for i in range(i1, i2)]
        out += [{"op": "+", "old": None, "new": j + 1, "text": b[j]} for j in range(j1, j2)]
    return out


def _prompt(code: str, path: str, findings: list[Finding], previous_error: str | None) -> str:
    problems = "\n".join(
        f"{i}. [{f.severity}] {f.title} (lines {f.line_start}-{f.line_end}): {f.explanation}"
        + (f" Suggested fix: {f.suggestion}" if f.suggestion else "")
        for i, f in enumerate(findings, 1)
    )
    text = f"FILE: {path}\n```\n{code}\n```\n\nPROBLEMS:\n{problems}\n"
    if previous_error:
        text += (
            f"\nYour previous answer was rejected: {previous_error}. Return the full, valid file.\n"
        )
    return text


PLACEHOLDERS = ("...", "# ...", "// ...", "# rest unchanged", "# rest of the code")


def _placeholders(code: str) -> set[str]:
    return {line.strip() for line in code.splitlines() if line.strip().lower() in PLACEHOLDERS}


_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def new_names_in_strings(before: str, after: str) -> list[str]:
    """Names inside string literals of the fix (SQL columns, keys, paths) that the
    original never mentions. Those are guesses about things outside the file,
    so they're shown to the reader instead of trusted. Uppercase words are taken
    as SQL keywords. Python only; other languages return no list."""
    known = set(_WORD.findall(before))
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(after).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []
    found: list[str] = []
    for tok in tokens:
        if tok.type != tokenize.STRING:
            continue
        for word in _WORD.findall(tok.string):
            if word in known or word.isupper() or len(word) < 3 or word in found:
                continue
            if word.lower() in {"rb", "br", "fr", "rf"}:
                continue
            found.append(word)
    return found


def _syntax_error(code: str, path: str) -> str | None:
    if not path.endswith(".py"):
        return None
    try:
        ast.parse(code)
    except SyntaxError as e:
        return f"line {e.lineno}: {e.msg}"
    return None


def fix(code: str, path: str, findings: list[Finding], client: LLMClient) -> FixResult:
    if not findings:
        raise FixError("There's nothing to fix: the review found no problems.")
    findings = findings[:MAX_FINDINGS]

    error: str | None = None
    for _attempt in range(2):
        output = client.generate(SYSTEM, _prompt(code, path, findings, error), FixOutput)
        fixed = output.fixed_code.replace("\r\n", "\n").strip("\n") + "\n"
        if not fixed.strip():
            raise FixError("The model returned an empty file.")
        if _placeholders(fixed) - _placeholders(code):
            error = "it contains placeholder lines like '...' instead of the whole file"
            continue
        error = _syntax_error(fixed, path)
        if error is None:
            break
    else:
        raise FixError(f"The fixed file failed its checks ({error}), so it isn't shown.")

    if fixed.strip() == code.strip():
        raise FixError("The model returned the file unchanged.")

    checks = ["Whole file returned, with no placeholder lines."]
    if path.endswith(".py"):
        checks.append("Parses as valid Python.")
    # Models echo the prompt's "[severity] Title (lines a-b)" format; label each
    # change with the exact finding title it refers to instead.
    for change in output.changes:
        match = next((f.title for f in findings if f.title.lower() in change.finding.lower()), None)
        if match:
            change.finding = match
    guesses = new_names_in_strings(code, fixed) if path.endswith(".py") else []
    return FixResult(fixed, output.changes, line_diff(code, fixed), checks, guesses)
