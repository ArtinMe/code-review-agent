"""Turn pasted code or a unified diff into ``SourceFile`` objects."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from .models import ReviewInput, SourceFile, SourceLine

LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".sql": "sql",
    ".kt": "kotlin",
    ".swift": "swift",
}

# Files that are generated or not worth an LLM's attention.
SKIP_PATTERNS = (
    re.compile(
        r"(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|poetry\.lock|uv\.lock|Cargo\.lock)$"
    ),
    re.compile(r"\.(min\.js|map|lock|svg|png|jpe?g|gif|ico|pdf|woff2?|ttf)$"),
    re.compile(r"(^|/)(dist|build|vendor|node_modules)/"),
)

HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class DiffError(ValueError):
    pass


def language_for(path: str) -> str:
    return LANGUAGES.get(PurePosixPath(path).suffix.lower(), "text")


def should_skip(path: str) -> bool:
    return any(p.search(path) for p in SKIP_PATTERNS)


def from_snippet(code: str, path: str = "snippet.py") -> ReviewInput:
    """A pasted snippet: every line is in scope."""
    text = code.replace("\r\n", "\n").rstrip("\n")
    if not text.strip():
        raise DiffError("There is no code to review.")
    lines = [
        SourceLine(number=i, text=line, changed=True)
        for i, line in enumerate(text.split("\n"), start=1)
    ]
    return ReviewInput(files=[SourceFile(path, lines, language_for(path))], kind="snippet")


def from_diff(diff_text: str, title: str = "") -> ReviewInput:
    """Parse a unified diff (as produced by ``git diff`` or GitHub).

    Only the new side is kept: added lines are in scope, context lines are
    included so the model can see what surrounds a change. Deleted files,
    binary files and generated files are skipped.
    """
    files: list[SourceFile] = []
    current: SourceFile | None = None
    new_line = 0
    in_hunk = False

    def finish() -> None:
        if current is not None and current.lines and not should_skip(current.path):
            files.append(current)

    for raw in diff_text.replace("\r\n", "\n").split("\n"):
        if raw.startswith("diff --git "):
            finish()
            current, in_hunk = None, False
            continue
        if raw.startswith("+++ "):
            target = raw[4:].strip()
            if target == "/dev/null":
                current = None  # deleted file: nothing new to review
            else:
                path = target[2:] if target.startswith("b/") else target
                current = SourceFile(path=path, lines=[], language=language_for(path))
            in_hunk = False
            continue
        if raw.startswith("--- "):
            continue
        match = HUNK_HEADER.match(raw)
        if match:
            new_line = int(match.group(1))
            in_hunk = current is not None
            continue
        if not in_hunk or current is None:
            continue
        if raw.startswith("+"):
            current.lines.append(SourceLine(new_line, raw[1:], changed=True))
            new_line += 1
        elif raw.startswith(" "):
            current.lines.append(SourceLine(new_line, raw[1:], changed=False))
            new_line += 1
        elif raw.startswith("-") or raw.startswith("\\"):
            continue  # removed line or "\ No newline at end of file"
        elif raw == "":
            continue
    finish()

    if not files:
        raise DiffError("The diff has no added code to review.")
    return ReviewInput(files=files, kind="diff", title=title)


def render_for_model(review_input: ReviewInput) -> str:
    """Show the code with real line numbers.

    In a diff, changed lines are marked with ``+`` so the model knows what
    is in scope, and gaps between hunks are shown as ``...``.
    """
    blocks = []
    for f in review_input.files:
        out = [f"FILE: {f.path} (language: {f.language})"]
        previous = None
        for line in f.lines:
            if previous is not None and line.number != previous + 1:
                out.append("     ...")
            marker = "+" if (review_input.kind == "diff" and line.changed) else " "
            out.append(f"{line.number:>4}{marker}| {line.text}")
            previous = line.number
        blocks.append("\n".join(out))
    return "\n\n".join(blocks)


def count_lines(review_input: ReviewInput) -> int:
    return sum(len(f.changed_numbers) for f in review_input.files)
