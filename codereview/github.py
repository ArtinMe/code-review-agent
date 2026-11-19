"""Fetch a pull request's diff from GitHub."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from .diff import DiffError, from_diff
from .models import ReviewInput

PR_URL = re.compile(
    r"^https?://github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)(?:/[\w/-]*)?(?:[#?].*)?$"
)
MAX_DIFF_BYTES = 400_000


class GitHubError(RuntimeError):
    pass


def parse_pr_url(url: str) -> tuple[str, str, int]:
    match = PR_URL.match(url.strip())
    if not match:
        raise GitHubError("That doesn't look like a GitHub pull request URL.")
    owner, repo, number = match.groups()
    return owner, repo, int(number)


def _get(url: str, accept: str) -> bytes:
    headers = {"Accept": accept, "User-Agent": "codereview-ai"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read(MAX_DIFF_BYTES + 1)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise GitHubError("Pull request not found, or the repository is private.") from e
        if e.code in (403, 429):
            raise GitHubError("GitHub rate limit reached. Set GITHUB_TOKEN to raise it.") from e
        raise GitHubError(f"GitHub returned HTTP {e.code}.") from e
    except urllib.error.URLError as e:
        raise GitHubError("Couldn't reach GitHub.") from e


def fetch_pull_request(url: str) -> ReviewInput:
    owner, repo, number = parse_pr_url(url)
    api = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
    meta = json.loads(_get(api, "application/vnd.github+json"))
    diff = _get(api, "application/vnd.github.v3.diff")
    if len(diff) > MAX_DIFF_BYTES:
        raise GitHubError("This pull request is too large to review (over 400 KB of diff).")
    try:
        return from_diff(diff.decode("utf-8", errors="replace"), title=meta.get("title", ""))
    except DiffError as e:
        raise GitHubError(str(e)) from e
