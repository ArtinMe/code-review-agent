def run_performance_agent(code: str, client, mode: str = "simple") -> str:
    if mode == "simple":
        style = """Use plain English. Short sentences. Avoid technical jargon.
Explain issues like you're talking to someone who builds things at home as a hobby.
Keep each explanation under 3 sentences."""
    else:
        style = """Use precise technical language. Reference Big O notation, memory complexity, and optimization patterns.
Target audience is senior software engineers who want deep analysis."""

    prompt = f"""You are a code performance expert.
Analyze the following code for performance issues.
Look for:
- Unnecessary loops or nested loops
- Inefficient algorithms
- Memory waste or memory leaks
- Slow database queries
- Better data structures that could be used
- Redundant computations that could be cached

Explanation style: {style}

Code to review:
{code}

Format your response exactly like this:

## Performance Review

### Issues Found

1. **Issue Name** - Severity: High/Medium/Low

   Explanation of the issue in plain text outside the code block.

   **Fix:**
```python
   only put actual runnable code here, no explanations, no comments, no ... placeholders
```

If no issues found, write: "No performance issues found."

Rules:
- Never use --- as a separator
- Code blocks must contain ONLY runnable code, never explanations or comments
- Never use ... or placeholders in code blocks
- Keep explanations in plain text outside code blocks
- Use numbers for issues, not bullet points"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text
