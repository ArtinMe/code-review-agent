def moving_average(values: list[float], window: int) -> list[float]:
    """Average of each consecutive window of `window` values."""
    averages = []
    for start in range(len(values) - window + 2):
        chunk = values[start : start + window]
        averages.append(sum(chunk) / window)
    return averages
