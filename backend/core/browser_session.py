from __future__ import annotations

import importlib.util
import logging
import secrets
import socket
import subprocess
import sys
import threading
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from .http_client import (
    _LOGIN_PROMPT_MARKERS,
    _WAF_MARKERS,
    LLAuthExpiredError,
    LLHttpClient,
    LLInvalidUrlError,
    LLNetworkError,
    LLNotFoundError,
    LLRateLimitError,
    TokenBucketRateLimiter,
)

logger = logging.getLogger(__name__)

INTERACTIVE_BROWSER_SENTINEL = "__ll_interactive_browser__"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def is_valid_ll_https_url(url: str) -> bool:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and host in {
        "www.learnedleague.com",
        "learnedleague.com",
    }


def validate_browser_fetch_response(
    url: str,
    *,
    ok: bool,
    status: int,
    final_url: str,
    body: str,
    require_auth: bool,
) -> str:
    """Apply the same error semantics as LLHttpClient to an in-browser fetch result."""
    if not ok and status == 0:
        raise LLNetworkError(body or f"Browser fetch failed for {url}")

    body_lower = body[:6000].lower()

    if status == 403:
        if any(marker in body_lower for marker in _WAF_MARKERS):
            raise LLRateLimitError(
                "Request blocked by upstream security check (HTTP 403). "
                "Complete the check in the LearnedLeague browser window."
            )
        raise LLNetworkError("Access denied by LearnedLeague (HTTP 403).")

    if status == 404:
        raise LLNotFoundError(f"Resource not found on LearnedLeague: {url}")

    if status >= 400:
        raise LLNetworkError(f"Unexpected HTTP {status} from LearnedLeague.")

    if any(marker in body_lower for marker in _WAF_MARKERS):
        raise LLRateLimitError(
            "Upstream security check page encountered. "
            "Complete the check in the LearnedLeague browser window."
        )

    if require_auth:
        final_lower = final_url.lower()
        if "ucp.php?mode=login" in final_lower or (
            'name="username"' in body_lower and 'name="password"' in body_lower
        ):
            raise LLAuthExpiredError("LearnedLeague session expired; please log in again.")
        if any(marker in body_lower for marker in _LOGIN_PROMPT_MARKERS) and (
            'class="flag"' not in body_lower and "logout" not in body_lower
        ):
            raise LLAuthExpiredError("LearnedLeague login is required for this page.")

    return body


class BrowserBackedLLClient:
    """Drop-in LLHttpClient-compatible adapter backed by InteractiveBrowserManager."""

    def __init__(
        self,
        manager: InteractiveBrowserManager,
        *,
        rate_limiter: TokenBucketRateLimiter | None = None,
    ) -> None:
        self._manager = manager
        self._rate_limiter = rate_limiter

    def __enter__(self) -> BrowserBackedLLClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        return

    def get_text(self, url: str, *, require_auth: bool = False) -> str:
        if self._rate_limiter is not None:
            self._rate_limiter.acquire()
        return self._manager.fetch_text(url, require_auth=require_auth)

    def get_bytes(self, url: str, *, require_auth: bool = False) -> bytes:
        if self._rate_limiter is not None:
            self._rate_limiter.acquire()
        text = self._manager.fetch_text(url, require_auth=require_auth)
        return text.encode("utf-8")


class InteractiveBrowserManager:
    """Manages a visible pywebview subprocess for interactive LL sign-in and fetches."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._proc: subprocess.Popen[bytes] | None = None
        self._port: int | None = None
        self._token: str = ""
        self._cached_auth: dict[str, Any] = {
            "authenticated": False,
            "username": None,
            "formatted_username": None,
            "profile_id": None,
        }

    @staticmethod
    def is_supported() -> bool:
        return importlib.util.find_spec("webview") is not None

    def _headers(self) -> dict[str, str]:
        return {"X-Bridge-Token": self._token}

    def _base_url(self) -> str:
        if self._port is None:
            raise LLNetworkError("Interactive browser session is not running.")
        return f"http://127.0.0.1:{self._port}"

    def _reset_state(self) -> None:
        self._proc = None
        self._port = None
        self._token = ""
        self._cached_auth = {
            "authenticated": False,
            "username": None,
            "formatted_username": None,
            "profile_id": None,
        }

    def _poll_worker_status(self) -> dict[str, Any] | None:
        if self._proc is None or self._proc.poll() is not None:
            self._reset_state()
            return None
        try:
            resp = httpx.get(
                f"{self._base_url()}/status",
                headers=self._headers(),
                timeout=3.0,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("authenticated"):
                self._cached_auth = {
                    "authenticated": True,
                    "username": data.get("username"),
                    "formatted_username": data.get("formatted_username"),
                    "profile_id": data.get("profile_id"),
                }
            return data
        except Exception:
            return None

    def start_or_show(self) -> dict[str, Any]:
        with self._lock:
            if not self.is_supported():
                raise RuntimeError(
                    "Interactive browser login requires pywebview, which is not installed."
                )

            if self._proc is not None and self._proc.poll() is None:
                status = self._poll_worker_status()
                if status and status.get("authenticated"):
                    return {"status": "authenticated", **status}
                try:
                    httpx.post(
                        f"{self._base_url()}/show",
                        headers=self._headers(),
                        timeout=3.0,
                    )
                except Exception:
                    pass
                return {"status": "waiting_for_user", "authenticated": False}

            self._reset_state()
            port = _find_free_port()
            token = secrets.token_urlsafe(24)
            if getattr(sys, "frozen", False):
                cmd = [
                    sys.executable,
                    "--ll-browser-worker",
                    "--port",
                    str(port),
                    "--token",
                    token,
                ]
            else:
                cmd = [
                    sys.executable,
                    "-m",
                    "backend.core.browser_worker",
                    "--port",
                    str(port),
                    "--token",
                    token,
                ]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._proc = proc
            self._port = port
            self._token = token

            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    self._reset_state()
                    raise RuntimeError("Interactive login window exited unexpectedly.")
                status = self._poll_worker_status()
                if status is not None:
                    if status.get("authenticated"):
                        return {"status": "authenticated", **status}
                    return {"status": "waiting_for_user", "authenticated": False}
                time.sleep(0.2)

            return {"status": "waiting_for_user", "authenticated": False}

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._reset_state()
                return {"running": False, "authenticated": False}
            data = self._poll_worker_status()
            if data is None:
                return {"running": False, "authenticated": False}
            return data

    def is_authenticated(self) -> bool:
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._reset_state()
                return False
            if self._cached_auth.get("authenticated"):
                return True
            data = self._poll_worker_status()
            return bool(data and data.get("authenticated"))

    def fetch_text(self, url: str, *, require_auth: bool = False) -> str:
        if not is_valid_ll_https_url(url):
            raise LLInvalidUrlError(f"Disallowed URL for LearnedLeague fetch: {url}")

        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._reset_state()
                raise LLAuthExpiredError(
                    "Interactive browser session is no longer running. Please sign in again."
                )
            base_url = self._base_url()
            headers = self._headers()

        try:
            resp = httpx.post(
                f"{base_url}/fetch",
                headers=headers,
                json={"url": url, "require_auth": require_auth},
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            raise LLNetworkError(f"Interactive browser bridge error: {exc}") from exc

        if resp.status_code == 400:
            raise LLInvalidUrlError(resp.json().get("detail", "Invalid URL."))
        if resp.status_code >= 400:
            raise LLNetworkError(f"Interactive browser fetch failed (HTTP {resp.status_code}).")

        payload = resp.json()
        return validate_browser_fetch_response(
            url,
            ok=bool(payload.get("ok", False)),
            status=int(payload.get("status", 0)),
            final_url=str(payload.get("final_url", url)),
            body=str(payload.get("body", "")),
            require_auth=require_auth,
        )

    def as_client(
        self,
        *,
        rate_limiter: TokenBucketRateLimiter | None = None,
    ) -> BrowserBackedLLClient:
        return BrowserBackedLLClient(self, rate_limiter=rate_limiter)

    def shutdown(self) -> None:
        with self._lock:
            proc = self._proc
            port = self._port
            token = self._token
            self._reset_state()

        if proc is None:
            return
        if port is not None and token:
            try:
                httpx.post(
                    f"http://127.0.0.1:{port}/shutdown",
                    headers={"X-Bridge-Token": token},
                    timeout=1.5,
                )
            except Exception:
                pass
        try:
            proc.wait(timeout=2.0)
        except Exception:
            try:
                proc.terminate()
                proc.wait(timeout=2.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


def build_ll_client(
    rate_limiter: TokenBucketRateLimiter,
    browser_manager: Any | None = None,
) -> LLHttpClient | BrowserBackedLLClient:
    """Return a browser-backed client when interactively authenticated, else LLHttpClient."""
    if browser_manager is not None and browser_manager.is_authenticated():
        return browser_manager.as_client(rate_limiter=rate_limiter)
    return LLHttpClient(rate_limiter=rate_limiter)
