from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ...core.auth import (
    DesktopKeychainStore,
    LLSessionData,
    login_with_cookie_header,
    login_with_credentials,
)
from ...core.browser_session import INTERACTIVE_BROWSER_SENTINEL
from ..deps import (
    GATE_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    AppState,
    get_app_state,
    get_optional_session,
    request_is_https,
    require_access_gate,
)
from ..schemas import CookieLoginRequest, GateVerifyRequest, LoginRequest
from ..security import get_client_ip

router = APIRouter(prefix="/api/auth", tags=["auth"])

_COOKIE_MAX_AGE = 7 * 86400


def _enforce_auth_guards(request: Request, state: AppState) -> None:
    if (
        state.settings.mode == "web"
        and state.settings.enforce_https
        and not request_is_https(request)
    ):
        raise HTTPException(
            status_code=400,
            detail="HTTPS is required for authentication.",
        )
    retry_after = state.auth_rate_limiter.check_and_record(get_client_ip(request))
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail=f"Too many authentication attempts. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )


def _set_session_cookie(
    response: Response,
    request: Request,
    state: AppState,
    session: LLSessionData,
) -> None:
    token = state.session_codec.encode(session)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=state.settings.is_cookie_secure(request_is_https(request)),
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )


@router.get("/gate")
def gate_status(
    request: Request,
    state: AppState = Depends(get_app_state),
) -> dict:
    required = bool(state.settings.access_code)
    unlocked = (
        True
        if not required
        else state.gate_codec.verify_token(request.cookies.get(GATE_COOKIE_NAME, ""))
    )
    return {"required": required, "unlocked": unlocked}


@router.post("/gate")
def gate_verify(
    body: GateVerifyRequest,
    request: Request,
    response: Response,
    state: AppState = Depends(get_app_state),
) -> dict:
    _enforce_auth_guards(request, state)
    if not state.gate_codec.verify_code(body.code):
        raise HTTPException(status_code=403, detail="Invalid access code.")
    response.set_cookie(
        key=GATE_COOKIE_NAME,
        value=state.gate_codec.issue_token(),
        httponly=True,
        samesite="lax",
        secure=state.settings.is_cookie_secure(request_is_https(request)),
        max_age=30 * 86400,
        path="/",
    )
    return {"unlocked": True}


@router.get("/me", dependencies=[Depends(require_access_gate)])
def auth_me(
    state: AppState = Depends(get_app_state),
    session: LLSessionData | None = Depends(get_optional_session),
) -> dict:
    keychain_avail = state.keychain.is_available() if state.settings.mode == "desktop" else False
    has_saved = (
        state.keychain.load_session() is not None
        if keychain_avail and session is None
        else False
    )
    has_legacy = (
        DesktopKeychainStore.has_legacy_login_file(state.settings.resolved_data_dir)
        if state.settings.mode == "desktop"
        else False
    )
    if session is None:
        return {
            "authenticated": False,
            "username": None,
            "formatted_username": None,
            "profile_id": None,
            "desktop_keychain_available": keychain_avail,
            "has_saved_keychain_session": has_saved,
            "has_legacy_login_file": has_legacy,
        }
    return {
        "authenticated": True,
        "username": session.username,
        "formatted_username": session.formatted_username,
        "profile_id": session.profile_id,
        "desktop_keychain_available": keychain_avail,
        "has_saved_keychain_session": has_saved,
        "has_legacy_login_file": has_legacy,
    }


@router.post("/login", dependencies=[Depends(require_access_gate)])
def auth_login(
    body: LoginRequest,
    request: Request,
    response: Response,
    state: AppState = Depends(get_app_state),
) -> dict:
    _enforce_auth_guards(request, state)
    session = login_with_credentials(
        body.username,
        body.password,
        rate_limiter=state.rate_limiter,
    )
    _set_session_cookie(response, request, state, session)
    if body.remember_me and state.settings.mode == "desktop":
        state.keychain.save_session(session)
    return {
        "authenticated": True,
        "username": session.username,
        "formatted_username": session.formatted_username,
        "profile_id": session.profile_id,
    }


@router.post("/cookie", dependencies=[Depends(require_access_gate)])
def auth_cookie_login(
    body: CookieLoginRequest,
    request: Request,
    response: Response,
    state: AppState = Depends(get_app_state),
) -> dict:
    _enforce_auth_guards(request, state)
    session = login_with_cookie_header(
        body.cookie,
        rate_limiter=state.rate_limiter,
    )
    _set_session_cookie(response, request, state, session)
    if body.remember_me and state.settings.mode == "desktop":
        state.keychain.save_session(session)
    return {
        "authenticated": True,
        "username": session.username,
        "formatted_username": session.formatted_username,
        "profile_id": session.profile_id,
    }


@router.post("/auto-login", dependencies=[Depends(require_access_gate)])
def auth_auto_login(
    request: Request,
    response: Response,
    state: AppState = Depends(get_app_state),
) -> dict:
    if state.settings.mode != "desktop":
        raise HTTPException(status_code=400, detail="Auto-login is only available in desktop mode.")
    saved = state.keychain.load_session()
    if saved is None:
        return {"authenticated": False}
    _set_session_cookie(response, request, state, saved)
    return {
        "authenticated": True,
        "username": saved.username,
        "formatted_username": saved.formatted_username,
        "profile_id": saved.profile_id,
    }


def _require_desktop_interactive(state: AppState) -> None:
    if state.settings.mode != "desktop":
        raise HTTPException(
            status_code=400,
            detail=(
                "Interactive browser login is only available in the desktop app. "
                "Use the Chrome extension on the web."
            ),
        )


@router.post("/interactive/start", dependencies=[Depends(require_access_gate)])
def auth_interactive_start(
    request: Request,
    response: Response,
    state: AppState = Depends(get_app_state),
) -> dict:
    _require_desktop_interactive(state)
    _enforce_auth_guards(request, state)
    if not state.browser_manager.is_supported():
        raise HTTPException(
            status_code=400,
            detail="Interactive browser login is not available on this host.",
        )
    try:
        status = state.browser_manager.start_or_show()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if status.get("authenticated") and status.get("profile_id"):
        pid = str(status["profile_id"])
        fname = str(status.get("formatted_username") or pid)
        uname = str(status.get("username") or fname.lower())
        session = LLSessionData(
            username=uname,
            formatted_username=fname,
            profile_id=pid,
            cookies={INTERACTIVE_BROWSER_SENTINEL: "1"},
        )
        _set_session_cookie(response, request, state, session)
        return {
            "status": "authenticated",
            "authenticated": True,
            "username": session.username,
            "formatted_username": session.formatted_username,
            "profile_id": session.profile_id,
        }

    return {"status": "waiting_for_user", "authenticated": False}


@router.get("/interactive/status", dependencies=[Depends(require_access_gate)])
def auth_interactive_status(
    request: Request,
    response: Response,
    state: AppState = Depends(get_app_state),
) -> dict:
    _require_desktop_interactive(state)
    status = state.browser_manager.get_status()
    if status.get("authenticated") and status.get("profile_id"):
        pid = str(status["profile_id"])
        fname = str(status.get("formatted_username") or pid)
        uname = str(status.get("username") or fname.lower())
        session = LLSessionData(
            username=uname,
            formatted_username=fname,
            profile_id=pid,
            cookies={INTERACTIVE_BROWSER_SENTINEL: "1"},
        )
        _set_session_cookie(response, request, state, session)
        return {
            "status": "authenticated",
            "authenticated": True,
            "username": session.username,
            "formatted_username": session.formatted_username,
            "profile_id": session.profile_id,
        }
    return {
        "status": "waiting_for_user" if status.get("running") else "stopped",
        "authenticated": False,
    }


@router.post("/logout", dependencies=[Depends(require_access_gate)])
def auth_logout(
    request: Request,
    response: Response,
    clear_keychain: bool = True,
    state: AppState = Depends(get_app_state),
) -> dict:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=state.settings.is_cookie_secure(request_is_https(request)),
    )
    if clear_keychain and state.settings.mode == "desktop":
        state.keychain.clear_session()
    state.browser_manager.shutdown()
    return {"authenticated": False}


@router.delete("/legacy-login-file", dependencies=[Depends(require_access_gate)])
def delete_legacy_login_file(state: AppState = Depends(get_app_state)) -> dict:
    if state.settings.mode != "desktop":
        raise HTTPException(status_code=400, detail="Only available in desktop mode.")
    deleted = DesktopKeychainStore.delete_legacy_login_file(state.settings.resolved_data_dir)
    return {"deleted": deleted}
