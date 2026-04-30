from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

try:
    from tenacity import retry as tenacity_retry
    from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential
except ImportError:  # pragma: no cover - exercised only when tenacity is absent.
    tenacity_retry = None
    retry_if_exception_type = stop_after_attempt = wait_exponential = None


def retry_call(
    func: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> T:
    if tenacity_retry is not None:
        wrapped = tenacity_retry(
            reraise=True,
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=base_delay, min=base_delay, max=8),
            retry=retry_if_exception_type(exceptions),
        )(func)
        return wrapped()

    delay = base_delay
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except exceptions as exc:  # type: ignore[misc]
            last_error = exc
            if attempt >= attempts:
                break
            time.sleep(delay)
            delay = min(delay * 2, 8)
    assert last_error is not None
    raise last_error
