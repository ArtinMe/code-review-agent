from codereview.diff import from_diff, from_snippet
from codereview.grounding import ground
from tests.conftest import raw

CODE = """\
import os

def load(name):
    path = os.path.join("/data", name)
    with open(path) as f:
        return f.read()
"""


def test_exact_quote_is_kept():
    r = ground(raw(4, 'path = os.path.join("/data", name)'), "security", from_snippet(CODE))
    assert r.reason == "kept"
    assert (r.finding.line_start, r.finding.line_end) == (4, 4)


def test_whitespace_differences_are_tolerated():
    r = ground(raw(4, 'path  =  os.path.join("/data",   name)'), "security", from_snippet(CODE))
    assert r.reason == "kept"


def test_off_by_two_citation_is_reanchored():
    r = ground(raw(6, "with open(path) as f:"), "correctness", from_snippet(CODE))
    assert r.reason == "reanchored"
    assert r.finding.line_start == 5
    assert r.finding.reanchored


def test_invented_quote_is_dropped():
    r = ground(raw(4, "subprocess.run(cmd, shell=True)"), "security", from_snippet(CODE))
    assert r.reason == "ungrounded" and r.finding is None


def test_line_outside_file_is_dropped():
    r = ground(raw(400, "return f.read()"), "security", from_snippet(CODE))
    assert r.finding is None


def test_tiny_quote_is_not_enough_evidence():
    r = ground(raw(4, "("), "security", from_snippet(CODE))
    assert r.finding is None


def test_renamed_snippet_file_still_matches():
    r = ground(raw(4, "os.path.join", file="main.py"), "security", from_snippet(CODE, "snippet.py"))
    assert r.finding.file == "snippet.py"


def test_diff_context_line_is_out_of_scope():
    diff = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,3 @@\n"
        " old_line = eval(user_input)\n+new_line = 1\n keep = 2\n"
    )
    review_input = from_diff(diff)
    r = ground(raw(1, "old_line = eval(user_input)", file="a.py"), "security", review_input)
    assert r.reason == "out_of_scope"
    r = ground(raw(2, "new_line = 1", file="a.py"), "security", review_input)
    assert r.reason == "kept"
