from codereview.diff import from_snippet
from codereview.pipeline import review
from evals.run import Bug, load_cases, score_case
from tests.conftest import FakeLLM, raw


def test_labels_resolve_to_real_lines():
    cases = load_cases()
    assert len(cases) >= 15
    for file, source, bugs in cases:
        lines = source.splitlines()
        for bug in bugs:
            assert 1 <= bug.line <= len(lines), file


def test_scoring_counts_catches_extras_and_clean_false_positives():
    source = "a = 1\nb = 2\nc = 3\nd = 4\ne = 5\nf = 6\n"
    bug = Bug("x.py", "correctness", 2)
    llm = FakeLLM({"correctness": [raw(2, "b = 2"), raw(6, "f = 6", title="Other thing entirely")]})
    result = review(from_snippet(source, "x.py"), llm)
    scored = score_case("x.py", [bug], result)
    assert scored.caught == [bug]
    assert scored.caught_by_category == [True]
    assert scored.extra == 1  # the line-6 finding doesn't match a planted bug

    clean = score_case("x.py", [], result)
    assert clean.clean_false_positives == len(result.findings)
