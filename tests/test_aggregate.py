from codereview import aggregate
from codereview.models import Finding


def make(
    line,
    severity="major",
    conf=0.8,
    title="SQL injection in query",
    agent="security",
    quote="q",
    end=None,
):
    return Finding(
        file="a.py",
        line_start=line,
        line_end=end or line,
        severity=severity,
        title=title,
        explanation="User input reaches the SQL query.",
        suggestion="",
        confidence=conf,
        agents=[agent],
        quote=quote,
    )


def test_same_issue_from_two_agents_is_merged_and_more_confident():
    merged, folded = aggregate.merge(
        [
            make(8, "critical", 0.9, agent="security"),
            make(8, "major", 0.6, title="Unsafe SQL query built from input", agent="correctness"),
        ]
    )
    assert folded == 1 and len(merged) == 1
    m = merged[0]
    assert m.severity == "critical"
    assert m.agents == ["correctness", "security"]
    assert abs(m.confidence - (1 - 0.1 * 0.4)) < 1e-9


def test_different_issues_on_nearby_lines_stay_separate():
    merged, folded = aggregate.merge(
        [
            make(8, title="SQL injection in query", quote="a"),
            make(9, title="Connection never closed leaks handle", quote="b"),
        ]
    )
    assert folded == 0 and len(merged) == 2


def test_far_apart_findings_never_merge():
    merged, _ = aggregate.merge([make(1), make(30)])
    assert len(merged) == 2


def test_rank_orders_by_severity_times_confidence():
    ranked = aggregate.rank(
        [make(1, "minor", 1.0), make(2, "critical", 0.5), make(3, "major", 0.9)]
    )
    assert [f.line_start for f in ranked] == [3, 2, 1]


def test_score_is_deterministic_and_bounded():
    assert aggregate.score([]) == 10.0
    assert aggregate.score([make(1, "critical", 1.0)]) == 7.0
    assert aggregate.score([make(i, "critical", 1.0) for i in range(10)]) == 0.0


def test_two_different_problems_on_the_same_line_are_kept_apart():
    a = make(5, title="SQL injection", agent="security")
    b = make(5, title="Query inside loop", agent="performance")
    b.explanation = "One database round trip per customer makes this slow."
    merged, folded = aggregate.merge([a, b])
    assert folded == 0 and len(merged) == 2


def test_same_bug_with_different_titles_is_merged():
    # Two real findings from one run: same line, same bug, different wording.
    a = make(9, "critical", 0.95, title="Off-by-one error in loop range", agent="correctness")
    a.explanation = (
        "The loop iterates from `0` up to `len(rows)` (inclusive), attempting to access "
        "`rows[len(rows)]`. Since list indices are `0` to `len(rows) - 1`, this will cause an "
        "`IndexError` when `i` equals `len(rows)`, leading to a program crash."
    )
    b = make(9, "critical", 0.9, title="Loop iterates out of bounds", agent="performance")
    b.explanation = (
        "The loop attempts to iterate `len(rows) + 1` times, causing an `IndexError` when "
        "`rows[len(rows)]` is accessed on the last iteration. This will crash the program."
    )
    merged, folded = aggregate.merge([a, b])
    assert folded == 1 and merged[0].agents == ["correctness", "performance"]
