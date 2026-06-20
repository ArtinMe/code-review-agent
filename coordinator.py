def run_coordinator(code: str, security_report: str, correctness_report: str, readability_report: str, client) -> str:
    prompt = f"""You are a senior code review coordinator.
You have received three specialist reports about the following code.
Your job is to synthesize them into one clear, prioritized, actionable report.

ORIGINAL CODE:
{code}

SECURITY REPORT:
{security_report}

CORRECTNESS REPORT:
{correctness_report}

READABILITY REPORT:
{readability_report}

Please provide a final unified report with:
1. Overall code health score (0-10)
2. Top 3 most critical issues to fix immediately
3. Summary of all issues grouped by category (Security, Correctness, Readability)
4. Quick wins — easy things the developer can fix right away
5. Final recommendation in 2-3 sentences

Be concise, direct, and actionable. A developer should be able to read this and know exactly what to do next."""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text
