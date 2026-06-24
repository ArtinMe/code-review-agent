def run_refactor_agent(code: str, client) -> str:
    prompt = f"""You are an expert code refactoring specialist.
Your job is to rewrite the following code to be cleaner, more readable, and more maintainable without changing its core functionality.

Code to refactor:
{code}

Rules:
- Keep the same logic and functionality
- Improve variable and function naming
- Add clear, concise comments
- Remove redundant code
- Apply best practices for the language
- Only return the refactored code inside a python code block
- No explanations outside the code block
- Never use ... or placeholders"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text