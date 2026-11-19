def add_tag(item: dict, tag: str, tags: list = []) -> dict:
    tags.append(tag)
    item["tags"] = tags
    return item


def tag_all(items: list[dict], tag: str) -> list[dict]:
    return [add_tag(item, tag) for item in items]
