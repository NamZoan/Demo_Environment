import pytest

from app.retry import retry_call


def test_retry_call_retries_until_success_with_bounded_backoff():
    attempts = []
    delays = []

    def operation():
        attempts.append(len(attempts) + 1)
        if len(attempts) < 3:
            raise OSError("temporary failure")
        return "ok"

    result = retry_call(
        operation,
        attempts=4,
        initial_delay=1.0,
        max_delay=3.0,
        sleep=delays.append,
        random_value=lambda: 1.0,
    )

    assert result == "ok"
    assert attempts == [1, 2, 3]
    assert delays == [1.25, 2.5]


def test_retry_call_reraises_the_last_error_after_total_attempt_limit():
    delays = []

    def operation():
        raise TimeoutError("database unavailable")

    with pytest.raises(TimeoutError, match="database unavailable"):
        retry_call(
            operation,
            attempts=3,
            initial_delay=2.0,
            max_delay=2.5,
            sleep=delays.append,
            random_value=lambda: 1.0,
        )

    assert delays == [2.5, 2.5]
