from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...core.scrapers.minileagues import fetch_minileague_detail, fetch_minileagues_catalog
from ..deps import AppState, get_app_state, require_access_gate

router = APIRouter(
    prefix="/api/minileagues",
    tags=["minileagues"],
    dependencies=[Depends(require_access_gate)],
)


@router.get("")
def list_minileagues(
    search: str = Query(default=""),
    refresh: bool = Query(default=False),
    state: AppState = Depends(get_app_state),
) -> dict:
    items = fetch_minileagues_catalog(
        state.cache,
        state.rate_limiter,
        force=refresh,
        browser_manager=state.browser_manager,
    )
    if search.strip():
        needle = search.strip().lower()
        items = [it for it in items if needle in it["title"].lower()]
    return {"items": items, "total": len(items)}


@router.get("/{slug}")
def get_minileague(slug: str, state: AppState = Depends(get_app_state)) -> dict:
    return fetch_minileague_detail(
        slug,
        state.cache,
        state.rate_limiter,
        browser_manager=state.browser_manager,
    )
