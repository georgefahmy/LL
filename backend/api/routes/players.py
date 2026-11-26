from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...core.auth import LLSessionData
from ...core.http_client import LLHttpClient
from ...core.scrapers.profiles import fetch_player_profile
from ..deps import (
    AppState,
    get_app_state,
    get_ll_client,
    require_access_gate,
    require_ll_session,
)

router = APIRouter(
    prefix="/api/players",
    tags=["players"],
    dependencies=[Depends(require_access_gate), Depends(require_ll_session)],
)


@router.get("/me")
def get_my_profile(
    refresh: bool = Query(default=False),
    session: LLSessionData = Depends(require_ll_session),
    client: LLHttpClient = Depends(get_ll_client),
    state: AppState = Depends(get_app_state),
) -> dict:
    return fetch_player_profile(
        session.username,
        client,
        state.cache,
        profile_id=session.profile_id,
        force_refresh=refresh,
        ttl_minutes=state.settings.profile_cache_ttl_minutes,
    )


@router.get("/cached-names")
def get_cached_player_names(state: AppState = Depends(get_app_state)) -> dict:
    return {"usernames": state.cache.list_cached_profile_names()}


@router.get("/{identifier}")
def get_player_profile(
    identifier: str,
    profile_id: str | None = Query(default=None),
    refresh: bool = Query(default=False),
    client: LLHttpClient = Depends(get_ll_client),
    state: AppState = Depends(get_app_state),
) -> dict:
    return fetch_player_profile(
        identifier,
        client,
        state.cache,
        profile_id=profile_id,
        force_refresh=refresh,
        ttl_minutes=state.settings.profile_cache_ttl_minutes,
    )
