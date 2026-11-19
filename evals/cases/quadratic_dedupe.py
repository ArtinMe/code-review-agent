def unique_emails(rows: list[dict]) -> list[str]:
    """Rows can number in the hundreds of thousands."""
    seen: list[str] = []
    for row in rows:
        email = row["email"].strip().lower()
        if email not in seen:
            seen.append(email)
    return seen
