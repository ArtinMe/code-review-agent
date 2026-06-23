def run_coordinator(code: str, security_report: str, correctness_report: str, readability_report: str, client) -> str:
    prompt = f"""You are a senior code review coordinator.
You have received four specialist reports about the following code.
Your job is to synthesize them into one clean, prioritized, actionable report.

ORIGINAL CODE:
{code}

SECURITY REPORT:
{security_report}

CORRECTNESS REPORT:
{correctness_report}

READABILITY REPORT:
{readability_report}

Format your response exactly like this:

## Final Code Review

**Overall Score: X/10**

### Top 3 Critical Issues

1. **Issue Name** - Category: Security/Correctness/Readability/Performance

   Short explanation of why this is critical.

2. **Issue Name** - Category: Security/Correctness/Readability/Performance

   Short explanation of why this is critical.

3. **Issue Name** - Category: Security/Correctness/Readability/Performance

   Short explanation of why this is critical.

### Quick Wins

1. Quick fix the developer can do right now.
2. Quick fix the developer can do right now.

### Final Verdict

2-3 sentences max. Be direct and actionable.

## Fixed Code

Provide the complete corrected version of the original code with all issues fixed. No explanations inside the code block, just clean runnable code.

```python
complete fixed code here
```

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
