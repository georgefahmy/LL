from __future__ import annotations

import random
import threading
import time
from urllib.parse import urljoin, urlparse

import httpx

from .constants import (
    ALLOWED_IMAGE_HOSTS,
    DEFAULT_BROWSER_HEADERS,
    MAX_IMAGE_BYTES,
)


class LLError(Exception):
    """Base error for LearnedLeague operations."""


class LLNetworkError(LLError):
    """Network or upstream HTTP error communicating with LearnedLeague."""


class LLRateLimitError(LLError):
    """Rate limit or anti-bot challenge encountered."""


class LLAuthExpiredError(LLError):
    """Authenticated LearnedLeague session has expired or is missing."""


class LLAuthFailedError(LLError):
    """LearnedLeague login failed (invalid credentials or cookie)."""


class LLParseError(LLError):
    """Unexpected HTML layout encountered while parsing LearnedLeague."""


class LLNotFoundError(LLError):
    """Requested resource or player was not found on LearnedLeague."""


class LLInvalidUrlError(LLError):
    """Invalid or disallowed URL provided."""


class TokenBucketRateLimiter:
    """Thread-safe minimum-interval rate limiter for outbound requests."""

    def __init__(self, rate_per_sec: float = 2.0) -> None:
        self._min_interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0.0
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def acquire(self) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            if now < self._next_allowed:
                sleep_for = self._next_allowed - now
                self._next_allowed += self._min_interval
            else:
                sleep_for = 0.0
                self._next_allowed = now + self._min_interval
        if sleep_for > 0:
            time.sleep(sleep_for)


_WAF_MARKERS = (
    "cf-browser-verification",
    "attention required! | cloudflare",
    "just a moment...",
    "enable javascript and cookies to continue",
)

_LOGIN_PROMPT_MARKERS = (
    "ucp.php?mode=login",
    "please log in to view",
    "you must be logged in",
)

_RETRY_STATUSES = {429, 500, 502, 503, 504}


class LLHttpClient:
    """Isolated, timeout-enforced, rate-limited HTTP client for LearnedLeague."""

    def __init__(
        self,
        cookies: dict[str, str] | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
        transport: httpx.BaseTransport | None = None,
        max_retries: int = 3,
    ) -> None:
        self._rate_limiter = rate_limiter or TokenBucketRateLimiter(2.0)
        self._max_retries = max(1, max_retries)
        timeout = httpx.Timeout(connect=10.0, read=25.0, write=10.0, pool=10.0)
        client_kwargs: dict = {
            "headers": DEFAULT_BROWSER_HEADERS.copy(),
            "timeout": timeout,
            "follow_redirects": True,
        }
        if cookies:
            client_kwargs["cookies"] = cookies
        if transport is not None:
            client_kwargs["transport"] = transport
        self._client = httpx.Client(**client_kwargs)

    def __enter__(self) -> LLHttpClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    @property
    def cookies(self) -> dict[str, str]:
        return {str(k): str(v) for k, v in self._client.cookies.items() if v}

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None = None,
        follow_redirects: bool | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            self._rate_limiter.acquire()
            try:
                kwargs: dict = {}
                if data is not None:
                    kwargs["data"] = data
                if follow_redirects is not None:
                    kwargs["follow_redirects"] = follow_redirects
                if extra_headers:
                    kwargs["headers"] = extra_headers
                resp = self._client.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt + 1 < self._max_retries:
                    self._backoff(attempt)
                    continue
                raise LLNetworkError(f"Network error contacting LearnedLeague: {exc}") from exc

            if resp.status_code in _RETRY_STATUSES:
                if attempt + 1 < self._max_retries:
                    self._backoff(attempt)
                    continue
                if resp.status_code == 429:
                    raise LLRateLimitError("LearnedLeague rate limit reached (HTTP 429).")
                raise LLNetworkError(f"LearnedLeague returned HTTP {resp.status_code}.")

            if resp.status_code == 403:
                body_lower = resp.text[:4000].lower()
                if any(marker in body_lower for marker in _WAF_MARKERS):
                    raise LLRateLimitError(
                        "Request blocked by upstream security check (HTTP 403)."
                    )
                raise LLNetworkError("Access denied by LearnedLeague (HTTP 403).")

            if resp.status_code == 404:
                raise LLNotFoundError(f"Resource not found on LearnedLeague: {url}")

            if resp.status_code >= 400:
                raise LLNetworkError(f"Unexpected HTTP {resp.status_code} from LearnedLeague.")

            return resp

        raise LLNetworkError(f"Failed after retries: {last_exc}")

    @staticmethod
    def _backoff(attempt: int) -> None:
        base = 0.5 * (2**attempt)
        time.sleep(base + random.uniform(0.0, 0.25))

    @staticmethod
    def _check_html_guards(resp: httpx.Response, *, require_auth: bool) -> None:
        body_lower = resp.text[:6000].lower()
        if any(marker in body_lower for marker in _WAF_MARKERS):
            raise LLRateLimitError("Upstream security check page encountered.")
        if require_auth:
            final_url = str(resp.url).lower()
            if "ucp.php?mode=login" in final_url or (
                'name="username"' in body_lower and 'name="password"' in body_lower
            ):
                raise LLAuthExpiredError("LearnedLeague session expired; please log in again.")
            if any(marker in body_lower for marker in _LOGIN_PROMPT_MARKERS) and (
                'class="flag"' not in body_lower and "logout" not in body_lower
            ):
                raise LLAuthExpiredError("LearnedLeague login is required for this page.")

    def get_text(self, url: str, *, require_auth: bool = False) -> str:
        resp = self._request_with_retry("GET", url)
        self._check_html_guards(resp, require_auth=require_auth)
        return resp.text

    def get_bytes(self, url: str, *, require_auth: bool = False) -> bytes:
        resp = self._request_with_retry("GET", url)
        if require_auth and "ucp.php?mode=login" in str(resp.url).lower():
            raise LLAuthExpiredError("LearnedLeague session expired; please log in again.")
        return resp.content

    def post_form(
        self,
        url: str,
        data: dict[str, str],
        extra_headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        return self._request_with_retry("POST", url, data=data, extra_headers=extra_headers)

    def fetch_raw_no_redirect(self, url: str) -> httpx.Response:
        return self._request_with_retry("GET", url, follow_redirects=False)


def validate_ll_image_url(raw_url: str) -> str:
    """Validate that an image URL is HTTPS on an allowlisted LearnedLeague host."""
    url = raw_url.strip()
    if not url:
        raise LLInvalidUrlError("Image URL is required.")
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        raise LLInvalidUrlError("Only HTTPS LearnedLeague image URLs are allowed.")
    if parsed.username or parsed.password:
        raise LLInvalidUrlError("Credentials in image URL are not permitted.")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_IMAGE_HOSTS:
        raise LLInvalidUrlError(f"Host '{host}' is not an allowed LearnedLeague image host.")
    return url


def fetch_ll_image(raw_url: str, client: LLHttpClient) -> tuple[bytes, str]:
    """Fetch an image from LearnedLeague safely with strict SSRF & MIME enforcement."""
    current_url = validate_ll_image_url(raw_url)
    for _ in range(4):
        resp = client.fetch_raw_no_redirect(current_url)
        if resp.status_code in {301, 302, 303, 307, 308}:
            location = resp.headers.get("location")
            if not location:
                raise LLNetworkError("Redirect missing Location header.")
            next_url = urljoin(current_url, location)
            current_url = validate_ll_image_url(next_url)
            continue
        content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            raise LLInvalidUrlError(
                f"Upstream response is not an image (Content-Type: {content_type or 'unknown'})."
            )
        if len(resp.content) > MAX_IMAGE_BYTES:
            raise LLInvalidUrlError("Image exceeds maximum allowed size (10 MB).")
        return resp.content, content_type
    raise LLNetworkError("Too many redirects fetching image.")
