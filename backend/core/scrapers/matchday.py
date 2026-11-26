from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from ..constants import BASE_URL
from ..http_client import LLHttpClient
from .seasons import parse_match_day_questions


def parse_todays_questions(
    html: str,
    season: int,
    day: int,
    *,
    display_answers: bool = False,
) -> dict[str, Any]:
    """Parse active or past match day's 6 questions and answers."""
    soup = BeautifulSoup(html, "html.parser")
    q_spans = soup.find_all("span", {"id": re.compile(r"q_field")})
    if q_spans:
        submitted_divs = soup.find_all("div", {"class": re.compile(r"ans_1")})
        correct_divs = soup.find_all("div", {"class": re.compile(r"ans_2")})
        points_divs = soup.find_all("div", {"class": re.compile(r"ans_3")})

        questions: list[dict[str, Any]] = []
        for idx in range(len(q_spans)):
            q_text = q_spans[idx].get_text(" ", strip=True)
            has_subs = idx < len(submitted_divs)
            sub_ans = submitted_divs[idx].get_text(" ", strip=True) if has_subs else "--"
            cor_ans = (
                correct_divs[idx].get_text(" ", strip=True) if idx < len(correct_divs) else "--"
            )
            pts_val = (
                points_divs[idx].get_text(" ", strip=True) if idx < len(points_divs) else "--"
            )
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

    past_records = parse_match_day_questions(html, season, day)
    if past_records:
        submitted_divs = soup.find_all("div", {"class": re.compile(r"ans_1")})
        past_questions: list[dict[str, Any]] = []
        for idx, rec in enumerate(past_records):
            if idx < len(submitted_divs):
                raw_sub = submitted_divs[idx].get_text(" ", strip=True) or "--"
                submitted_val = raw_sub if display_answers else "hidden"
            else:
                submitted_val = "--"
            past_questions.append(
                {
                    "id": rec["q_num"],
                    "question": (
                        f"{rec['category']} - {rec['question']}"
                        if rec.get("category")
                        else rec["question"]
                    ),
                    "submitted_answer": submitted_val,
                    "correct_answer": rec["answer"] if display_answers else "hidden",
                    "points_assigned": (
                        f"{rec['percent']}%" if rec.get("percent") is not None else "--"
                    ),
                }
            )
        return {
            "status": "ok",
            "season": season,
            "day": day,
            "message": f"LL {season} Match Day {day} (Past Match)",
            "questions": past_questions,
        }

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

    return {
        "status": "ok",
        "season": season,
        "day": day,
        "message": f"LL {season} Match Day {day}",
        "questions": [],
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
