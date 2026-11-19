from codereview.web.app import RateLimiter, create_app
from tests.conftest import FakeLLM, raw

CODE = "def f(xs):\n    return xs[len(xs)]\n"


def client_with(llm, monkeypatch, limit="100"):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", limit)
    app = create_app(client_factory=lambda: llm)
    app.config["TESTING"] = True
    return app.test_client()


def test_review_endpoint_returns_findings(monkeypatch):
    llm = FakeLLM({"correctness": [raw(2, "return xs[len(xs)]", title="Index out of range")]})
    response = client_with(llm, monkeypatch).post(
        "/api/review", json={"code": CODE, "filename": "f.py"}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["findings"][0]["title"] == "Index out of range"
    assert data["findings"][0]["file"] == "f.py"


def test_empty_code_is_a_400(monkeypatch):
    response = client_with(FakeLLM(), monkeypatch).post("/api/review", json={"code": "  "})
    assert response.status_code == 400


def test_all_agents_failing_is_a_503(monkeypatch):
    llm = FakeLLM(failing={"security", "correctness", "performance", "maintainability"})
    response = client_with(llm, monkeypatch).post("/api/review", json={"code": CODE})
    assert response.status_code == 503


def test_rate_limit(monkeypatch):
    client = client_with(FakeLLM(), monkeypatch, limit="2")
    codes = [client.post("/api/review", json={"code": CODE}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_bucket_refills_over_time():
    limiter = RateLimiter(capacity=1, refill_seconds=10)
    assert limiter.allow("ip", now=0)
    assert not limiter.allow("ip", now=1)
    assert limiter.allow("ip", now=11)


def test_index_page_renders(monkeypatch):
    response = client_with(FakeLLM(), monkeypatch).get("/")
    assert response.status_code == 200 and b"CodeReview AI" in response.data


def test_daily_cap_resets_each_day():
    from codereview.web.app import DailyCap

    cap = DailyCap(limit=2)
    assert [cap.allow("2026-11-18") for _ in range(3)] == [True, True, False]
    assert cap.allow("2026-11-19")
    assert DailyCap(limit=0).allow("2026-11-18")  # 0 means no ceiling


def test_debate_demo_page_is_static_and_labelled(monkeypatch):
    llm = FakeLLM()
    response = client_with(llm, monkeypatch).get("/debate")
    assert response.status_code == 200
    assert b"scripted demo" in response.data  # it must say it isn't live output
    assert llm.calls == []  # and it must never call a model


def test_shared_stylesheet_is_served(monkeypatch):
    response = client_with(FakeLLM(), monkeypatch).get("/static/base.css")
    assert response.status_code == 200 and b"--ink" in response.data


def test_fix_endpoint_returns_fixed_code(monkeypatch):
    from codereview.fixer import Change, FixOutput

    llm = FakeLLM()
    llm.queued = [
        FixOutput(
            fixed_code="def f(xs):\n    return xs[-1]\n",
            changes=[Change(finding="Index", change="Use -1.")],
        )
    ]
    finding = {
        "severity": "critical",
        "title": "Index",
        "line_start": 2,
        "line_end": 2,
        "explanation": "Past the end.",
        "suggestion": "xs[-1]",
    }
    response = client_with(llm, monkeypatch).post(
        "/api/fix", json={"code": CODE, "filename": "f.py", "findings": [finding]}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["fixed_code"].endswith("xs[-1]\n") and data["diff"]


def test_fix_endpoint_rejects_bad_findings(monkeypatch):
    response = client_with(FakeLLM(), monkeypatch).post(
        "/api/fix", json={"code": CODE, "findings": [{"severity": "nope"}]}
    )
    assert response.status_code == 400
