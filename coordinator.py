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

(Be fair and calibrated with the score. Simple code with one bug should score 6-7/10. Only give low scores like 2-3/10 for code with multiple severe issues. Perfect code is 10/10.)

### Issues by Priority

**Critical** (must fix immediately):
1. Issue name — one sentence explanation.

**Major** (should fix soon):
1. Issue name — one sentence explanation.

**Minor** (nice to fix):
1. Issue name — one sentence explanation.

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
- Be fair and calibrated with scoring
- Only mark something Critical if it truly is critical
- Code blocks must contain ONLY runnable code
- Never use ... or placeholders in code blocks
- Keep explanations in plain text outside code blocks"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text