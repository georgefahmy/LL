from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_NO_STORE_PREFIXES = (
    "/api/auth/",
    "/api/players/",
    "/api/defense/",
    "/api/luck/",
)

_BASE_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


def is_request_https(request: Request) -> bool:
    proto_hdr = request.headers.get("x-forwarded-proto", "")
    if proto_hdr:
        first_proto = proto_hdr.split(",")[0].strip().lower()
        return first_proto == "https"
    return request.url.scheme.lower() == "https"


def get_client_ip(request: Request) -> str:
    cf_ip = request.headers.get("cf-connecting-ip", "").strip()
    if cf_ip:
        return cf_ip
    xff = request.headers.get("x-forwarded-for", "").strip()
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class AuthRateLimiter:
    """Thread-safe sliding-window rate limiter per client IP for auth endpoints."""

    def __init__(self, max_attempts: int = 10, window_seconds: int = 300) -> None:
        self._max_attempts = max(1, max_attempts)
        self._window = max(1, window_seconds)
        self._lock = threading.Lock()
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def check_and_record(self, client_ip: str) -> int | None:
        """Record an attempt. Returns retry-after seconds if rate-limited, else None."""
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            dq = self._attempts[client_ip]
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= self._max_attempts:
                retry_after = max(1, math.ceil(dq[0] + self._window - now))
                return retry_after
            dq.append(now)
            return None


def _normalize_host_header(raw_host: str, scheme: str) -> str:
    host = raw_host.split(",")[0].strip().lower()
    if not host:
        return ""
    default_port = ":443" if scheme == "https" else ":80"
    if host.endswith(default_port):
        return host[: -len(default_port)]
    return host


def _normalize_origin_host(origin: str) -> tuple[str, str] | None:
    parsed = urlparse(origin)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        return None
    hostname = parsed.hostname.lower()
    port = parsed.port
    if port is None or (scheme == "https" and port == 443) or (scheme == "http" and port == 80):
        return scheme, hostname
    return scheme, f"{hostname}:{port}"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach strict CSP, clickjacking, MIME, referrer, HSTS, and cache-control headers."""

    def __init__(self, app, *, mode: str) -> None:
        super().__init__(app)
        self._mode = mode

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        https = is_request_https(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )

        csp = _BASE_CSP
        if self._mode == "web" and https:
            csp = f"{_BASE_CSP}; upgrade-insecure-requests"
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        response.headers.setdefault("Content-Security-Policy", csp)

        path = request.url.path
        if any(path.startswith(prefix) for prefix in _NO_STORE_PREFIXES):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"

        return response


class CsrfOriginMiddleware(BaseHTTPMiddleware):
    """Reject cross-site mutating browser requests to /api/*."""

    async def dispatch(self, request: Request, call_next):
        if request.method in _MUTATING_METHODS and request.url.path.startswith("/api/"):
            sec_fetch_site = request.headers.get("sec-fetch-site", "").strip().lower()
            if sec_fetch_site == "cross-site":
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Cross-site request rejected.", "code": "CSRF_REJECTED"},
                )

            origin = request.headers.get("origin", "").strip()
            if origin:
                parsed_origin = _normalize_origin_host(origin)
                if parsed_origin is None:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Invalid Origin header.", "code": "CSRF_REJECTED"},
                    )
                origin_scheme, origin_host = parsed_origin
                raw_req_host = (
                    request.headers.get("x-forwarded-host")
                    or request.headers.get("host")
                    or ""
                )
                req_scheme = "https" if is_request_https(request) else "http"
                expected_host = _normalize_host_header(raw_req_host, req_scheme)
                if expected_host and origin_host != expected_host:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": "Origin mismatch rejected.",
                            "code": "CSRF_REJECTED",
                        },
                    )
                # Ensure scheme downgrades aren't accepted when behind HTTPS
                if req_scheme == "https" and origin_scheme != "https":
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": "HTTPS Origin required.",
                            "code": "CSRF_REJECTED",
                        },
                    )

        return await call_next(request)


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds configured limit."""

    def __init__(self, app, *, max_bytes: int) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        cl_raw = request.headers.get("content-length", "").strip()
        if cl_raw:
            try:
                if int(cl_raw) > self._max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": "Request payload too large.",
                            "code": "PAYLOAD_TOO_LARGE",
                        },
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header."},
                )
        return await call_next(request)
