"""Web app: one page plus a JSON API.

POST /api/review  {"code": "...", "filename": "app.py"}
                  {"pr_url": "https://github.com/o/r/pull/1"}
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from ..diff import DiffError, from_snippet
from ..fixer import FixError, fix, line_diff
from ..github import GitHubError, fetch_pull_request
from ..llm import GeminiClient, LLMClient, LLMError
from ..models import Finding
from ..pipeline import InputTooLarge, review
from . import demo

MAX_CODE_CHARS = 60_000
EXAMPLE_REPORT = Path(__file__).parent / "static" / "example.json"
EXAMPLE_FIX = Path(__file__).parent / "static" / "example_fix.json"


class RateLimiter:
    """Token bucket per client IP, so one visitor can't spend the whole API quota."""

    def __init__(self, capacity: int = 5, refill_seconds: float = 60.0) -> None:
        self.capacity = capacity
        self.rate = capacity / refill_seconds
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.capacity), now))
            tokens = min(self.capacity, tokens + (now - last) * self.rate)
            if tokens < 1:
                self._buckets[key] = (tokens, now)
                return False
            self._buckets[key] = (tokens - 1, now)
            return True


class DailyCap:
    """A ceiling on reviews per day for the whole site, to protect a public demo's API quota.

    Counts per process; the Docker image runs a single worker so this is the whole site.
    """

    def __init__(self, limit: int) -> None:
        self.limit = limit  # 0 means no ceiling
        self._day = ""
        self._count = 0
        self._lock = threading.Lock()

    def allow(self, today: str | None = None) -> bool:
        if self.limit <= 0:
            return True
        today = today or time.strftime("%Y-%m-%d", time.gmtime())
        with self._lock:
            if today != self._day:
                self._day, self._count = today, 0
            if self._count >= self.limit:
                return False
            self._count += 1
            return True


def create_app(client_factory: Callable[[], LLMClient] | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__)
    if os.getenv("TRUST_PROXY") == "1":
        # behind one reverse proxy (Railway, Render): take the client IP it reports
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)  # type: ignore[method-assign]
    limiter = RateLimiter(capacity=int(os.getenv("RATE_LIMIT_PER_MINUTE", "5")))
    daily = DailyCap(limit=int(os.getenv("MAX_REVIEWS_PER_DAY", "0")))
    client_holder: dict[str, LLMClient] = {}

    def client() -> LLMClient:
        if "c" not in client_holder:
            client_holder["c"] = (client_factory or GeminiClient)()
        return client_holder["c"]

    # A real review of the sample code, saved ahead of time, so visitors see a
    # finished report immediately without spending API quota.
    example = json.loads(EXAMPLE_REPORT.read_text()) if EXAMPLE_REPORT.exists() else None
    example_fix = json.loads(EXAMPLE_FIX.read_text()) if EXAMPLE_FIX.exists() else None

    @app.get("/")
    def index():
        return render_template("index.html", example=example, example_fix=example_fix)

    @app.get("/debate")
    def debate():
        """Scripted showcase of a two-model review. Static: no model is called."""
        return render_template(
            "debate.html",
            fix={"fixed_code": demo.AGREED_FIX, "diff": line_diff(demo.ORIGINAL, demo.AGREED_FIX)},
        )

    @app.get("/healthz")
    def health():
        return {"ok": True}

    @app.post("/api/review")
    def api_review():
        if not limiter.allow(request.remote_addr or "?"):
            return jsonify(error="Too many reviews in a minute. Try again shortly."), 429
        if not daily.allow():
            return jsonify(
                error="The demo's daily review limit is used up. Try again tomorrow, "
                "or run it yourself from the GitHub repository."
            ), 429

        body = request.get_json(silent=True) or {}
        try:
            if body.get("pr_url"):
                review_input = fetch_pull_request(str(body["pr_url"]))
            else:
                code = str(body.get("code", ""))
                if len(code) > MAX_CODE_CHARS:
                    return jsonify(error="That's too much code for one review."), 413
                filename = str(body.get("filename") or "snippet.py")[:100]
                review_input = from_snippet(code, path=filename)
            result = review(review_input, client())
        except (DiffError, GitHubError, InputTooLarge) as e:
            return jsonify(error=str(e)), 400
        except LLMError as e:
            return jsonify(error=str(e)), 503

        if all(run.error for run in result.agents):
            return jsonify(error="Every reviewer failed. The model service may be down."), 503
        return jsonify(result.to_dict())

    @app.post("/api/fix")
    def api_fix():
        if not limiter.allow(request.remote_addr or "?"):
            return jsonify(error="Too many requests in a minute. Try again shortly."), 429
        if not daily.allow():
            return jsonify(error="The demo's daily limit is used up. Try again tomorrow."), 429

        body = request.get_json(silent=True) or {}
        code = str(body.get("code", ""))
        filename = str(body.get("filename") or "snippet.py")[:100]
        if not code.strip() or len(code) > MAX_CODE_CHARS:
            return jsonify(error="Send the same code that was reviewed."), 400
        try:
            findings = [_finding_from_json(f) for f in body.get("findings", [])[:20]]
        except (TypeError, ValueError, KeyError):
            return jsonify(error="The findings weren't in the expected format."), 400
        try:
            result = fix(code, filename, findings, client())
        except FixError as e:
            return jsonify(error=str(e)), 422
        except LLMError as e:
            return jsonify(error=str(e)), 503
        return jsonify(result.to_dict())

    return app


def _finding_from_json(data: dict) -> Finding:
    severity = str(data["severity"])
    if severity not in ("critical", "major", "minor"):
        raise ValueError(severity)
    return Finding(
        file=str(data.get("file", "")),
        line_start=int(data["line_start"]),
        line_end=int(data["line_end"]),
        severity=severity,
        title=str(data["title"])[:200],
        explanation=str(data.get("explanation", ""))[:2000],
        suggestion=str(data.get("suggestion", ""))[:4000],
        confidence=float(data.get("confidence", 1.0)),
        agents=[str(a) for a in data.get("agents", [])][:4],
    )


app = create_app()
