import pytest

from codereview.diff import DiffError, from_diff, from_snippet, render_for_model

DIFF = """\
diff --git a/app/db.py b/app/db.py
index 1111111..2222222 100644
--- a/app/db.py
+++ b/app/db.py
@@ -10,4 +10,5 @@ def connect():
     conn = open_db()
-    cursor = conn.cursor()
+    cursor = conn.cursor(buffered=True)
+    cursor.execute(query)
     return cursor
\\ No newline at end of file
@@ -40,2 +41,3 @@ def close(conn):
     conn.close()
+    log("closed")
diff --git a/old.py b/old.py
deleted file mode 100644
--- a/old.py
+++ /dev/null
@@ -1,2 +0,0 @@
-x = 1
-y = 2
diff --git a/package-lock.json b/package-lock.json
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,1 +1,1 @@
-{}
+{"a": 1}
"""


def test_snippet_lines_are_all_in_scope():
    review_input = from_snippet("a = 1\r\nb = 2\n\n", path="x.py")
    f = review_input.files[0]
    assert [line.number for line in f.lines] == [1, 2]
    assert f.changed_numbers == {1, 2}
    assert f.language == "python"


def test_empty_snippet_is_rejected():
    with pytest.raises(DiffError):
        from_snippet("   \n\n")


def test_diff_keeps_new_side_with_real_line_numbers():
    review_input = from_diff(DIFF)
    assert review_input.kind == "diff"
    assert [f.path for f in review_input.files] == ["app/db.py"]  # deleted + lockfile skipped
    f = review_input.files[0]
    numbers = {line.number: (line.text, line.changed) for line in f.lines}
    assert numbers[10] == ("    conn = open_db()", False)
    assert numbers[11] == ("    cursor = conn.cursor(buffered=True)", True)
    assert numbers[12] == ("    cursor.execute(query)", True)
    assert numbers[13] == ("    return cursor", False)
    assert numbers[42] == ('    log("closed")', True)
    assert f.changed_numbers == {11, 12, 42}


def test_diff_without_additions_is_rejected():
    with pytest.raises(DiffError):
        from_diff("diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1,1 +1,0 @@\n-gone\n")


def test_render_marks_changed_lines_and_gaps():
    text = render_for_model(from_diff(DIFF))
    assert "  11+| " in text
    assert "  10 | " in text
    assert "     ..." in text  # gap between the two hunks
