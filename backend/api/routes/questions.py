from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ...core.auth import LLSessionData
from ...core.grading import grade_answer
from ...core.http_client import LLHttpClient, fetch_ll_image
from ...core.lookup import lookup_term
from ..deps import (
    AppState,
    get_app_state,
    get_optional_session,
    require_access_gate,
    require_desktop_mode,
)
from ..schemas import (
    FavoritesPut,
    GradeRequest,
    MockDaySave,
    OneDayAttemptSave,
    PracticeAnswerCreate,
    PracticeAnswerOverride,
)

router = APIRouter(
    prefix="/api",
    tags=["questions"],
    dependencies=[Depends(require_access_gate)],
)

_QCODE_NORM_RE = re.compile(r"^S(\d+)D(\d+)Q(\d+)$", re.IGNORECASE)


def _normalize_qcode(qcode: str) -> str:
    m = _QCODE_NORM_RE.match(qcode.strip())
    if m:
        return f"S{int(m.group(1))}D{int(m.group(2)):02d}Q{int(m.group(3))}"
    return qcode.strip().upper()


@router.get("/questions")
def list_questions(
    min_pct: int = Query(default=0, ge=0, le=100),
    max_pct: int = Query(default=100, ge=0, le=100),
    category: str = Query(default="ALL"),
    season: str = Query(default="ALL"),
    search: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    random: bool = Query(default=False),
    state: AppState = Depends(get_app_state),
) -> dict:
    season_int: int | None = None
    if season.upper() != "ALL":
        try:
            season_int = int(season)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid season filter.") from exc
    return state.cache.query_questions(
        min_pct=min_pct,
        max_pct=max_pct,
        category=category,
        season=season_int,
        search=search,
        limit=limit,
        offset=offset,
        random_one=random,
    )


@router.get("/questions/sync/status")
def sync_status(state: AppState = Depends(get_app_state)) -> dict:
    return {
        "question_count": state.cache.count_questions(),
        **state.sync_worker.status(),
    }


@router.post("/questions/sync")
def trigger_sync(state: AppState = Depends(get_app_state)) -> dict:
    started = state.sync_worker.trigger_now()
    return {
        "triggered": started,
        **state.sync_worker.status(),
    }


@router.get("/questions/export.json.gz")
def export_questions_gzip(state: AppState = Depends(get_app_state)) -> Response:
    payload = state.cache.export_questions_gzip()
    return Response(
        content=payload,
        media_type="application/gzip",
        headers={"Content-Disposition": 'attachment; filename="seed_questions.json.gz"'},
    )


@router.get("/questions/{qcode}")
def get_single_question(qcode: str, state: AppState = Depends(get_app_state)) -> dict:
    norm = _normalize_qcode(qcode)
    q = state.cache.get_question(norm)
    if q is None:
        raise HTTPException(status_code=404, detail=f"Question {norm} not found.")
    return q


@router.post("/questions/grade")
def grade_single_question(body: GradeRequest) -> dict:
    res = grade_answer(body.submitted_answer, body.correct_answer)
    return {
        "correct": res.correct,
        "score": res.best_score,
        "matched_variant": res.matched_variant,
        "variants": res.variants,
    }


@router.get("/proxy/image")
def proxy_ll_image(
    url: str = Query(..., min_length=1),
    state: AppState = Depends(get_app_state),
    session: LLSessionData | None = Depends(get_optional_session),
) -> Response:
    cookies = session.cookies if session else None
    with LLHttpClient(cookies=cookies, rate_limiter=state.rate_limiter) as client:
        img_bytes, content_type = fetch_ll_image(url, client)
    return Response(
        content=img_bytes,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/lookup")
def lookup_selection(q: str = Query(..., min_length=1, max_length=200)) -> dict:
    return lookup_term(q)


# ---- Desktop-Mode Local Personal Storage ----


@router.get("/local-store/practice-answers", dependencies=[Depends(require_desktop_mode)])
def list_local_practice_answers(
    qcode: str | None = None,
    state: AppState = Depends(get_app_state),
) -> dict:
    return {"items": state.cache.list_practice_answers(qcode=qcode)}


@router.post("/local-store/practice-answers", dependencies=[Depends(require_desktop_mode)])
def add_local_practice_answer(
    body: PracticeAnswerCreate,
    state: AppState = Depends(get_app_state),
) -> dict:
    answer_id = state.cache.record_practice_answer(
        qcode=body.qcode,
        submitted_answer=body.submitted_answer,
        correct=body.correct,
        override=body.override,
    )
    return {"id": answer_id}


@router.patch(
    "/local-store/practice-answers/{answer_id}",
    dependencies=[Depends(require_desktop_mode)],
)
def patch_local_practice_answer(
    answer_id: int,
    body: PracticeAnswerOverride,
    state: AppState = Depends(get_app_state),
) -> dict:
    updated = state.cache.override_practice_answer(
        answer_id, correct=body.correct, override=body.override
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Practice answer record not found.")
    return {"updated": True}


@router.get("/local-store/favorites", dependencies=[Depends(require_desktop_mode)])
def get_local_favorites(state: AppState = Depends(get_app_state)) -> dict:
    return {"usernames": state.cache.list_favorites()}


@router.put("/local-store/favorites", dependencies=[Depends(require_desktop_mode)])
def put_local_favorites(
    body: FavoritesPut,
    state: AppState = Depends(get_app_state),
) -> dict:
    return {"usernames": state.cache.set_favorites(body.usernames)}


@router.get("/local-store/onedays", dependencies=[Depends(require_desktop_mode)])
def get_local_onedays(state: AppState = Depends(get_app_state)) -> dict:
    return {"items": state.cache.list_local_oneday_attempts()}


@router.post("/local-store/onedays", dependencies=[Depends(require_desktop_mode)])
def post_local_oneday(
    body: OneDayAttemptSave,
    state: AppState = Depends(get_app_state),
) -> dict:
    state.cache.save_local_oneday_attempt(
        slug=body.slug,
        title=body.title,
        payload=body.payload,
        score=body.score,
        percentile=body.percentile,
    )
    return {"saved": True}


@router.get("/local-store/mock-days", dependencies=[Depends(require_desktop_mode)])
def get_local_mock_days(state: AppState = Depends(get_app_state)) -> dict:
    return {"items": state.cache.list_local_mock_days()}


@router.post("/local-store/mock-days", dependencies=[Depends(require_desktop_mode)])
def post_local_mock_day(
    body: MockDaySave,
    state: AppState = Depends(get_app_state),
) -> dict:
    state.cache.save_local_mock_day(
        uuid=body.uuid,
        code=body.code,
        seed=body.seed,
        threshold=body.threshold,
        payload=body.payload,
    )
    return {"saved": True}


@router.get("/local-store/export", dependencies=[Depends(require_desktop_mode)])
def export_local_personal_data(state: AppState = Depends(get_app_state)) -> dict:
    return state.cache.export_personal_data()


@router.post("/local-store/import", dependencies=[Depends(require_desktop_mode)])
def import_local_personal_data(
    payload: dict,
    state: AppState = Depends(get_app_state),
) -> dict:
    counts = state.cache.import_personal_data(payload)
    return {"imported": counts}
