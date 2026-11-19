import pytest

from codereview.fixer import Change, FixError, FixOutput, fix, line_diff
from codereview.models import Finding
from tests.conftest import FakeLLM

CODE = "def first(xs):\n    return xs[len(xs)]\n"
GOOD = "def first(xs):\n    return xs[0]\n"
FINDING = Finding(
    file="a.py",
    line_start=2,
    line_end=2,
    severity="critical",
    title="Index out of range",
    explanation="xs[len(xs)] is always past the end.",
    suggestion="Use xs[0].",
    confidence=0.9,
    agents=["correctness"],
)


def answer(code: str) -> FixOutput:
    return FixOutput(fixed_code=code, changes=[Change(finding="Index out of range", change="x")])


def test_fix_returns_code_diff_and_checks():
    llm = FakeLLM()
    llm.queued = [answer(GOOD)]
    result = fix(CODE, "a.py", [FINDING], llm)
    assert result.fixed_code == GOOD
    assert [d["op"] for d in result.diff] == [" ", "-", "+"]
    assert "Parses as valid Python." in result.checks
    assert "Index out of range" in llm.prompts[0] and "Use xs[0]." in llm.prompts[0]


def test_syntax_error_gets_one_retry_with_the_error():
    llm = FakeLLM()
    llm.queued = [answer("def first(xs):\n    return xs[0\n"), answer(GOOD)]
    result = fix(CODE, "a.py", [FINDING], llm)
    assert result.fixed_code == GOOD
    assert "rejected" in llm.prompts[1]


def test_still_broken_after_retry_is_refused():
    llm = FakeLLM()
    broken = answer("def first(xs) return\n")
    llm.queued = [broken, broken]
    with pytest.raises(FixError):
        fix(CODE, "a.py", [FINDING], llm)


def test_fragment_with_placeholder_is_refused():
    llm = FakeLLM()
    fragment = answer("def first(xs):\n    ...\n")
    llm.queued = [fragment, fragment]
    with pytest.raises(FixError, match="placeholder"):
        fix(CODE, "a.py", [FINDING], llm)


def test_unchanged_file_is_refused():
    llm = FakeLLM()
    llm.queued = [answer(CODE)]
    with pytest.raises(FixError, match="unchanged"):
        fix(CODE, "a.py", [FINDING], llm)


def test_nothing_to_fix_makes_no_model_call():
    llm = FakeLLM()
    with pytest.raises(FixError):
        fix(CODE, "a.py", [], llm)
    assert llm.calls == []


def test_non_python_files_skip_the_parse_check():
    llm = FakeLLM()
    llm.queued = [answer("const a = 1;\n")]
    result = fix("var a = 1;\n", "a.js", [FINDING], llm)
    assert not any("Python" in c for c in result.checks)


def test_line_diff_numbers_both_sides():
    diff = line_diff("a\nb\nc\n", "a\nB\nc\nd\n")
    assert diff == [
        {"op": " ", "old": 1, "new": 1, "text": "a"},
        {"op": "-", "old": 2, "new": None, "text": "b"},
        {"op": "+", "old": None, "new": 2, "text": "B"},
        {"op": " ", "old": 3, "new": 3, "text": "c"},
        {"op": "+", "old": None, "new": 4, "text": "d"},
    ]


def test_names_guessed_inside_strings_are_flagged():
    from codereview.fixer import new_names_in_strings

    before = 'cur.execute(f"SELECT * FROM orders WHERE customer = \'{customer}\'")\n'
    after = 'cur.execute("SELECT SUM(order_total) FROM orders WHERE customer = ?", (customer,))\n'
    assert new_names_in_strings(before, after) == ["order_total"]
    # names that already exist, SQL keywords, and new variables outside strings are fine
    assert new_names_in_strings("x = 'orders'\n", "total = 'orders'\n") == []


def test_change_labels_are_mapped_to_finding_titles():
    llm = FakeLLM()
    llm.queued = [FixOutput(fixed_code=GOOD, changes=[
        Change(finding="[critical] Index out of range (lines 2-2)", change="Use xs[0].")])]
    result = fix(CODE, "a.py", [FINDING], llm)
    assert result.changes[0].finding == "Index out of range"
