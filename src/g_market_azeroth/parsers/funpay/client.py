from __future__ import annotations

import time

import httpx


DEFAULT_USER_AGENT = (
    "G-Market-Azeroth-FunPayParser/0.1 "
    "(price research tool; no credentials)"
)
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class FunPayClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        user_agent: str = DEFAULT_USER_AGENT,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    def get_text(self, url: str) -> str:
        headers = {"User-Agent": self._user_agent}
        with httpx.Client(
            timeout=self._timeout_seconds,
            headers=headers,
            follow_redirects=True,
        ) as client:
            response = self._request_with_retry(client, url)
            response.raise_for_status()
            return response.text

    def _request_with_retry(self, client: httpx.Client, url: str) -> httpx.Response:
        attempts = self._max_retries + 1
        for attempt in range(attempts):
            response = client.get(url)
            if response.status_code not in RETRY_STATUS_CODES or attempt == attempts - 1:
                return response

            time.sleep(self._retry_delay(attempt, response.headers.get("Retry-After")))

        raise RuntimeError("unreachable retry state")

    def _retry_delay(self, attempt: int, retry_after_header: str | None) -> float:
        retry_after = _parse_retry_after(retry_after_header)
        if retry_after is not None:
            return retry_after

        return self._retry_backoff_seconds * (2**attempt)


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None

    try:
        delay = float(value)
    except ValueError:
        return None

    return delay if delay >= 0 else None
