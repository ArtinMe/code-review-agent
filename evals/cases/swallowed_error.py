import json


def load_settings(path: str) -> dict:
    settings = {"retries": 3, "timeout": 30}
    try:
        with open(path) as f:
            settings.update(json.load(f))
    except:
        pass
    return settings
