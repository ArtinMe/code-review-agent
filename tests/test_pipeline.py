import pytest

from codereview.diff import from_snippet
from codereview.pipeline import InputTooLarge, review
from tests.conftest import FakeLLM, raw

CODE = """\
def find(db, name):
    rows = db.execute(f"SELECT * FROM users WHERE name = '{name}'")
    for i in range(len(rows) + 1):
        print(rows[i])
"""


def test_full_review_verifies_merges_and_ranks():
    llm = FakeLLM(
        {
            "security": [
                raw(
                    2,
                    "db.execute(f\"SELECT * FROM users WHERE name = '{name}'\")",
                    severity="critical",
                    title="SQL injection",
                    confidence=0.95,
                )
            ],
            "correctness": [
                raw(3, "for i in range(len(rows) + 1):", title="Off-by-one loop", confidence=0.9),
                raw(2, 'db.execute(f"SELECT', title="SQL injection via f-string", confidence=0.7),
                raw(9, "os.system(cmd)", title="Command injection"),  # invented: dropped
            ],
            "performance": [raw(4, "print(rows[i])", severity="minor", confidence=0.3)],  # low conf
        }
    )
    result = review(from_snippet(CODE), llm)

    assert sorted(llm.calls) == ["correctness", "maintainability", "performance", "security"]
    assert [f.title for f in result.findings] == ["SQL injection", "Off-by-one loop"]
    assert result.findings[0].agents == ["correctness", "security"]
    assert result.stats.dropped_ungrounded == 1
    assert result.stats.merged_duplicates == 1
    assert result.stats.dropped_low_confidence == 1
    assert not result.partial
    assert 0 <= result.score < 10


def test_one_failing_agent_gives_partial_review():
    llm = FakeLLM({"correctness": [raw(3, "for i in range(len(rows) + 1):")]}, failing={"security"})
    result = review(from_snippet(CODE), llm)
    assert result.partial
    assert len(result.findings) == 1
    failed = [run for run in result.agents if run.error]
    assert [run.agent for run in failed] == ["security"]


def test_huge_input_is_refused_before_calling_the_model():
    llm = FakeLLM()
    with pytest.raises(InputTooLarge):
        review(from_snippet("x = 1\n" * 5000), llm)
    assert llm.calls == []


def test_to_dict_is_json_ready():
    import json

    result = review(from_snippet(CODE), FakeLLM())
    data = json.loads(json.dumps(result.to_dict()))
    assert data["score"] == 10.0 and data["findings"] == []


def test_cli_reports_total_failure_instead_of_a_clean_result(monkeypatch, tmp_path, capsys):
    from codereview import cli

    source = tmp_path / "a.py"
    source.write_text(CODE)
    everyone = {"security", "correctness", "performance", "maintainability"}
    monkeypatch.setattr(cli, "GeminiClient", lambda: FakeLLM(failing=everyone))
    assert cli.main(["--no-cache", "file", str(source)]) == 2
    assert "every reviewer failed" in capsys.readouterr().err
