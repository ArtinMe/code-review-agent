def run_readability_agent(code: str, client) -> str:
    prompt = f"""You are a code readability and style expert.
Analyze the following code for readability and maintainability issues.
Look for:
- Poor variable and function naming
- Missing or inadequate comments
- Functions that are too long or complex
- Code duplication
- Inconsistent formatting or style
- Hard to understand logic that needs clarification

Code to review:
{code}

Provide a clear, structured readability report with:
1. List of readability issues found (if any)
2. Severity level for each (High/Medium/Low)
3. Brief explanation of each issue
4. Suggested improvement for each issue

If no issues found, state that the code is clean and readable."""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text
