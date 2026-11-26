from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from ..cache import CacheStore
from ..constants import BASE_URL
from ..http_client import LLHttpClient, LLNotFoundError

_OUTCOME_RE = re.compile(r"^(?:([WLTF])|Forfeit)\b", re.IGNORECASE)
_SCORE_RE = re.compile(r"\d+\s*\(\d+\)\s*[-–]\s*\d+")


def _safe_int(text: str) -> int:
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


def _parse_opponent_row(row: Any, fallback_day: int) -> dict[str, Any] | None:
    """Parse one opponent schedule row from profile &1 results table."""
    img = row.find("img")
    flag = row.find("a", {"class": "flag"})
    if not img or not img.get("title") or not flag or not flag.get("href"):
        return None

    username = str(img.get("title")).strip()
    profile_id = str(flag.get("href")).split("?")[-1].strip()
    cells = row.find_all("td")
    day_num = _safe_int(cells[0].get_text(strip=True)) if cells else 0
    match_day = day_num if 1 <= day_num <= 25 else fallback_day

    flag_cell = flag.find_parent("td")
    extra_cells = [c for idx, c in enumerate(cells) if idx > 0 and c is not flag_cell]

    played: bool | None = False if extra_cells else None
    result = ""
    for cell in extra_cells:
        txt = cell.get_text(" ", strip=True)
        if not txt:
            continue
        out_match = _OUTCOME_RE.match(txt)
        if out_match:
            played = True
            result = (out_match.group(1) or "F").upper()
        elif _SCORE_RE.search(txt):
            played = True

    return {
        "username": username,
        "profile_id": profile_id,
        "match_day": match_day,
        "played": played,
        "result": result,
    }


def parse_profile_latest(html: str) -> dict[str, Any]:
    """Parse profile &1 (latest tab): username, profile_id, opponents, category metrics."""
    soup = BeautifulSoup(html, "html.parser")
    flag_div = soup.find("div", {"class": "flagdiv"})
    name_el = soup.find("h1", {"class": "namecss"})
    if not flag_div or not flag_div.find("a") or not name_el:
        raise LLNotFoundError("LearnedLeague player not found.")

    profile_id = str(flag_div.find("a").get("href") or "").split("?")[-1].strip()
    if not profile_id.isdigit():
        raise LLNotFoundError("LearnedLeague player not found.")

    formatted_username = name_el.get_text(" ", strip=True)

    opponents: dict[str, str] = {}
    opponent_schedule: list[dict[str, Any]] = []
    op_table = soup.find("table", {"summary": "Data table for LL results"})
    if op_table:
        for row in op_table.find_all("tr")[1:]:
            entry = _parse_opponent_row(row, len(opponent_schedule) + 1)
            if entry is not None:
                opponents[entry["username"]] = entry["profile_id"]
                opponent_schedule.append(entry)

    category_metrics: dict[str, dict[str, Any]] = {}
    cat_table = soup.find("table", {"class": "std sortable this_sea std_bord"}) or soup.find(
        "table", {"class": "this_sea"}
    )
    if cat_table and cat_table.find("tbody"):
        for row in cat_table.find("tbody").find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            cat_name = cells[0].get_text(" ", strip=True)
            parts = cells[1].get_text(strip=True).split("-")
            correct = _safe_int(parts[0]) if len(parts) > 0 else 0
            total = _safe_int(parts[1]) if len(parts) > 1 else 0
            percent = (correct / total) if total > 0 else 0.0
            category_metrics[cat_name] = {
                "correct": correct,
                "total": total,
                "percent": round(percent, 6),
            }

    return {
        "profile_id": profile_id,
        "username": formatted_username.lower(),
        "formatted_username": formatted_username,
        "link": f"{BASE_URL}/profiles.php?{profile_id}",
        "opponents": opponents,
        "opponent_schedule": opponent_schedule,
        "category_metrics": category_metrics,
    }


def parse_profile_qhistory(html: str) -> dict[str, dict[str, Any]]:
    """Parse profile &9 (question history tab)."""
    soup = BeautifulSoup(html, "html.parser")
    qhistory_div = soup.find("div", {"class": "qhistory"})
    if not qhistory_div:
        return {}

    history: dict[str, dict[str, Any]] = {}
    for category_li in qhistory_div.find_all("li"):
        cat_span = category_li.find("span", {"class": "catname"})
        category_name = cat_span.get_text(" ", strip=True) if cat_span else ""
        table = category_li.find("table", {"class": "qh"})
        if not table:
            continue
        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            anchors = cells[0].find_all("a")
            if len(anchors) < 3:
                continue
            href = str(anchors[2].get("href") or "")
            raw_id = href.split("?")[-1]
            parts = raw_id.split("&")
            if len(parts) < 3:
                continue
            qcode = f"S{parts[0]}D{parts[1].zfill(2)}Q{parts[2]}"
            svg = cells[2].find("svg")
            aria = str(svg.get("aria-label") or "") if svg else ""
            correct = "Check" in aria
            q_text = cells[1].get_text(" ", strip=True)
            history[qcode] = {
                "question_category": category_name,
                "correct": correct,
                "question": q_text,
                "url": f"{BASE_URL}{href}" if href.startswith("/") else f"{BASE_URL}/{href}",
            }
    return history


def parse_profile_stats(html: str) -> dict[str, dict[str, str]]:
    """Parse profile &2 (all-time & current season stats)."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"class": "std std_bord stats_all"}) or soup.find(
        "table", {"class": "stats_all"}
    )
    if not table or not table.find("thead") or not table.find("tbody"):
        return {"total": {}, "current_season": {}}

    headers = [
        "Seas." if td.get_text(strip=True) == "Season" else td.get_text(strip=True)
        for td in table.find("thead").find_all("td")
    ]
    tbody = table.find("tbody")
    total_row = tbody.find("tr", {"class": "grandtotal-row"})
    first_row = tbody.find("tr")

    total_cells = (
        [td.get_text(strip=True) for td in total_row.find_all("td")] if total_row else []
    )
    current_cells = (
        [td.get_text(strip=True) for td in first_row.find_all("td")] if first_row else []
    )

    if not total_cells and current_cells:
        total_cells = list(current_cells)

    total_stats: dict[str, str] = {}
    current_stats: dict[str, str] = {}
    for idx, hdr in enumerate(headers):
        if idx < len(total_cells):
            total_stats[hdr] = "Total" if idx == 0 else total_cells[idx]
        if idx < len(current_cells):
            current_stats[hdr] = current_cells[idx]

    return {"total": total_stats, "current_season": current_stats}


def parse_profile_past_seasons(html: str) -> dict[str, Any]:
    """Parse profile &7 (past seasons tab), safely returning {} for rookies."""
    soup = BeautifulSoup(html, "html.parser")
    past_div = soup.find("div", {"class": "pastseasons"})
    if not past_div:
        return {}

    result: dict[str, Any] = {}
    for season_box in past_div.find_all("div", {"class": "fl_latest"}):
        h2 = season_box.find("h2")
        h3 = season_box.find("h3")
        table = season_box.find("table")
        if not h2 or not h3 or not table or not table.find("tbody"):
            continue
        season_name = h2.get_text(" ", strip=True).split(" ")[0]
        rundle_name = h3.get_text(" ", strip=True)
        wins = ties = losses = 0
        matches: dict[str, Any] = {}

        for row in table.find("tbody").find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            md_key = cells[0].get_text(" ", strip=True).replace(" ", "_").lower()
            opp_img = cells[1].find("img")
            res_code = cells[2].get_text(strip=True)
            res_str = "Win" if res_code == "W" else "Tie" if res_code == "T" else "Loss"
            if res_str == "Win":
                wins += 1
            elif res_str == "Tie":
                ties += 1
            else:
                losses += 1
            score_text = cells[3].get_text(strip=True)
            matches[md_key] = {
                "opponent": str(opp_img.get("title") or "").strip() if opp_img else "",
                "result": res_str,
                "score": score_text,
            }

        result[season_name] = {
            "season": season_name,
            "rundle": rundle_name,
            "results": {"wins": wins, "ties": ties, "losses": losses},
            "matches": matches,
        }
    return result


def fetch_player_profile(
    identifier: str,
    client: LLHttpClient,
    cache: CacheStore,
    *,
    profile_id: str | None = None,
    force_refresh: bool = False,
    ttl_minutes: int = 30,
) -> dict[str, Any]:
    """Fetch full LearnedLeague player profile using authenticated client + TTL cache."""
    lookup_key = (profile_id or identifier).strip()
    if not lookup_key:
        raise LLNotFoundError("Player username or profile ID is required.")

    if not force_refresh:
        cached = cache.get_cached_profile(lookup_key, ttl_minutes=ttl_minutes)
        if cached is not None:
            return cached

    latest_html = client.get_text(
        f"{BASE_URL}/profiles.php?{lookup_key}&1",
        require_auth=True,
    )
    profile = parse_profile_latest(latest_html)
    pid = profile["profile_id"]

    qhist_html = client.get_text(f"{BASE_URL}/profiles.php?{pid}&9", require_auth=True)
    stats_html = client.get_text(f"{BASE_URL}/profiles.php?{pid}&2", require_auth=True)
    past_html = client.get_text(f"{BASE_URL}/profiles.php?{pid}&7", require_auth=True)

    profile["question_history"] = parse_profile_qhistory(qhist_html)
    profile["stats"] = parse_profile_stats(stats_html)
    profile["past_seasons"] = parse_profile_past_seasons(past_html)

    cache.set_cached_profile(profile)
    return profile
