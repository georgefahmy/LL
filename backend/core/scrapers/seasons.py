from __future__ import annotations

import logging
import random
import re
import threading
import time
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, SoupStrainer

from ..browser_session import build_ll_client
from ..cache import CacheStore
from ..constants import ALL_RUNDLES_URL, BASE_URL, MIN_AVAILABLE_SEASON
from ..http_client import (
    LLAuthExpiredError,
    LLParseError,
    LLRateLimitError,
    TokenBucketRateLimiter,
)

logger = logging.getLogger(__name__)


def parse_season_and_day(html: str) -> tuple[int, int]:
    """Parse current LearnedLeague (season, match_day) from allrundles.php HTML."""
    if not html or not html.strip():
        raise LLParseError("Empty HTML received from allrundles.php")

    h1_soup = BeautifulSoup(html, "html.parser", parse_only=SoupStrainer("h1"))
    h3_soup = BeautifulSoup(html, "html.parser", parse_only=SoupStrainer("h3"))
    table_soup = BeautifulSoup(html, "html.parser", parse_only=SoupStrainer("table"))

    season: int | None = None
    h1_el = h1_soup.find("h1")
    if h1_el:
        m = re.search(r"LL\s*(\d+)", h1_el.get_text(" ", strip=True), re.IGNORECASE)
        if m:
            season = int(m.group(1))

    if season is None:
        raise LLParseError("Could not parse current LearnedLeague season from allrundles.php")

    h3_el = h3_soup.find("h3")
    if h3_el:
        m = re.search(r"(\d+)\s*$", h3_el.get_text(" ", strip=True))
        if m:
            return season, int(m.group(1))

    md_tables = table_soup.find_all("table", {"class": "MDTable"})
    if md_tables:
        rows = md_tables[0].find_all("tr")
        for idx, row in enumerate(rows):
            text = row.get_text(" ", strip=True)
            if "Active" in text:
                m = re.search(r"Match\s*Day\s*(\d+)", text, re.IGNORECASE)
                if m:
                    return season, int(m.group(1))
                return season, max(0, idx - 1)
        data_rows = rows[1:-1] if len(rows) > 2 else rows[1:]
        if data_rows:
            last_cells = data_rows[-1].find_all("td")
            if last_cells and last_cells[-1].get_text(strip=True).isdigit():
                m = re.search(r"(\d+)", last_cells[0].get_text(" ", strip=True))
                if m:
                    return season, int(m.group(1))
            for idx, row in enumerate(data_rows):
                if not row.find("a"):
                    return season, max(0, idx)

    return season, 0


def parse_match_day_questions(html: str, season: int, day: int) -> list[dict[str, Any]]:
    """Parse 6 match-day questions, answers, percentages, defense, and rundle stats."""
    if not html or not html.strip():
        return []

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")
    q_divs = soup.find_all("div", {"class": "ind-Q20"})
    ans_divs = soup.find_all("div", {"class": "a-red"})

    if not rows or not q_divs or not ans_divs:
        return []

    categories: list[str] = []
    questions: list[str] = []
    clickable_links: list[str] = []

    for div in q_divs:
        raw_text = div.get_text(" ", strip=True)
        if "-" in raw_text:
            prefix, rest = raw_text.split("-", 1)
            cat = prefix.split(".")[-1].strip()
            q_text = rest.strip()
        else:
            cat = ""
            q_text = raw_text
        categories.append(cat)
        questions.append(q_text)

        non_span_links = [
            a for a in div.find_all("a") if a.get("href") and not a.find_parent("span")
        ]
        if len(non_span_links) == 1:
            clickable_links.append(urljoin(BASE_URL + "/", str(non_span_links[0].get("href"))))
        else:
            clickable_links.append("")

    answers = [div.get_text(" ", strip=True) for div in ans_divs]
    matchday_h1 = soup.find("h1", {"class": "matchday"})
    date_str = (
        matchday_h1.get_text(" ", strip=True).split(":")[0].strip() if matchday_h1 else ""
    )

    pct_row_cells = (
        [c.get_text(strip=True) for c in rows[-2].find_all("td", {"class": "ind-Q3"})][2:-1]
        if len(rows) >= 2
        else []
    )
    def_row_cells = (
        [c.get_text(strip=True) for c in rows[-1].find_all("td", {"class": "ind-Q3"})][2:-1]
        if len(rows) >= 1
        else []
    )

    rundle_rows = [
        [c.get_text(strip=True) for c in r.find_all("td", {"class": "ind-Q3"})][2:-1]
        for r in rows[1:8]
    ]
    rundle_keys = ["A", "B", "C", "D", "E", "R"]

    records: list[dict[str, Any]] = []
    count = min(len(questions), len(answers))
    for j in range(count):
        q_num = j + 1
        day_code = f"D{day:02d}Q{q_num}"
        qcode = f"S{season}{day_code}"
        pct_raw = pct_row_cells[j] if j < len(pct_row_cells) else "0"
        pct_digits = re.sub(r"[^0-9]", "", pct_raw)
        pct_int = int(pct_digits) if pct_digits else 0
        defense_val = def_row_cells[j] if j < len(def_row_cells) else ""

        rec: dict[str, Any] = {
            "qcode": qcode,
            "season": season,
            "day": day,
            "q_num": q_num,
            "question_num": day_code,
            "question": questions[j],
            "answer": answers[j],
            "category": categories[j],
            "percent": pct_int,
            "defense": defense_val,
            "date": date_str,
            "url": f"{BASE_URL}/question.php?{season}&{day}&{q_num}",
            "clickable_link": clickable_links[j],
        }
        for r_idx, r_key in enumerate(rundle_keys):
            if r_idx < len(rundle_rows) and j < len(rundle_rows[r_idx]):
                rec[r_key] = rundle_rows[r_idx][j]
            else:
                rec[r_key] = ""
        records.append(rec)

    return records


class SeasonSyncWorker:
    """Non-blocking background worker to incrementally sync missing LL match days."""

    def __init__(
        self,
        cache: CacheStore,
        rate_limiter: TokenBucketRateLimiter,
        *,
        seed_url: str = "",
        sync_interval_hours: int = 6,
        sync_delay_seconds: float = 2.5,
        max_days_per_run: int = 25,
        browser_manager: Any | None = None,
    ) -> None:
        self._cache = cache
        self._rate_limiter = rate_limiter
        self._seed_url = seed_url.strip()
        self._sync_interval_seconds = max(1, sync_interval_hours) * 3600
        self._sync_delay_seconds = max(0.0, float(sync_delay_seconds))
        self._max_days_per_run = max(0, int(max_days_per_run))
        self._browser_manager = browser_manager
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._status_lock = threading.Lock()
        self._status: dict[str, Any] = {
            "running": False,
            "phase": "idle",
            "latest_season": None,
            "current_day": None,
            "total_missing_days": 0,
            "completed_days": 0,
            "remaining_missing_days": 0,
            "last_synced_at": self._cache.get_meta("last_synced_at"),
            "last_error": None,
        }

    def status(self) -> dict[str, Any]:
        with self._status_lock:
            return dict(self._status)

    def _update_status(self, **kwargs: Any) -> None:
        with self._status_lock:
            self._status.update(kwargs)

    def record_external_sync(
        self,
        *,
        latest_season: int | None = None,
        current_day: int | None = None,
        last_synced_at: str | None = None,
        remaining_missing_days: int | None = None,
    ) -> None:
        """Clear stale error status after a successful external (extension) sync."""
        with self._status_lock:
            if self._status["running"]:
                return
            self._status["phase"] = "idle"
            self._status["last_error"] = None
            if latest_season is not None:
                self._status["latest_season"] = latest_season
            if current_day is not None:
                self._status["current_day"] = current_day
            if last_synced_at is not None:
                self._status["last_synced_at"] = last_synced_at
            if remaining_missing_days is not None:
                self._status["remaining_missing_days"] = remaining_missing_days

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="ll-season-sync",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def trigger_now(self) -> bool:
        with self._status_lock:
            if self._status["running"]:
                return False
        self._wake_event.set()
        return True

    def _run_loop(self) -> None:
        # Initial sync immediately on background start
        self.sync_once()
        while not self._stop_event.is_set():
            triggered = self._wake_event.wait(timeout=self._sync_interval_seconds)
            self._wake_event.clear()
            if self._stop_event.is_set():
                break
            if triggered or True:
                self.sync_once()

    def _try_seed_from_remote(self) -> None:
        if not self._seed_url or self._cache.count_questions() >= 100:
            return
        self._update_status(phase="seeding_from_server")
        try:
            resp = httpx.get(self._seed_url, timeout=30.0, follow_redirects=True)
            if resp.status_code == 200 and resp.content:
                imported = self._cache.seed_from_gzip_bytes(resp.content)
                logger.info("Seeded %d questions from %s", imported, self._seed_url)
        except Exception as exc:
            logger.warning("Optional seed fetch failed (%s): %s", self._seed_url, exc)

    def sync_once(self) -> None:
        with self._status_lock:
            if self._status["running"]:
                return
            self._status["running"] = True
            self._status["last_error"] = None
            self._status["phase"] = "checking"

        try:
            self._try_seed_from_remote()
            with build_ll_client(self._rate_limiter, self._browser_manager) as client:
                allrundles_html = client.get_text(ALL_RUNDLES_URL)
                latest_season, current_day = parse_season_and_day(allrundles_html)
                self._cache.set_meta("latest_season", str(latest_season))
                self._cache.set_meta("current_day", str(current_day))

                existing_days = self._cache.get_existing_season_days()
                missing: list[tuple[int, int]] = []
                for season in range(MIN_AVAILABLE_SEASON, latest_season + 1):
                    max_day = 25 if season < latest_season else min(25, current_day)
                    for day in range(1, max_day + 1):
                        if (season, day) not in existing_days:
                            missing.append((season, day))

                # Sync newest seasons first so recent questions appear right away
                missing.sort(key=lambda item: (-item[0], item[1]))
                if self._max_days_per_run > 0 and len(missing) > self._max_days_per_run:
                    batch = missing[: self._max_days_per_run]
                    remaining_after_batch = len(missing) - len(batch)
                else:
                    batch = missing
                    remaining_after_batch = 0

                self._update_status(
                    latest_season=latest_season,
                    current_day=current_day,
                    total_missing_days=len(batch),
                    completed_days=0,
                    remaining_missing_days=remaining_after_batch,
                    phase="syncing" if batch else "idle",
                )

                for idx, (season, day) in enumerate(batch, start=1):
                    if self._stop_event.is_set():
                        break
                    if idx > 1 and self._sync_delay_seconds > 0.0:
                        delay = self._sync_delay_seconds + random.uniform(0.0, 1.0)
                        if self._stop_event.wait(timeout=delay):
                            break
                    url = f"{BASE_URL}/match.php?{season}&{day}"
                    try:
                        html = client.get_text(url)
                        records = parse_match_day_questions(html, season, day)
                        if records:
                            self._cache.upsert_questions(records)
                    except (LLRateLimitError, LLAuthExpiredError) as exc:
                        logger.warning(
                            "Aborting archive sync at S%sD%s: %s", season, day, exc
                        )
                        raise
                    except Exception as exc:
                        logger.warning("Failed syncing S%sD%s: %s", season, day, exc)
                    self._update_status(completed_days=idx)

            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._cache.set_meta("last_synced_at", now_iso)
            self._update_status(
                running=False,
                phase="idle",
                last_synced_at=now_iso,
            )
        except Exception as exc:
            logger.warning("Background season sync failed: %s", exc)
            self._update_status(
                running=False,
                phase="error",
                last_error=str(exc),
            )
