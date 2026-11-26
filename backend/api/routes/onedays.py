from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...core.grading import grade_answer
from ...core.scrapers.onedays import fetch_oneday_detail, fetch_onedays_catalog
from ..deps import AppState, get_app_state, require_access_gate
from ..schemas import OneDayGradeRequest

router = APIRouter(
    prefix="/api/onedays",
    tags=["onedays"],
    dependencies=[Depends(require_access_gate)],
)


@router.get("")
def list_onedays(
    search: str = Query(default=""),
    refresh: bool = Query(default=False),
    state: AppState = Depends(get_app_state),
) -> dict:
    items = fetch_onedays_catalog(
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
def get_oneday(slug: str, state: AppState = Depends(get_app_state)) -> dict:
    return fetch_oneday_detail(
        slug,
        state.cache,
        state.rate_limiter,
        browser_manager=state.browser_manager,
    )


@router.post("/grade")
def grade_oneday(
    body: OneDayGradeRequest,
    state: AppState = Depends(get_app_state),
) -> dict:
    detail = fetch_oneday_detail(
        body.slug,
        state.cache,
        state.rate_limiter,
        browser_manager=state.browser_manager,
    )
    q_map = {str(q["question_num"]): q for q in detail.get("questions", [])}

    score = 0
    results: list[dict] = []
    money_used = 0
    for item in body.answers:
        q = q_map.get(item.question_num)
        if not q:
            continue
        sub_ans = item.submitted_answer.strip()
        is_forfeit = sub_ans.upper() == "NONE" or not sub_ans
        if item.override is not None:
            is_correct = item.override
            best_score = 1.0 if is_correct else 0.0
        elif is_forfeit:
            is_correct = False
            best_score = 0.0
        else:
            graded = grade_answer(item.submitted_answer, str(q.get("answer", "")))
            is_correct = graded.correct
            best_score = graded.best_score

        is_money = bool(item.money_question and money_used < 5)
        if is_money:
            money_used += 1

        points_earned = 0
        if is_correct:
            points_earned = 15
            if is_money:
                points_earned += max(0, 100 - int(q.get("percent", 0)))
        score += points_earned

        results.append(
            {
                "question_num": item.question_num,
                "correct": is_correct,
                "score": best_score,
                "correct_answer": q.get("answer", ""),
                "percent": q.get("percent", 0),
                "money_question": is_money,
                "points_earned": points_earned,
            }
        )

    percentiles: dict = detail.get("percentiles") or {}
    final_percentile = "NONE"
    if percentiles:
        closest_pct = min(
            percentiles.keys(),
            key=lambda p: abs(int(percentiles[p]) - score),
        )
        final_percentile = str(closest_pct)

    return {
        "slug": body.slug,
        "total_score": score,
        "final_percentile": final_percentile,
        "results": results,
    }
