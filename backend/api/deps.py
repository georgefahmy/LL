from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

from ..config import AppSettings
from ..core.auth import (
    AccessGateCodec,
    DesktopKeychainStore,
    LLSessionData,
    SessionCookieCodec,
)
from ..core.browser_session import (
    INTERACTIVE_BROWSER_SENTINEL,
    BrowserBackedLLClient,
    InteractiveBrowserManager,
)
from ..core.cache import CacheStore
from ..core.http_client import LLAuthExpiredError, LLHttpClient, TokenBucketRateLimiter
from ..core.scrapers.seasons import SeasonSyncWorker
from .security import AuthRateLimiter, is_request_https

SESSION_COOKIE_NAME = "ll_session"
GATE_COOKIE_NAME = "ll_gate"


@dataclass
class AppState:
    settings: AppSettings
    cache: CacheStore
    rate_limiter: TokenBucketRateLimiter
    auth_rate_limiter: AuthRateLimiter
    session_codec: SessionCookieCodec
    gate_codec: AccessGateCodec
    keychain: DesktopKeychainStore
    sync_worker: SeasonSyncWorker
    browser_manager: InteractiveBrowserManager


def get_app_state(request: Request) -> AppState:
    return request.app.state.ll


def require_access_gate(
    request: Request,
    state: AppState = Depends(get_app_state),
) -> None:
    if not state.settings.access_code:
        return
    token = request.cookies.get(GATE_COOKIE_NAME, "")
    if not state.gate_codec.verify_token(token):
        raise HTTPException(
            status_code=403,
            detail="Access code required",
            headers={"X-LL-Error-Code": "ACCESS_GATE_REQUIRED"},
        )


def get_optional_session(
    request: Request,
    state: AppState = Depends(get_app_state),
) -> LLSessionData | None:
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    if not token:
        return None
    return state.session_codec.decode(token)


def require_ll_session(
    session: LLSessionData | None = Depends(get_optional_session),
) -> LLSessionData:
    if session is None:
        raise HTTPException(
            status_code=401,
            detail="LearnedLeague login required",
            headers={"X-LL-Error-Code": "LL_AUTH_REQUIRED"},
        )
    return session


def get_ll_client(
    session: LLSessionData = Depends(require_ll_session),
    state: AppState = Depends(get_app_state),
) -> Iterator[LLHttpClient | BrowserBackedLLClient]:
    if session.cookies.get(INTERACTIVE_BROWSER_SENTINEL) == "1":
        if not state.browser_manager.is_authenticated():
            raise LLAuthExpiredError(
                "Interactive browser session is no longer active. Please sign in again."
            )
        browser_client = state.browser_manager.as_client()
        try:
            yield browser_client
        finally:
            browser_client.close()
        return

    client = LLHttpClient(
        cookies=session.cookies,
        rate_limiter=state.rate_limiter,
    )
    try:
        yield client
    finally:
        client.close()


def request_is_https(request: Request) -> bool:
    return is_request_https(request)


def require_desktop_mode(state: AppState = Depends(get_app_state)) -> None:
    if state.settings.mode != "desktop":
        raise HTTPException(
            status_code=400,
            detail="Server-side personal storage is only enabled in desktop mode.",
        )
