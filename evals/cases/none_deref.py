USERS = {
    "ada": {"email": "ada@example.com", "plan": "pro"},
    "linus": {"email": "linus@example.com", "plan": "free"},
}


def plan_label(username: str) -> str:
    user = USERS.get(username)
    return user["plan"].upper()
