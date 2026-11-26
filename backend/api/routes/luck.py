from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.analytics import parse_leaguewide_csv, run_luck_analysis
from ...core.constants import ALL_RUNDLES_URL, LGWIDE_URL
from ...core.http_client import LLHttpClient, LLParseError
from ...core.scrapers.seasons import parse_season_and_day
from ..deps import (
    AppState,
    get_app_state,
    get_ll_client,
    require_access_gate,
    require_ll_session,
)
from ..schemas import LuckAnalyzeRequest

router = APIRouter(
    prefix="/api/luck",
    tags=["luck"],
    dependencies=[Depends(require_access_gate), Depends(require_ll_session)],
)


@router.get("/latest-season")
def get_latest_season(
    client: LLHttpClient = Depends(get_ll_client),
    state: AppState = Depends(get_app_state),
) -> dict:
    try:
        html = client.get_text(ALL_RUNDLES_URL)
        detected_season, detected_day = parse_season_and_day(html)
        state.cache.set_meta("latest_season", str(detected_season))
        state.cache.set_meta("current_day", str(detected_day))
        return {"latest_season": detected_season, "current_day": detected_day}
    except LLParseError:
        s_str = state.cache.get_meta("latest_season")
        d_str = state.cache.get_meta("current_day")
        max_s, max_d = state.cache.get_max_season_day()
        return {
            "latest_season": int(s_str) if s_str else max_s,
            "current_day": int(d_str) if d_str else max_d,
        }


@router.post("/analyze")
def analyze_luck(
    body: LuckAnalyzeRequest,
    client: LLHttpClient = Depends(get_ll_client),
    state: AppState = Depends(get_app_state),
) -> dict:
    resolved_season = body.season
    resolved_matchday = body.matchday

    if resolved_season is None or resolved_matchday is None:
        url = (
            f"{ALL_RUNDLES_URL}?{resolved_season}"
            if resolved_season is not None
            else ALL_RUNDLES_URL
        )
        try:
            html = client.get_text(url)
            detected_season, detected_day = parse_season_and_day(html)
            if body.season is None:
                state.cache.set_meta("latest_season", str(detected_season))
                state.cache.set_meta("current_day", str(detected_day))
            if resolved_season is None:
                resolved_season = detected_season
            if resolved_matchday is None:
                resolved_matchday = detected_day
        except LLParseError:
            max_s, max_d = state.cache.get_max_season_day()
            resolved_season = resolved_season or max_s
            resolved_matchday = resolved_matchday if resolved_matchday is not None else max_d

    # Completed historical seasons stay valid longer; active season refreshes every 6h
    max_age = 30 * 86400 if resolved_matchday >= 25 else 6 * 3600
    csv_text = None
    if not body.refresh:
        csv_text = state.cache.get_leaguewide_csv(
            resolved_season,
            resolved_matchday,
            max_age_seconds=max_age,
        )

    if csv_text is None:
        csv_url = LGWIDE_URL.format(resolved_season)
        raw_bytes = client.get_bytes(csv_url, require_auth=True)
        try:
            csv_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            csv_text = raw_bytes.decode("latin-1")

        # Validate before caching (protects against caching an HTML login redirect)
        df = parse_leaguewide_csv(csv_text)
        state.cache.set_leaguewide_csv(resolved_season, resolved_matchday, csv_text)
    else:
        try:
            df = parse_leaguewide_csv(csv_text)
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

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
        "season": resolved_season,
        "matchday": resolved_matchday,
        **result,
    }
