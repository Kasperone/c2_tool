import random
import time


def jittered_sleep(base_seconds: float, jitter_percent: int = 20):
    """Sleep for base_seconds ± jitter_percent%.
    Example: base=60, jitter=20 -> sleep between 48s and 72s.
    """
    if base_seconds <= 0:
        return
    variance = base_seconds * (jitter_percent / 100.0)
    actual = base_seconds + random.uniform(-variance, variance)
    actual = max(0.1, actual)
    time.sleep(actual)
