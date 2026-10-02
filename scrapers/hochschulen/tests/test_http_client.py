"""Retries of the shared HTTP layer, against a local server (no network)."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests
from urllib3.response import HTTPResponse

from registry import http_client


class Script:
    """Status codes the server answers with, in order; the last one repeats."""

    def __init__(self):
        self.statuses = [200]
        self.seen = []


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(http_client, "BACKOFF_SECONDS", (0, 0, 0))
    script = Script()

    class Handler(BaseHTTPRequestHandler):
        def _answer(self):
            script.seen.append(self.command)
            index = min(len(script.seen) - 1, len(script.statuses) - 1)
            status = script.statuses[index]
            body = f"status {status}".encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = _answer
        do_POST = _answer

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    http_client.STATS.reset()

    yield script, f"http://127.0.0.1:{httpd.server_address[1]}/"

    httpd.shutdown()
    httpd.server_close()


def test_temporary_5xx_is_retried_until_success(server):
    script, url = server
    script.statuses = [503, 502, 200]

    response = http_client.get(url, timeout=5)

    assert response.status_code == 200
    assert len(script.seen) == 3
    assert http_client.STATS.snapshot() == {"request_attempts": 3, "request_retries": 2}


def test_rate_limit_429_is_retried(server):
    script, url = server
    script.statuses = [429, 200]

    assert http_client.get(url, timeout=5).status_code == 200
    assert len(script.seen) == 2


def test_gives_up_after_three_attempts_and_returns_the_last_answer(server):
    script, url = server
    script.statuses = [503]

    response = http_client.get(url, timeout=5)

    # Adapters keep their raise_for_status() -> same exception type as before.
    assert response.status_code == 503
    with pytest.raises(requests.HTTPError):
        response.raise_for_status()
    assert len(script.seen) == 3
    assert http_client.STATS.attempts == 3


def test_permanent_4xx_is_not_retried(server):
    script, url = server
    script.statuses = [404]

    assert http_client.get(url, timeout=5).status_code == 404
    assert len(script.seen) == 1


def test_post_is_not_retried(server):
    script, url = server
    script.statuses = [503, 200]

    with http_client.session() as s:
        assert s.post(url, data={"a": 1}, timeout=5).status_code == 503
    assert script.seen == ["POST"]


def test_retry_false_only_counts(server):
    script, url = server
    script.statuses = [503, 200]

    assert http_client.get(url, retry=False, timeout=5).status_code == 503
    assert len(script.seen) == 1
    assert http_client.STATS.snapshot() == {"request_attempts": 1, "request_retries": 0}


def test_connection_error_is_retried_then_raised(monkeypatch):
    monkeypatch.setattr(http_client, "BACKOFF_SECONDS", (0, 0, 0))
    http_client.STATS.reset()

    # Nothing listens on port 9 (discard) on 127.0.0.1 in the test environment.
    with pytest.raises(requests.ConnectionError):
        http_client.get("http://127.0.0.1:9/", timeout=2)

    assert http_client.STATS.attempts == 3


def test_backoff_schedule_is_2_then_5_then_10_seconds():
    retry = http_client.make_retry()

    assert retry.get_backoff_time() == 0
    assert retry.new(history=("x",)).get_backoff_time() == 2
    assert retry.new(history=("x", "x")).get_backoff_time() == 5
    assert retry.new(history=("x", "x", "x")).get_backoff_time() == 10
    assert retry.new(history=("x",) * 5).get_backoff_time() == 10


def test_retry_after_header_is_capped():
    retry = http_client.make_retry()
    response = HTTPResponse(body=b"", headers={"Retry-After": "3600"}, status=429)

    assert retry.get_retry_after(response) == http_client.RETRY_AFTER_CAP_SECONDS
