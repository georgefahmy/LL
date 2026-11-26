from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from ..constants import BASE_URL
from ..http_client import LLHttpClient


def parse_todays_questions(
    html: str,
    season: int,
    day: int,
    *,
    display_answers: bool = False,
) -> dict[str, Any]:
    """Parse active match day's questions and caller's own submitted answers."""
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if h1 and h1.parent and "Results" in h1.parent.get_text(" ", strip=True):
        return {
            "status": "no_active_match",
            "season": season,
            "day": day,
            "message": "No active match day currently in play.",
            "questions": [],
        }

    h2 = soup.find("h2")
    if h2 and h2.parent and "not yet active" in h2.parent.get_text(" ", strip=True).lower():
        return {
            "status": "not_yet_active",
            "season": season,
            "day": day,
            "message": f"Match Day {day} is not yet active.",
            "questions": [],
        }

    q_spans = soup.find_all("span", {"id": re.compile(r"q_field")})
    submitted_divs = soup.find_all("div", {"class": re.compile(r"ans_1")})
    correct_divs = soup.find_all("div", {"class": re.compile(r"ans_2")})
    points_divs = soup.find_all("div", {"class": re.compile(r"ans_3")})

    questions: list[dict[str, Any]] = []
    for idx in range(len(q_spans)):
        q_text = q_spans[idx].get_text(" ", strip=True)
        has_subs = idx < len(submitted_divs)
        sub_ans = submitted_divs[idx].get_text(" ", strip=True) if has_subs else "--"
        cor_ans = correct_divs[idx].get_text(" ", strip=True) if idx < len(correct_divs) else "--"
        pts_val = points_divs[idx].get_text(" ", strip=True) if idx < len(points_divs) else "--"
        questions.append(
            {
                "id": idx + 1,
                "question": q_text,
                "submitted_answer": sub_ans if display_answers else "hidden",
                "correct_answer": cor_ans if display_answers else "hidden",
                "points_assigned": pts_val,
            }
        )

    return {
        "status": "ok",
        "season": season,
        "day": day,
        "message": f"LL {season} Match Day {day}",
        "questions": questions,
    }


def fetch_todays_questions(
    client: LLHttpClient,
    season: int,
    day: int,
    *,
    display_answers: bool = False,
) -> dict[str, Any]:
    """Always fetch live per-user Today's Questions (never shared cache)."""
    url = f"{BASE_URL}/match.php?{season}&{day}"
    html = client.get_text(url, require_auth=True)
    return parse_todays_questions(html, season, day, display_answers=display_answers)
