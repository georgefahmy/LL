from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.analytics import generate_mock_day
from ..deps import AppState, get_app_state, require_access_gate
from ..schemas import MockDayRequest

router = APIRouter(
    prefix="/api/mock-day",
    tags=["mock-day"],
    dependencies=[Depends(require_access_gate)],
)


@router.post("/generate")
def create_mock_day(
    body: MockDayRequest,
    state: AppState = Depends(get_app_state),
) -> dict:
    pool = state.cache.list_questions_for_mock(threshold=body.threshold)
    if len(pool) < 6:
        pool = state.cache.list_questions_for_mock(threshold=-1)
    if len(pool) < 6:
        raise HTTPException(
            status_code=503,
            detail="Question archive is still syncing. Please wait a moment and try again.",
        )
    return generate_mock_day(pool, seed=body.seed, threshold=body.threshold)
