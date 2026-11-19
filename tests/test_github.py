import pytest

from codereview import github


def test_parse_pr_url():
    assert github.parse_pr_url("https://github.com/psf/requests/pull/6710") == (
        "psf",
        "requests",
        6710,
    )
    assert github.parse_pr_url("https://github.com/a/b.c/pull/1/files") == ("a", "b.c", 1)
    assert github.parse_pr_url("https://github.com/a/b/pull/9#discussion")[2] == 9


@pytest.mark.parametrize(
    "bad", ["https://gitlab.com/a/b/pull/1", "github.com/a/b/issues/3", "nope"]
)
def test_bad_urls_are_rejected(bad):
    with pytest.raises(github.GitHubError):
        github.parse_pr_url(bad)


def test_fetch_builds_review_input(monkeypatch):
    diff = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -0,0 +1,1 @@\n+print('hi')\n"

    def fake_get(url, accept):
        return b'{"title": "Say hi"}' if accept.endswith("+json") else diff.encode()

    monkeypatch.setattr(github, "_get", fake_get)
    review_input = github.fetch_pull_request("https://github.com/o/r/pull/7")
    assert review_input.title == "Say hi"
    assert review_input.files[0].path == "x.py"


def test_oversized_diff_is_refused(monkeypatch):
    def fake_get(url, accept):
        return b"{}" if accept.endswith("+json") else b"x" * (github.MAX_DIFF_BYTES + 1)

    monkeypatch.setattr(github, "_get", fake_get)
    with pytest.raises(github.GitHubError):
        github.fetch_pull_request("https://github.com/o/r/pull/7")
