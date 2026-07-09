"""Shared utilities: retry decorator, timing helpers, platform detection."""

from __future__ import annotations

import functools
import platform
import time
from dataclasses import dataclass
from typing import Callable, Iterable, ParamSpec, TypeVar

from loguru import logger

P = ParamSpec("P")
T = TypeVar("T")


class Platform:
    """Lightweight OS detection helpers."""

    @staticmethod
    def is_windows() -> bool:
        return platform.system() == "Windows"

    @staticmethod
    def is_macos() -> bool:
        return platform.system() == "Darwin"

    @staticmethod
    def is_linux() -> bool:
        return platform.system() == "Linux"

    @staticmethod
    def name() -> str:
        return platform.system()


def retry(
    attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Retry a callable on failure.

    Args:
        attempts: Total number of attempts (>= 1).
        delay: Seconds to wait before the first retry.
        backoff: Multiplier applied to the delay after each failed attempt.
        exceptions: Exception types that trigger a retry.

    Returns:
        A decorator that retries the wrapped function.
    """
    attempts = max(1, attempts)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            current_delay = delay
            last_exc: Exception | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:  # noqa: BLE001 - deliberate broad retry
                    last_exc = exc
                    if attempt >= attempts:
                        break
                    logger.warning(
                        "Attempt {}/{} for '{}' failed: {}. Retrying in {:.1f}s...",
                        attempt,
                        attempts,
                        func.__name__,
                        exc,
                        current_delay,
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator


@dataclass
class Stopwatch:
    """Context-manager stopwatch reporting elapsed seconds."""

    label: str = "operation"
    elapsed: float = 0.0
    _start: float = 0.0

    def __enter__(self) -> "Stopwatch":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.elapsed = time.perf_counter() - self._start


def chunked(items: Iterable[T], size: int) -> Iterable[list[T]]:
    """Yield successive ``size``-length chunks from ``items``."""
    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
