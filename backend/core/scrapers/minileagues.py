from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..browser_session import build_ll_client
from ..constants import BASE_URL, EXCLUDED_QUIZ_MARKERS, MINILEAGUES_LIST_URL
from ..http_client import LLNotFoundError


def slug_from_mini_url(url: str) -> str:
    parsed = urlparse(url)
    raw = parsed.query or parsed.path.rstrip("/").split("/")[-1]
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_")
    return slug or "minileague"


def parse_minileague_catalog(html: str) -> list[dict[str, str]]:
    """Parse available Mini Leagues from /mini/."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"class": "std min"})
    if not table:
        return []
    tbody = table.find("tbody") or table
    rows = tbody.find_all("tr")
    body_rows = rows[3:-1] if len(rows) > 4 else rows

    items: list[dict[str, str]] = []
    seen_slugs: set[str] = set()
    min_dt = datetime(2014, 1, 1)
    for row in body_rows:
        title_cell = row.find("td", {"class": "std-left"})
        if not title_cell or not title_cell.find("a"):
            continue
        title = title_cell.get_text(" ", strip=True)
        if any(marker in title for marker in EXCLUDED_QUIZ_MARKERS):
            continue
        href = str(title_cell.find("a").get("href") or "").strip()
        if not href:
            continue
        date_cell = row.find("td", {"class": "std-midleft"})
        players_cell = row.find("td", {"class": "std-mid"})
        date_str = date_cell.get_text(" ", strip=True) if date_cell else ""
        if date_str:
            try:
                if datetime.strptime(date_str, "%b %d, %Y") <= min_dt:
                    continue
            except ValueError:
                pass
        full_url = urljoin(BASE_URL + "/", href)
        slug = slug_from_mini_url(full_url)
        if slug in seen_slugs:
            slug = f"{slug}_{len(seen_slugs)}"
        seen_slugs.add(slug)
        items.append(
            {
                "slug": slug,
                "title": title,
                "url": full_url,
                "date": date_str,
                "num_players": players_cell.get_text(" ", strip=True) if players_cell else "",
            }
        )
    return sorted(items, key=lambda x: x["title"].lower())


def parse_minileague_match_links(html: str) -> list[tuple[str, str]]:
    """Parse ordered match day links from a Mini League overview page."""
    soup = BeautifulSoup(html, "html.parser")
    mtch_table = soup.find("table", {"class": "mtch"})
    if not mtch_table:
        return []
    links: list[tuple[str, str]] = []
    for row in mtch_table.find_all("tr"):
        anchor = row.find("a")
        if not anchor or not anchor.get("href"):
            continue
        href = str(anchor.get("href"))
        # Skip championship match day 12 link as in v8
        if "12" in href:
            continue
        label = re.split(r"(Match[^M]*|Champ[C]+)", row.get_text(" ", strip=True))[0].strip()
        links.append((label or f"Day {len(links) + 1}", urljoin(BASE_URL + "/", href)))
    return links


def parse_minileague_match_day(html: str, day_index: int) -> list[dict[str, Any]]:
    """Parse all questions/answers and % correct from a single Mini League match day."""
    soup = BeautifulSoup(html, "html.parser")
    items = soup.find_all(True, {"class": ["ind-Q20", "a-red"]})
    pct_cells: list[str] = []
    mini_table = soup.find("table", {"class": "std mini"})
    if mini_table and mini_table.find("tfoot"):
        pct_cells = [
            td.get_text(strip=True)
            for td in mini_table.find("tfoot").find_all("td", {"class": "ind-Q3-t"})
        ][2:-1]

    questions: list[dict[str, Any]] = []
    pair_idx = 0
    i = 0
    while i + 1 < len(items):
        q_el = items[i]
        a_el = items[i + 1]
        if "ind-Q20" not in (q_el.get("class") or []) or "a-red" not in (a_el.get("class") or []):
            i += 1
            continue
        raw_q = q_el.get_text(" ", strip=True)
        if "-" in raw_q:
            q_label_raw, q_text = raw_q.split("-", 1)
            q_label = q_label_raw.strip().split(".")[0].strip()
            q_text = q_text.strip()
        else:
            q_label = f"Q{pair_idx + 1}"
            q_text = raw_q
        pct = pct_cells[pair_idx] if pair_idx < len(pct_cells) else "0"
        pct_num = int(re.sub(r"[^0-9]", "", pct) or "0")
        questions.append(
            {
                "day": day_index,
                "label": q_label,
                "question": q_text,
                "answer": a_el.get_text(" ", strip=True),
                "percent": pct_num,
            }
        )
        pair_idx += 1
        i += 2

    return questions


def fetch_minileagues_catalog(
    cache,
    rate_limiter,
    *,
    force: bool = False,
    browser_manager: Any | None = None,
) -> list[dict[str, str]]:
    if not force:
        cached = cache.get_minileagues_catalog()
        if cached is not None:
            return cached
    with build_ll_client(rate_limiter, browser_manager) as client:
        html = client.get_text(MINILEAGUES_LIST_URL)
    items = parse_minileague_catalog(html)
    if items:
        cache.set_minileagues_catalog(items)
    return items


def fetch_minileague_detail(
    slug: str,
    cache,
    rate_limiter,
    *,
    browser_manager: Any | None = None,
) -> dict[str, Any]:
    cached = cache.get_minileague_detail(slug)
    if cached is not None:
        return cached
    meta = cache.get_minileague_catalog_item(slug)
    if not meta:
        catalog = fetch_minileagues_catalog(
            cache, rate_limiter, browser_manager=browser_manager
        )
        meta = next((item for item in catalog if item["slug"] == slug), None)
    if not meta:
        raise LLNotFoundError(f"Mini League '{slug}' was not found.")

    all_questions: list[dict[str, Any]] = []
    match_days: list[dict[str, Any]] = []
    with build_ll_client(rate_limiter, browser_manager) as client:
        overview_html = client.get_text(meta["url"])
        match_links = parse_minileague_match_links(overview_html)
        for day_idx, (label, match_url) in enumerate(match_links, start=1):
            day_html = client.get_text(match_url)
            day_questions = parse_minileague_match_day(day_html, day_idx)
            for q in day_questions:
                q["index"] = len(all_questions) + 1
                all_questions.append(q)
            match_days.append({"day": day_idx, "label": label, "questions": day_questions})

    pct_values = [q["percent"] for q in all_questions]
    overall_correct = round(sum(pct_values) / len(pct_values), 2) if pct_values else 0.0

    detail = {
        "slug": meta["slug"],
        "title": meta["title"],
        "date": meta.get("date", ""),
        "url": meta["url"],
        "num_players": meta.get("num_players", ""),
        "overall_correct": overall_correct,
        "total_questions": len(all_questions),
        "match_days": match_days,
    }
    cache.set_minileague_detail(slug, detail)
    return detail
