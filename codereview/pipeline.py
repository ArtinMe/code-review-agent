"""Run the agents in parallel and turn their answers into one verified review."""

from __future__ import annotations

import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from . import aggregate
from .agents import AGENTS, Agent, build_prompt
from .diff import count_lines, render_for_model
from .grounding import ground
from .llm import LLMClient
from .models import AgentOutput, AgentRun, GroundingStats, Review, ReviewInput

MAX_LINES = 1500


class InputTooLarge(ValueError):
    pass


def _ask(client: LLMClient, agent: Agent, prompt: str) -> tuple[AgentOutput | None, AgentRun]:
    run = AgentRun(agent=agent.name)
    started = time.perf_counter()
    try:
        with_meta = getattr(client, "review_with_meta", None)
        if with_meta is not None:
            output, run.cached = with_meta(agent.system_prompt(), prompt)
        else:
            output = client.review(agent.system_prompt(), prompt)
        run.findings_returned = len(output.findings)
        return output, run
    except Exception as e:  # one failing agent must not sink the whole review
        run.error = str(e) or type(e).__name__
        return None, run
    finally:
        run.seconds = time.perf_counter() - started


def review(
    review_input: ReviewInput,
    client: LLMClient,
    agents: Sequence[Agent] = AGENTS,
    min_confidence: float = aggregate.MIN_CONFIDENCE,
) -> Review:
    started = time.perf_counter()
    lines = sum(len(f.lines) for f in review_input.files)
    if lines > MAX_LINES:
        raise InputTooLarge(f"Too much code to review at once ({lines} lines, limit {MAX_LINES}).")

    prompt = build_prompt(render_for_model(review_input), review_input.kind, review_input.title)

    with ThreadPoolExecutor(max_workers=len(agents)) as pool:
        results = list(pool.map(lambda a: _ask(client, a, prompt), agents))

    stats = GroundingStats()
    grounded = []
    dropped: list[dict] = []
    for agent, (output, _run) in zip(agents, results, strict=True):
        if output is None:
            continue
        for raw in output.findings:
            result = ground(raw, agent.name, review_input)
            if result.finding is None:
                if result.reason == "out_of_scope":
                    stats.dropped_out_of_scope += 1
                else:
                    stats.dropped_ungrounded += 1
                dropped.append(
                    {
                        "agent": agent.name,
                        "reason": result.reason,
                        "title": raw.title,
                        "line_start": raw.line_start,
                        "quote": raw.quote,
                    }
                )
                continue
            if result.reason == "reanchored":
                stats.reanchored += 1
            grounded.append(result.finding)

    merged, stats.merged_duplicates = aggregate.merge(grounded)
    confident = [f for f in merged if f.confidence >= min_confidence]
    stats.dropped_low_confidence = len(merged) - len(confident)
    final = aggregate.rank(confident)
    stats.kept = len(final)

    return Review(
        findings=final,
        score=aggregate.score(final),
        agents=[run for _output, run in results],
        stats=stats,
        files_reviewed=len(review_input.files),
        lines_reviewed=count_lines(review_input),
        seconds=time.perf_counter() - started,
        dropped=dropped,
    )
