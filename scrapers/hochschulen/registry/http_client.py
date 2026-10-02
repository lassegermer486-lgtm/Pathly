"""
Shared HTTP layer for the state adapters (v1.3, reliability).

Only transport: retries, backoff and request counting. Fetching, navigation
and parsing stay in the state adapters.

    session()          drop-in for requests.Session()
    get(url, **kw)     drop-in for requests.get(url, **kw)

A request is tried at most 3 times; between attempts we wait 2 s, then 5 s.
Retried: connection errors, timeouts, 429 and temporary 5xx answers, for
GET/HEAD only. Not retried: 4xx answers, parser errors, POSTs.
After the last attempt the final answer is returned unchanged, so the
adapters' own raise_for_status() / except requests.RequestException
behave as before.

Adapters that already retry on their own (Hamburg, Schleswig-Holstein) use
retry=False: their requests are counted, but not multiplied.
"""

from __future__ import annotations

import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ATTEMPTS = 3
BACKOFF_SECONDS = (2, 5, 10)
RETRY_STATUS = (429, 500, 502, 503, 504)
# A Retry-After header is honoured, but we never wait longer than this.
RETRY_AFTER_CAP_SECONDS = 30


class RequestStats:
    """Requests of the current state run (reset by registry.run per state)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with self._lock:
            self.requests = 0
            self.retries = 0

    def add(self, requests_=0, retries=0):
        with self._lock:
            self.requests += requests_
            self.retries += retries

    @property
    def attempts(self) -> int:
        return self.requests + self.retries

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "request_attempts": self.requests + self.retries,
                "request_retries": self.retries,
            }


STATS = RequestStats()


class _ScheduledRetry(Retry):
    """urllib3 Retry with the fixed 2 s / 5 s / 10 s schedule and counting."""

    def get_backoff_time(self) -> float:
        done = len(self.history)
        if done == 0:
            return 0
        return BACKOFF_SECONDS[min(done, len(BACKOFF_SECONDS)) - 1]

    def get_retry_after(self, response):
        seconds = super().get_retry_after(response)
        if seconds is None:
            return None
        return min(seconds, RETRY_AFTER_CAP_SECONDS)

    def increment(self, *args, **kwargs):
        # Raises MaxRetryError when exhausted: then no further attempt follows.
        new = super().increment(*args, **kwargs)
        STATS.add(retries=1)
        return new


def make_retry(attempts: int = ATTEMPTS) -> Retry:
    retries = attempts - 1
    return _ScheduledRetry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        other=0,
        redirect=None,
        status_forcelist=RETRY_STATUS,
        allowed_methods=frozenset({"GET", "HEAD"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )


class _CountingAdapter(HTTPAdapter):
    def send(self, request, *args, **kwargs):
        STATS.add(requests_=1)
        return super().send(request, *args, **kwargs)


def session(retry: bool = True) -> requests.Session:
    """A requests.Session whose GETs are retried (retry=False: only counted)."""
    s = requests.Session()
    adapter = _CountingAdapter(max_retries=make_retry() if retry else 0)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def get(url: str, retry: bool = True, **kwargs) -> requests.Response:
    """requests.get with retries: a fresh session per call, as requests.get does."""
    with session(retry=retry) as s:
        return s.get(url, **kwargs)
