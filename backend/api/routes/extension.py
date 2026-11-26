from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...core.analytics import (
    build_similarity_radar,
    calculate_hun,
    parse_leaguewide_csv,
    run_luck_analysis,
)
from ...core.constants import MIN_AVAILABLE_SEASON
from ...core.scrapers.matchday import parse_todays_questions
from ...core.scrapers.profiles import (
    parse_profile_latest,
    parse_profile_past_seasons,
    parse_profile_qhistory,
    parse_profile_stats,
)
from ...core.scrapers.seasons import parse_match_day_questions, parse_season_and_day
from ..deps import AppState, get_app_state, require_access_gate
from ..schemas import (
    ExtensionAnalyzeLuckRequest,
    ExtensionHunRequest,
    ExtensionIngestMatchdayRequest,
    ExtensionParseProfileRequest,
    ExtensionParseSeasonDayRequest,
    ExtensionParseTodaysQuestionsRequest,
    ExtensionSimilarityRequest,
    ExtensionSyncPlanRequest,
)

router = APIRouter(
    prefix="/api/extension",
    tags=["extension"],
    dependencies=[Depends(require_access_gate)],
)


@router.post("/parse-profile")
def extension_parse_profile(body: ExtensionParseProfileRequest) -> dict[str, Any]:
    profile = parse_profile_latest(body.latest_html)
    profile["question_history"] = (
        parse_profile_qhistory(body.qhist_html) if body.qhist_html else {}
    )
    profile["stats"] = (
        parse_profile_stats(body.stats_html)
        if body.stats_html
        else {"total": {}, "current_season": {}}
    )
    profile["past_seasons"] = (
        parse_profile_past_seasons(body.past_html) if body.past_html else {}
    )
    return profile


@router.post("/parse-todays-questions")
def extension_parse_todays_questions(
    body: ExtensionParseTodaysQuestionsRequest,
) -> dict[str, Any]:
    return parse_todays_questions(
        body.html,
        body.season,
        body.day,
        display_answers=body.show_answers,
    )


@router.post("/parse-season-day")
def extension_parse_season_day(body: ExtensionParseSeasonDayRequest) -> dict[str, int]:
    latest_season, current_day = parse_season_and_day(body.html)
    return {"latest_season": latest_season, "current_day": current_day}


@router.post("/hun")
def extension_hun(body: ExtensionHunRequest) -> dict[str, Any]:
    hun = calculate_hun(body.qhist_1, body.qhist_2)
    return {"player1": body.player1, "player2": body.player2, **hun}


@router.post("/similarity")
def extension_similarity(body: ExtensionSimilarityRequest) -> dict[str, Any]:
    series = build_similarity_radar(body.metrics_1, body.metrics_2)
    return {"player1": body.player1, "player2": body.player2, "series": series}


@router.post("/analyze-luck")
def extension_analyze_luck(body: ExtensionAnalyzeLuckRequest) -> dict[str, Any]:
    try:
        df = parse_leaguewide_csv(body.csv_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        result = run_luck_analysis(
            df,
            usernames=body.usernames,
            extra_fields=body.extra_fields,
            rundle_flag=body.rundle_flag,
            use_sos=body.use_sos,
            divide_pairs=body.divide_pairs,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Luck calculation error: {exc}") from exc
    return {
        "season": body.season,
        "matchday": body.matchday,
        **result,
    }


@router.post("/sync-plan")
def extension_sync_plan(
    body: ExtensionSyncPlanRequest,
    state: AppState = Depends(get_app_state),
) -> dict[str, Any]:
    latest_season, current_day = parse_season_and_day(body.allrundles_html)
    state.cache.set_meta("latest_season", str(latest_season))
    state.cache.set_meta("current_day", str(current_day))

    existing_days = state.cache.get_existing_season_days()
    missing: list[tuple[int, int]] = []
    for season in range(MIN_AVAILABLE_SEASON, latest_season + 1):
        max_day = 25 if season < latest_season else min(25, current_day)
        for day in range(1, max_day + 1):
            if (season, day) not in existing_days:
                missing.append((season, day))

    missing.sort(key=lambda item: (-item[0], item[1]))
    batch = missing[: body.max_days]
    remaining_missing = len(missing) - len(batch)
    state.sync_worker.record_external_sync(
        latest_season=latest_season,
        current_day=current_day,
        remaining_missing_days=remaining_missing,
    )
    return {
        "latest_season": latest_season,
        "current_day": current_day,
        "batch": [{"season": s, "day": d} for s, d in batch],
        "remaining_missing_days": remaining_missing,
    }


@router.post("/ingest-matchday")
def extension_ingest_matchday(
    body: ExtensionIngestMatchdayRequest,
    state: AppState = Depends(get_app_state),
) -> dict[str, Any]:
    records = parse_match_day_questions(body.html, body.season, body.day)
    imported = state.cache.upsert_questions(records) if records else 0
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state.cache.set_meta("last_synced_at", now_iso)
    state.sync_worker.record_external_sync(last_synced_at=now_iso)
    return {
        "season": body.season,
        "day": body.day,
        "imported": imported,
    }
