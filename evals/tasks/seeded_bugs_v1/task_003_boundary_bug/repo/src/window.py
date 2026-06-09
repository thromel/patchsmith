def moving_average(values: list[float], window: int) -> list[float]:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(values) <= window:
        return []
    return [
        sum(values[index : index + window]) / window
        for index in range(0, len(values) - window + 1)
    ]

