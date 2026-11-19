"""Measure how well the reviewer finds planted bugs and stays quiet on clean code.

    uv run python -m evals.run                # uses the on-disk cache
    uv run python -m evals.run --no-cache     # fresh model calls

Metrics
- recall: planted bugs with a finding whose lines overlap the bug (+/- 1 line)
- clean-file false positives: findings of major/critical severity on files with no bugs
- extra findings: findings on buggy files that don't match a planted bug.
  These aren't necessarily wrong (a file can have more than one problem), so
  they're reported, not counted as errors.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from codereview.agents import AGENTS
from codereview.diff import from_snippet
from codereview.llm import CachedClient, GeminiClient, LLMClient
from codereview.models import Review
from codereview.pipeline import review

HERE = Path(__file__).parent
LINE_SLACK = 1
AGENT_COUNT = len(AGENTS)


@dataclass
class Bug:
    file: str
    category: str
    line: int
    note: str = ""


@dataclass
class CaseResult:
    file: str
    bugs: list[Bug]
    caught: list[Bug] = field(default_factory=list)
    caught_by_category: list[bool] = field(default_factory=list)
    extra: int = 0
    clean_false_positives: int = 0
    findings: int = 0
    dropped: int = 0
    agent_errors: int = 0


def load_cases() -> list[tuple[str, str, list[Bug]]]:
    labels = json.loads((HERE / "labels.json").read_text())
    cases = []
    for case in labels["cases"]:
        source = (HERE / "cases" / case["file"]).read_text()
        lines = source.splitlines()
        bugs = []
        for bug in case["bugs"]:
            line = next((i for i, text in enumerate(lines, 1) if bug["match"] in text), None)
            if line is None:
                raise ValueError(f"{case['file']}: label match not found: {bug['match']!r}")
            bugs.append(Bug(case["file"], bug["category"], line, bug.get("note", "")))
        cases.append((case["file"], source, bugs))
    return cases


def score_case(file: str, bugs: list[Bug], result: Review) -> CaseResult:
    out = CaseResult(file=file, bugs=bugs, findings=len(result.findings))
    out.dropped = result.stats.dropped_ungrounded + result.stats.dropped_out_of_scope
    out.agent_errors = sum(1 for run in result.agents if run.error)
    matched_findings = set()
    for bug in bugs:
        hits = [
            i
            for i, f in enumerate(result.findings)
            if f.line_start - LINE_SLACK <= bug.line <= f.line_end + LINE_SLACK
        ]
        if hits:
            out.caught.append(bug)
            out.caught_by_category.append(
                any(bug.category in result.findings[i].agents for i in hits)
            )
            matched_findings.update(hits)
    if bugs:
        out.extra = len(result.findings) - len(matched_findings)
    else:
        out.clean_false_positives = sum(
            1 for f in result.findings if f.severity in ("major", "critical")
        )
    return out


def run(client: LLMClient, pause: float = 0.0) -> dict:
    cases = load_cases()
    results: list[CaseResult] = []
    for file, source, bugs in cases:
        result = review(from_snippet(source, path=file), client)
        scored = score_case(file, bugs, result)
        results.append(scored)
        status = "clean" if not bugs else f"{len(scored.caught)}/{len(bugs)} caught"
        print(
            f"  {file:<24} {status:<12} findings={scored.findings} dropped={scored.dropped}"
            + (f"  ({scored.agent_errors} agent errors)" if scored.agent_errors else "")
        )
        if pause and not all(run.cached for run in result.agents):
            time.sleep(pause)

    # A case where every agent failed tells us nothing about review quality.
    not_run = [r.file for r in results if r.agent_errors == AGENT_COUNT]
    results = [r for r in results if r.agent_errors < AGENT_COUNT]

    planted = [b for r in results for b in r.bugs]
    caught = [b for r in results for b in r.caught]
    clean = [r for r in results if not r.bugs]
    by_category: dict[str, list[int]] = {}
    for r in results:
        for bug in r.bugs:
            hit = bug in r.caught
            by_category.setdefault(bug.category, [0, 0])
            by_category[bug.category][0] += int(hit)
            by_category[bug.category][1] += 1
    right_agent = sum(flag for r in results for flag in r.caught_by_category)

    summary = {
        "model": client.model,
        "cases": len(results),
        "cases_not_run": not_run,
        "planted_bugs": len(planted),
        "caught": len(caught),
        "recall": round(len(caught) / len(planted), 3) if planted else None,
        "caught_by_matching_specialist": right_agent,
        "recall_by_category": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_category.items())},
        "clean_files": len(clean),
        "clean_files_with_false_positive": sum(1 for r in clean if r.clean_false_positives),
        "clean_false_positives": sum(r.clean_false_positives for r in clean),
        "extra_findings_on_buggy_files": sum(r.extra for r in results if r.bugs),
        "findings_dropped_by_verification": sum(r.dropped for r in results),
        "agent_errors": sum(r.agent_errors for r in results),
        "missed": [
            f"{b.file}:{b.line} ({b.note})" for r in results for b in r.bugs if b not in r.caught
        ],
    }
    return summary


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--pause", type=float, default=15.0, help="seconds between uncached cases")
    parser.add_argument("--out", default=str(HERE / "results" / "latest.json"))
    args = parser.parse_args()

    base = GeminiClient()
    client = base if args.no_cache else CachedClient(base)
    print(f"Running {len(load_cases())} cases with {base.model}\n")
    summary = run(client, pause=args.pause)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
