from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ...core.auth import DesktopKeychainStore
from ...core.constants import CATEGORIES, LUCK_FIELDS, MODKOS_URL, STATS_DEFINITION
from ...core.updater import check_latest_release
from ..deps import GATE_COOKIE_NAME, AppState, get_app_state

router = APIRouter(prefix="/api", tags=["health"])


def _active_version(state: AppState) -> str:
    return (
        state.settings.extension_version
        if state.settings.mode == "web"
        else state.settings.app_version
    )


@router.get("/health")
def health(state: AppState = Depends(get_app_state)) -> dict:
    return {
        "status": "ok",
        "version": _active_version(state),
        "extension_version": state.settings.extension_version,
        "mode": state.settings.mode,
    }


@router.get("/meta")
def metadata(
    request: Request,
    state: AppState = Depends(get_app_state),
) -> dict:
    gate_required = bool(state.settings.access_code)
    gate_unlocked = (
        True
        if not gate_required
        else state.gate_codec.verify_token(request.cookies.get(GATE_COOKIE_NAME, ""))
    )
    active_ver = _active_version(state)

    if state.settings.disable_update_check or state.settings.mode == "web":
        update_info = {
            "current_version": active_ver,
            "latest_version": active_ver,
            "update_available": False,
            "release_url": f"https://github.com/{state.settings.github_repo}/releases/latest",
        }
    else:
        update_info = check_latest_release(
            active_ver,
            state.settings.github_repo,
        )

    latest_season_str = state.cache.get_meta("latest_season")
    current_day_str = state.cache.get_meta("current_day")
    max_cached_season, max_cached_day = state.cache.get_max_season_day()

    latest_season = int(latest_season_str) if latest_season_str else max_cached_season
    current_day = int(current_day_str) if current_day_str else max_cached_day

    has_legacy_login = (
        DesktopKeychainStore.has_legacy_login_file(state.settings.resolved_data_dir)
        if state.settings.mode == "desktop"
        else False
    )

    return {
        "mode": state.settings.mode,
        "version": active_ver,
        "extension_version": state.settings.extension_version,
        "update": update_info,
        "question_count": state.cache.count_questions(),
        "latest_season": latest_season,
        "current_day": current_day,
        "sync_status": state.sync_worker.status(),
        "access_gate_required": gate_required,
        "access_gate_unlocked": gate_unlocked,
        "has_legacy_login_file": has_legacy_login,
        "categories": CATEGORIES,
        "luck_fields": LUCK_FIELDS,
        "stats_definition": STATS_DEFINITION,
        "modkos_url": MODKOS_URL,
    }
