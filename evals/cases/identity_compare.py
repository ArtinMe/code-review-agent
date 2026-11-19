def describe(status: str) -> str:
    code = status.strip().lower()
    if code is "active":
        return "Account is active"
    if code == "suspended":
        return "Account is suspended"
    return "Unknown status"
