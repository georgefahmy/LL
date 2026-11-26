from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..browser_session import build_ll_client
from ..constants import BASE_URL, EXCLUDED_QUIZ_MARKERS, ONEDAYS_LIST_URL
from ..http_client import LLNotFoundError


def slug_from_oneday_url(url: str) -> str:
    parsed = urlparse(url)
    raw = parsed.query or parsed.path.rstrip("/").split("/")[-1]
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_")
    return slug or "oneday"


def parse_oneday_catalog(
    html: str,
    *,
    now: datetime | None = None,
) -> list[dict[str, str]]:
    """Parse available OneDay Specials from onedaysalpha.php."""
    current_dt = now or datetime.now()
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")
    body_rows = rows[1:-1] if len(rows) > 2 else rows[1:]

    items: list[dict[str, str]] = []
    seen_slugs: set[str] = set()
    for row in body_rows:
        title_cell = row.find("td", {"class": "std-left"})
        date_cell = row.find("td", {"class": "std-midleft"})
        if not title_cell or not title_cell.find("a"):
            continue
        title = title_cell.get_text(" ", strip=True)
        if any(marker in title for marker in EXCLUDED_QUIZ_MARKERS):
            continue
        href = str(title_cell.find("a").get("href") or "").strip()
        if not href:
            continue
        date_str = date_cell.get_text(" ", strip=True) if date_cell else ""
        if date_str:
            try:
                if datetime.strptime(date_str, "%b %d, %Y") >= current_dt:
                    continue
            except ValueError:
                pass
        full_url = urljoin(BASE_URL + "/", href)
        slug = slug_from_oneday_url(full_url)
        if slug in seen_slugs:
            slug = f"{slug}_{len(seen_slugs)}"
        seen_slugs.add(slug)
        items.append(
            {
                "slug": slug,
                "title": title,
                "url": full_url,
                "date": date_str,
            }
        )
    return items


def parse_oneday_detail(
    html: str,
    metrics_html: str | None,
    meta: dict[str, Any],
) -> dict[str, Any]:
    """Parse OneDay questions, answers, blurb, ModKos rating, and percentiles safely."""
    soup = BeautifulSoup(html, "html.parser")
    qs_div = soup.find("div", {"id": "qs_close", "class": "qdivshow_wide"}) or soup.find(
        "div", {"id": "qs_close"}
    )
    if not qs_div:
        raise LLNotFoundError(f"OneDay questions not available for '{meta.get('title', '')}'.")

    raw_questions: list[str] = []
    for p in qs_div.find_all("p"):
        text = p.get_text(" ", strip=True)
        if "." in text:
            raw_questions.append(text.split(".", 1)[1].strip())
        else:
            raw_questions.append(text)

    raw_answers = [
        a.get_text("\n", strip=True).split("\n")[-1].strip()
        for a in qs_div.find_all("div", {"class": "answer3"})
    ]

    question_metrics: list[int] = [0] * len(raw_questions)
    percentile_info: dict[str, int] = {}
    number_of_players = 0

    if metrics_html:
        m_soup = BeautifulSoup(metrics_html, "html.parser")
        q_container = m_soup.find("div", {"class": "q_container"})
        if q_container and q_container.find("table", {"class": "tbl_q"}):
            tbl_rows = q_container.find("table", {"class": "tbl_q"}).find_all("tr")[1:]
            parsed_metrics: list[int] = []
            for m_row in tbl_rows:
                parts = m_row.get_text(" ", strip=True).split()
                val = 0
                if len(parts) >= 2 and parts[1].rstrip("%").isdigit():
                    val = int(parts[1].rstrip("%"))
                elif parts and parts[-1].rstrip("%").isdigit():
                    val = int(parts[-1].rstrip("%"))
                parsed_metrics.append(val)
            for idx in range(min(len(parsed_metrics), len(question_metrics))):
                question_metrics[idx] = parsed_metrics[idx]

        pct_container = m_soup.find("div", {"class": "pctile_container"})
        if pct_container:
            pr_cells = pct_container.find_all("td", {"class": "pr"})
            val_cells = pct_container.find_all("td", {"class": None})
            for pr_td, val_td in zip(pr_cells, val_cells, strict=False):
                pr_text = pr_td.get_text(strip=True)
                val_norm = unicodedata.normalize("NFKD", val_td.get_text(strip=True)).strip()
                if pr_text.isdigit() and val_norm.isdigit():
                    percentile_info[pr_text] = int(val_norm)

        byl_container = m_soup.find("div", {"class": "byl_container"})
        if byl_container:
            for row in byl_container.find_all("tr")[1:]:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    num_txt = cells[1].get_text(strip=True)
                    if num_txt.isdigit():
                        number_of_players += int(num_txt)

    blurb_div = soup.find("div", {"id": "blurb_close"})
    if blurb_div:
        raw_blurb = blurb_div.get_text("\n", strip=True)
        if "blurb" in raw_blurb.lower():
            idx = raw_blurb.lower().find("blurb") + 5
            raw_blurb = raw_blurb[idx:].lstrip(" :\r\n")
        blurb = re.sub(r"[\r\n]+", "\n", raw_blurb).strip()
    else:
        blurb = ""

    modkos_rating = "None"
    if "ModKos" in blurb:
        ratings = {"G", "PG", "PG-13", "R", "X"}
        for token in blurb.split():
            cleaned = token.replace(".", "").replace(",", "").strip()
            if cleaned in ratings:
                modkos_rating = cleaned
                break

    overall_avg = (
        round(sum(question_metrics) / len(question_metrics), 2) if question_metrics else 0.0
    )

    questions = []
    for idx, q_text in enumerate(raw_questions):
        questions.append(
            {
                "question_num": str(idx + 1),
                "question": q_text,
                "answer": raw_answers[idx] if idx < len(raw_answers) else "",
                "percent": question_metrics[idx] if idx < len(question_metrics) else 0,
            }
        )

    return {
        "slug": meta["slug"],
        "title": meta["title"],
        "date": meta.get("date", ""),
        "url": meta["url"],
        "blurb": blurb,
        "difficulty_rating": modkos_rating,
        "overall_average": overall_avg,
        "p90": percentile_info.get("90"),
        "p50": percentile_info.get("50"),
        "p10": percentile_info.get("10"),
        "percentiles": percentile_info,
        "number_of_players": number_of_players,
        "questions": questions,
    }


def extract_oneday_metrics_url(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    tabs = soup.find("ul", {"id": "profilestabs"})
    if tabs and tabs.find("a") and tabs.find("a").get("href"):
        return urljoin(BASE_URL + "/", str(tabs.find("a").get("href")))
    return None


def fetch_onedays_catalog(
    cache,
    rate_limiter,
    *,
    force: bool = False,
    browser_manager: Any | None = None,
) -> list[dict[str, str]]:
    if not force:
        cached = cache.get_onedays_catalog()
        if cached is not None:
            return cached
    with build_ll_client(rate_limiter, browser_manager) as client:
        html = client.get_text(ONEDAYS_LIST_URL)
    items = parse_oneday_catalog(html)
    if items:
        cache.set_onedays_catalog(items)
    return items


def fetch_oneday_detail(
    slug: str,
    cache,
    rate_limiter,
    *,
    browser_manager: Any | None = None,
) -> dict[str, Any]:
    cached = cache.get_oneday_detail(slug)
    if cached is not None:
        return cached
    meta = cache.get_oneday_catalog_item(slug)
    if not meta:
        catalog = fetch_onedays_catalog(
            cache, rate_limiter, browser_manager=browser_manager
        )
        meta = next((item for item in catalog if item["slug"] == slug), None)
    if not meta:
        raise LLNotFoundError(f"OneDay '{slug}' was not found.")

    with build_ll_client(rate_limiter, browser_manager) as client:
        html = client.get_text(meta["url"])
        metrics_url = extract_oneday_metrics_url(html)
        metrics_html = None
        if metrics_url:
            try:
                metrics_html = client.get_text(metrics_url)
            except Exception:
                metrics_html = None

    detail = parse_oneday_detail(html, metrics_html, meta)
    cache.set_oneday_detail(slug, detail)
    return detail
