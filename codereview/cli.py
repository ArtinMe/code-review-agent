"""Command line: review a file, a diff, or a GitHub pull request.

    codereview file app.py
    git diff main | codereview diff -
    codereview pr https://github.com/owner/repo/pull/123 --fail-on major

Exit code is 1 when ``--fail-on`` is set and a finding at or above that
severity is found, so it can gate a CI job.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .diff import DiffError, from_diff, from_snippet
from .github import GitHubError, fetch_pull_request
from .llm import CachedClient, GeminiClient, LLMError
from .models import SEVERITY_WEIGHT, Review
from .pipeline import InputTooLarge, review

COLORS = {"critical": "\033[31m", "major": "\033[33m", "minor": "\033[36m"}
RESET, DIM, BOLD = "\033[0m", "\033[2m", "\033[1m"


def _print_review(result: Review, color: bool) -> None:
    def c(code: str, text: str) -> str:
        return f"{code}{text}{RESET}" if color else text

    for f in result.findings:
        where = f"{f.file}:{f.line_start}" + (
            f"-{f.line_end}" if f.line_end != f.line_start else ""
        )
        print(
            f"{c(COLORS[f.severity], f.severity.upper()):<10} {c(BOLD, f.title)}  {c(DIM, where)}"
        )
        print(f"    {f.explanation}")
        if f.suggestion:
            print(c(DIM, "    fix: ") + f.suggestion.replace("\n", "\n         "))
        print(c(DIM, f"    {', '.join(f.agents)} · confidence {f.confidence:.2f}\n"))
    if not result.findings:
        print("No problems found.\n")
    s = result.stats
    print(
        f"Score {result.score}/10 · {len(result.findings)} findings · "
        f"{result.lines_reviewed} lines in {result.files_reviewed} file(s) · {result.seconds:.1f}s"
    )
    print(
        c(
            DIM,
            f"Verification: {s.dropped_ungrounded} ungrounded and {s.dropped_out_of_scope} "
            f"out-of-scope findings dropped, {s.reanchored} re-anchored, "
            f"{s.merged_duplicates} duplicates merged",
        )
    )
    for run in result.agents:
        if run.error:
            print(c(COLORS["major"], f"Agent {run.agent} failed: {run.error} (review is partial)"))


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="codereview", description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true", help="print the review as JSON")
    parser.add_argument("--no-cache", action="store_true", help="always call the model")
    parser.add_argument(
        "--fail-on", choices=list(SEVERITY_WEIGHT), help="exit 1 if a finding is this severe"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_file = sub.add_parser("file", help="review a whole source file")
    p_file.add_argument("path")
    p_diff = sub.add_parser("diff", help="review a unified diff (use - for stdin)")
    p_diff.add_argument("path")
    p_pr = sub.add_parser("pr", help="review a GitHub pull request by URL")
    p_pr.add_argument("url")
    args = parser.parse_args(argv)

    try:
        if args.command == "file":
            source = Path(args.path)
            review_input = from_snippet(source.read_text(), path=source.name)
        elif args.command == "diff":
            text = sys.stdin.read() if args.path == "-" else Path(args.path).read_text()
            review_input = from_diff(text)
        else:
            review_input = fetch_pull_request(args.url)

        client = GeminiClient()
        result = review(review_input, client if args.no_cache else CachedClient(client))
    except (DiffError, GitHubError, LLMError, InputTooLarge, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if all(run.error for run in result.agents):
        reasons = sorted({run.error or "" for run in result.agents})
        print(f"error: every reviewer failed: {'; '.join(reasons)}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        _print_review(result, color=sys.stdout.isatty())

    if args.fail_on:
        threshold = SEVERITY_WEIGHT[args.fail_on]
        if any(SEVERITY_WEIGHT[f.severity] >= threshold for f in result.findings):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
