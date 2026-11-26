from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ...core.analytics import (
    build_similarity_radar,
    calculate_hun,
    expected_opponent_points,
    recommend_defense,
)
from ...core.auth import LLSessionData
from ...core.http_client import LLHttpClient
from ...core.ocr import (
    decode_image_base64,
    extract_text_from_image_bytes,
    parse_category_stats_text,
)
from ...core.scrapers.matchday import fetch_todays_questions
from ...core.scrapers.profiles import fetch_player_profile
from ..deps import (
    AppState,
    get_app_state,
    get_ll_client,
    require_access_gate,
    require_ll_session,
)
from ..schemas import (
    CategoryMetricInput,
    DefenseRecommendRequest,
    ManualDefenseRecommendRequest,
    ParseStatsScreenshotRequest,
)

router = APIRouter(
    prefix="/api/defense",
    tags=["defense"],
    dependencies=[Depends(require_access_gate)],
)


def _to_metrics_dict(
    raw_metrics: dict[str, CategoryMetricInput],
) -> dict[str, dict[str, Any]]:
    converted: dict[str, dict[str, Any]] = {}
    for cat, metric in raw_metrics.items():
        pct = float(metric.percent)
        if metric.total > 0 and pct == 0.0:
            pct = round(min(1.0, metric.correct / metric.total), 6)
        converted[cat.strip()] = {
            "correct": metric.correct,
            "total": metric.total,
            "percent": pct,
        }
    return converted


@router.post("/parse-stats-screenshot")
def defense_parse_stats_screenshot(body: ParseStatsScreenshotRequest) -> dict[str, Any]:
    if body.raw_text is not None and body.raw_text.strip():
        return parse_category_stats_text(body.raw_text)
    if body.image_base64 is None or not body.image_base64.strip():
        raise HTTPException(
            status_code=400,
            detail="Provide either image_base64 or raw_text.",
        )
    try:
        image_bytes = decode_image_base64(body.image_base64)
        ocr_text = extract_text_from_image_bytes(image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return parse_category_stats_text(ocr_text)


@router.post("/recommend-manual")
def defense_recommend_manual(body: ManualDefenseRecommendRequest) -> dict[str, Any]:
    opp_dict = _to_metrics_dict(body.opponent_metrics)
    player_dict = (
        _to_metrics_dict(body.player_metrics)
        if body.player_metrics is not None
        else None
    )
    has_any_difficulty = bool(
        body.difficulties and any(d is not None for d in body.difficulties)
    )
    try:
        recommendations = recommend_defense(
            body.categories,
            opp_dict,
            player_metrics=player_dict,
            difficulties=body.difficulties,
            prior_weight=body.prior_weight,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "mode": "irt" if has_any_difficulty else "category_only",
        "expected_opponent_points": expected_opponent_points(recommendations),
        "recommendations": recommendations,
    }


@router.post("/recommend")
def defense_recommend(
    body: DefenseRecommendRequest,
    session: LLSessionData = Depends(require_ll_session),
    client: LLHttpClient = Depends(get_ll_client),
    state: AppState = Depends(get_app_state),
) -> dict:
    opp_profile = fetch_player_profile(
        body.opponent,
        client,
        state.cache,
        profile_id=body.opponent_profile_id,
        force_refresh=body.refresh,
        ttl_minutes=state.settings.profile_cache_ttl_minutes,
    )
    has_any_difficulty = bool(
        body.difficulties and any(d is not None for d in body.difficulties)
    )
    player_profile = None
    if has_any_difficulty:
        player_identifier = (body.player or session.username).strip()
        player_pid = body.player_profile_id or (
            None if body.player else session.profile_id
        )
        player_profile = fetch_player_profile(
            player_identifier,
            client,
            state.cache,
            profile_id=player_pid,
            force_refresh=body.refresh,
            ttl_minutes=state.settings.profile_cache_ttl_minutes,
        )
    try:
        recommendations = recommend_defense(
            body.categories,
            opp_profile.get("category_metrics", {}),
            player_metrics=player_profile.get("category_metrics", {})
            if player_profile
            else None,
            difficulties=body.difficulties,
            prior_weight=body.prior_weight,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "opponent": opp_profile["formatted_username"],
        "opponent_profile_id": opp_profile["profile_id"],
        "player": player_profile["formatted_username"] if player_profile else None,
        "mode": "irt" if has_any_difficulty else "category_only",
        "expected_opponent_points": expected_opponent_points(recommendations),
        "recommendations": recommendations,
    }


@router.get("/hun")
def defense_hun(
    player1: str = Query(..., min_length=1),
    player2: str = Query(..., min_length=1),
    player1_id: str | None = Query(default=None),
    player2_id: str | None = Query(default=None),
    refresh: bool = Query(default=False),
    session: LLSessionData = Depends(require_ll_session),
    client: LLHttpClient = Depends(get_ll_client),
    state: AppState = Depends(get_app_state),
) -> dict:
    _ = session
    p1 = fetch_player_profile(
        player1,
        client,
        state.cache,
        profile_id=player1_id,
        force_refresh=refresh,
        ttl_minutes=state.settings.profile_cache_ttl_minutes,
    )
    p2 = fetch_player_profile(
        player2,
        client,
        state.cache,
        profile_id=player2_id,
        force_refresh=refresh,
        ttl_minutes=state.settings.profile_cache_ttl_minutes,
    )
    hun = calculate_hun(p1.get("question_history", {}), p2.get("question_history", {}))
    return {
        "player1": p1["formatted_username"],
        "player2": p2["formatted_username"],
        **hun,
    }


@router.get("/similarity")
def defense_similarity(
    player1: str = Query(..., min_length=1),
    player2: str = Query(..., min_length=1),
    player1_id: str | None = Query(default=None),
    player2_id: str | None = Query(default=None),
    refresh: bool = Query(default=False),
    session: LLSessionData = Depends(require_ll_session),
    client: LLHttpClient = Depends(get_ll_client),
    state: AppState = Depends(get_app_state),
) -> dict:
    _ = session
    p1 = fetch_player_profile(
        player1,
        client,
        state.cache,
        profile_id=player1_id,
        force_refresh=refresh,
        ttl_minutes=state.settings.profile_cache_ttl_minutes,
    )
    p2 = fetch_player_profile(
        player2,
        client,
        state.cache,
        profile_id=player2_id,
        force_refresh=refresh,
        ttl_minutes=state.settings.profile_cache_ttl_minutes,
    )
    series = build_similarity_radar(
        p1.get("category_metrics", {}),
        p2.get("category_metrics", {}),
    )
    return {
        "player1": p1["formatted_username"],
        "player2": p2["formatted_username"],
        "series": series,
    }


@router.get("/todays-questions")
def defense_todays_questions(
    season: int | None = Query(default=None),
    day: int | None = Query(default=None),
    show_answers: bool = Query(default=False),
    session: LLSessionData = Depends(require_ll_session),
    client: LLHttpClient = Depends(get_ll_client),
    state: AppState = Depends(get_app_state),
) -> dict:
    if season is None or day is None:
        s_str = state.cache.get_meta("latest_season")
        d_str = state.cache.get_meta("current_day")
        max_s, max_d = state.cache.get_max_season_day()
        resolved_season = season if season is not None else (int(s_str) if s_str else max_s)
        resolved_day = day if day is not None else ((int(d_str) if d_str else max_d) + 1)
    else:
        resolved_season = season
        resolved_day = day
    _ = session  # guarantees authenticated session
    return fetch_todays_questions(
        client,
        resolved_season,
        resolved_day,
        display_answers=show_answers,
    )
