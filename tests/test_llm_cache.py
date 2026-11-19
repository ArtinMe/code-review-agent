from codereview.llm import CachedClient
from tests.conftest import FakeLLM, raw


def test_cache_returns_same_answer_without_calling_model(tmp_path):
    inner = FakeLLM({"security": [raw(1, "x = 1")]})
    cached = CachedClient(inner, tmp_path)
    system = "Your area: Security.\nbrief"
    first, hit1 = cached.review_with_meta(system, "prompt")
    second, hit2 = cached.review_with_meta(system, "prompt")
    assert (hit1, hit2) == (False, True)
    assert first == second
    assert inner.calls == ["security"]


def test_different_prompt_is_a_cache_miss(tmp_path):
    inner = FakeLLM()
    cached = CachedClient(inner, tmp_path)
    cached.review("Your area: Security.", "a")
    cached.review("Your area: Security.", "b")
    assert len(inner.calls) == 2


def test_rate_limit_backoff_waits_for_the_quota_window():
    from codereview.llm import RATE_LIMIT_WAIT, backoff_seconds

    class RateLimited(Exception):
        code = 429

    assert backoff_seconds(RateLimited(), 1, 2.0) >= RATE_LIMIT_WAIT
    assert backoff_seconds(ValueError(), 1, 2.0) < 4.0
