def run_correctness_agent(code: str, client) -> str:
    prompt = f"""You are a code correctness expert.
Analyze the following code for bugs and logical errors.
Look for:
- Logic errors and wrong assumptions
- Edge cases that aren't handled
- Infinite loops or recursion issues
- Wrong variable usage
- Off-by-one errors
- Null/None reference issues

Code to review:
{code}

Provide a clear, structured correctness report with:
1. List of bugs or logical errors found (if any)
2. Severity level for each (High/Medium/Low)
3. Brief explanation of each issue
4. Suggested fix for each issue

If no issues found, state that the code logic looks correct."""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text
