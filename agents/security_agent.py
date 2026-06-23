def run_security_agent(code: str, client, mode: str = "simple") -> str:
    if mode == "simple":
        style = """Use plain English. Short sentences. Avoid technical jargon.
Explain issues like you're talking to someone who builds things at home as a hobby.
Keep each explanation under 3 sentences."""
    else:
        style = """Use precise technical language. Include CVE references where relevant.
Explain root causes and attack vectors in detail.
Target audience is senior software engineers."""

    prompt = f"""You are a security code review expert.
Analyze the following code for security vulnerabilities.
Look for:
- SQL injection risks
- Exposed API keys or passwords
- Unsafe user input handling
- Insecure dependencies
- Authentication/authorization issues

Explanation style: {style}

Code to review:
{code}

Format your response exactly like this:

## Security Review

### Issues Found

1. **Issue Name** - Severity: High/Medium/Low

   Explanation of the issue in plain text outside the code block.

   **Fix:**
```python
   only put actual runnable code here, no explanations, no comments, no ... placeholders
```

If no issues found, write: "No security issues found."

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
