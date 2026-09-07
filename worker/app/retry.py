from typing import Callable, TypeVar


T = TypeVar("T")


def retry_call(
    operation: Callable[[], T],
    *,
    attempts: int,
    initial_delay: float,
    max_delay: float,
    sleep: Callable[[float], None],
    random_value: Callable[[], float],
) -> T:
    for retry_index in range(attempts):
        try:
            return operation()
        except Exception:
            if retry_index == attempts - 1:
                raise
            base = min(max_delay, initial_delay * 2**retry_index)
            sleep(min(max_delay, base * (1 + 0.25 * random_value())))

    raise RuntimeError("retry_call requires at least one attempt")
