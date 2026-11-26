from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from backend.core.http_client import LLNotFoundError, LLParseError
from backend.core.scrapers.matchday import parse_todays_questions
from backend.core.scrapers.minileagues import (
    parse_minileague_catalog,
    parse_minileague_match_day,
    parse_minileague_match_links,
)
from backend.core.scrapers.onedays import parse_oneday_catalog, parse_oneday_detail
from backend.core.scrapers.profiles import (
    parse_profile_latest,
    parse_profile_past_seasons,
    parse_profile_qhistory,
    parse_profile_stats,
)
from backend.core.scrapers.seasons import parse_match_day_questions, parse_season_and_day

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_season_and_day() -> None:
    season, day = parse_season_and_day(_read("allrundles.html"))
    assert season == 109
    assert day == 14


def test_parse_season_and_day_fallback_to_table() -> None:
    html = """
    <html><body>
      <h1>LL108: All Rundles</h1>
      <table class="MDTable">
        <tr><th>Day</th><th>Status</th></tr>
        <tr><td><a href="match.php?108&1">Match Day 1</a></td><td>100</td></tr>
        <tr><td><a href="match.php?108&2">Match Day 2</a></td><td>Active</td></tr>
        <tr><td>Match Day 3</td><td></td></tr>
      </table>
    </body></html>
    """
    season, day = parse_season_and_day(html)
    assert season == 108
    assert day == 2


def test_parse_season_and_day_invalid_raises() -> None:
    with pytest.raises(LLParseError):
        parse_season_and_day("<html><body><p>Unexpected</p></body></html>")


def test_parse_match_day_questions() -> None:
    qs = parse_match_day_questions(_read("match_day_past.html"), 109, 14)
    assert len(qs) == 6
    assert qs[0]["qcode"] == "S109D14Q1"
    assert qs[0]["category"] == "AMER HIST"
    assert qs[0]["answer"] == "ERIE CANAL"
    assert qs[0]["percent"] == 76
    assert qs[0]["defense"] == "1.0"
    assert qs[0]["A"] == "92"
    assert qs[1]["clickable_link"] == "https://www.learnedleague.com/images/test_q2.png"
    assert qs[1]["question"].startswith("Identify the element")


def test_parse_todays_questions_states() -> None:
    ok = parse_todays_questions(_read("match_day_today.html"), 109, 14, display_answers=False)
    assert ok["status"] == "ok"
    assert len(ok["questions"]) == 6
    assert ok["questions"][0]["submitted_answer"] == "hidden"
    assert ok["questions"][0]["points_assigned"] == "3"

    revealed = parse_todays_questions(_read("match_day_today.html"), 109, 14, display_answers=True)
    assert revealed["questions"][0]["submitted_answer"] == "MY ANS 1"
    assert revealed["questions"][0]["correct_answer"] == "TRUE ANS 1"

    no_match = parse_todays_questions("<div><h1>LL109 Results</h1></div>", 109, 14)
    assert no_match["status"] == "no_active_match"

    inactive = parse_todays_questions("<div><h2>Match is not yet active</h2></div>", 109, 15)
    assert inactive["status"] == "not_yet_active"


def test_parse_oneday_catalog_and_detail() -> None:
    items = parse_oneday_catalog(_read("onedaysalpha.html"), now=datetime(2026, 1, 1))
    assert len(items) == 1
    assert items[0]["slug"] == "4689"
    assert items[0]["title"] == "Solar System Trivia"

    detail = parse_oneday_detail(
        _read("oneday_detail.html"),
        _read("oneday_metrics.html"),
        items[0],
    )
    assert detail["difficulty_rating"] == "PG-13"
    assert detail["number_of_players"] == 350
    assert detail["p90"] == 35
    assert detail["p50"] == 20
    assert detail["p10"] is None
    assert len(detail["questions"]) == 2
    assert detail["questions"][0]["answer"] == "MERCURY"
    assert detail["questions"][0]["percent"] == 90

    # Metrics page missing -> no UnboundLocalError
    detail_no_metrics = parse_oneday_detail(_read("oneday_detail.html"), None, items[0])
    assert detail_no_metrics["number_of_players"] == 0
    assert detail_no_metrics["questions"][0]["percent"] == 0


def test_parse_minileagues_dynamic_counts() -> None:
    catalog = parse_minileague_catalog(_read("mini_list.html"))
    assert len(catalog) == 1
    assert catalog[0]["slug"] == "jazz1"

    links = parse_minileague_match_links(_read("mini_overview.html"))
    assert len(links) == 2
    assert all("12" not in url for _, url in links)

    day_qs = parse_minileague_match_day(_read("mini_match_day.html"), 1)
    assert len(day_qs) == 5
    assert day_qs[0]["answer"] == "PAUL DESMOND"
    assert day_qs[0]["percent"] == 68
    assert day_qs[4]["percent"] == 79


def test_parse_profiles_and_rookie_edge_cases() -> None:
    latest = parse_profile_latest(_read("profile_latest.html"))
    assert latest["profile_id"] == "12345"
    assert latest["formatted_username"] == "AlicePlayer"
    assert latest["opponents"] == {"BobOpp": "22222", "CarolOpp": "33333"}
    assert latest["category_metrics"]["SCIENCE"]["correct"] == 10
    assert latest["category_metrics"]["MATH"]["percent"] == 0.0

    qhist = parse_profile_qhistory(_read("profile_qhistory.html"))
    assert qhist["S109D01Q2"]["correct"] is True
    assert qhist["S108D05Q3"]["correct"] is False

    stats = parse_profile_stats(_read("profile_stats.html"))
    assert stats["total"]["PTS"] == "265"
    assert stats["current_season"]["W"] == "8"

    # Single-season rookie without grandtotal-row or pastseasons
    single_stats = parse_profile_stats(_read("profile_stats_single.html"))
    assert single_stats["total"]["W"] == "5"
    assert single_stats["current_season"]["W"] == "5"

    past = parse_profile_past_seasons(_read("profile_past_seasons.html"))
    assert past["LL108"]["results"] == {"wins": 1, "ties": 1, "losses": 0}
    assert parse_profile_past_seasons("<html><body>No past seasons</body></html>") == {}

    # Minimal 2-column fixture leaves played=None while preserving match_day
    assert latest["opponent_schedule"] == [
        {
            "username": "BobOpp",
            "profile_id": "22222",
            "match_day": 1,
            "played": None,
            "result": "",
        },
        {
            "username": "CarolOpp",
            "profile_id": "33333",
            "match_day": 2,
            "played": None,
            "result": "",
        },
    ]

    with pytest.raises(LLNotFoundError):
        parse_profile_latest("<html><body><p>Not found</p></body></html>")


def test_parse_profile_opponent_schedule_played_and_upcoming() -> None:
    html = """
    <html><body>
      <h1 class="namecss">AlicePlayer</h1>
      <div class="flagdiv"><a href="/profiles.php?12345"></a></div>
      <table summary="Data table for LL results">
        <tr><th>MD</th><th>Opponent</th><th>Result</th><th>Score</th></tr>
        <tr>
          <td>1</td>
          <td><a class="flag" href="/profiles.php?201"><img title="PlayedWin" /></a></td>
          <td>W</td>
          <td>7(5)-4(3)</td>
        </tr>
        <tr>
          <td>2</td>
          <td><a class="flag" href="/profiles.php?202"><img title="PlayedLoss" /></a></td>
          <td>L</td>
          <td>3(2)-6(4)</td>
        </tr>
        <tr>
          <td>3</td>
          <td><a class="flag" href="/profiles.php?203"><img title="UpNextOpp" /></a></td>
          <td>&nbsp;</td>
          <td>&nbsp;</td>
        </tr>
      </table>
    </body></html>
    """
    parsed = parse_profile_latest(html)
    assert parsed["opponent_schedule"] == [
        {
            "username": "PlayedWin",
            "profile_id": "201",
            "match_day": 1,
            "played": True,
            "result": "W",
        },
        {
            "username": "PlayedLoss",
            "profile_id": "202",
            "match_day": 2,
            "played": True,
            "result": "L",
        },
        {
            "username": "UpNextOpp",
            "profile_id": "203",
            "match_day": 3,
            "played": False,
            "result": "",
        },
    ]
