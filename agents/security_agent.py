def run_security_agent(code: str, client) -> str:
    prompt = f"""You are a security code review expert.
Analyze the following code for security vulnerabilities.
Look for:
- SQL injection risks
- Exposed API keys or passwords
- Unsafe user input handling
- Insecure dependencies
- Authentication/authorization issues

Code to review:
{code}

Provide a clear, structured security report with:
1. List of security issues found (if any)
2. Severity level for each (High/Medium/Low)
3. Brief explanation of each issue
4. Suggested fix for each issue

If no issues found, state that the code looks secure."""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text
