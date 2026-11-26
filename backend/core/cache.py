from __future__ import annotations

import gzip
import json
import logging
import re
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_QCODE_RE = re.compile(r"^S(\d+)D(\d+)Q(\d+)$", re.IGNORECASE)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return default


def _parse_qcode(qcode: str, record: dict[str, Any]) -> tuple[int, int, int]:
    match = _QCODE_RE.match(qcode.strip())
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    season = _safe_int(record.get("season"), 0)
    qnum_str = str(record.get("question_num", ""))
    m2 = re.match(r"D(\d+)Q(\d+)", qnum_str, re.IGNORECASE)
    if m2:
        return season, int(m2.group(1)), int(m2.group(2))
    return season, 0, 0


class CacheStore:
    """Thread-safe SQLite WAL persistence for public cache, auth TTL cache, and desktop state."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _init_schema(self) -> None:
        with self._tx() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA busy_timeout=5000;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS questions (
                    qcode TEXT PRIMARY KEY,
                    season INTEGER NOT NULL,
                    day INTEGER NOT NULL,
                    q_num INTEGER NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    category TEXT NOT NULL,
                    percent INTEGER NOT NULL,
                    defense TEXT NOT NULL DEFAULT '',
                    date TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL DEFAULT '',
                    clickable_link TEXT NOT NULL DEFAULT '',
                    rundle_a TEXT NOT NULL DEFAULT '',
                    rundle_b TEXT NOT NULL DEFAULT '',
                    rundle_c TEXT NOT NULL DEFAULT '',
                    rundle_d TEXT NOT NULL DEFAULT '',
                    rundle_e TEXT NOT NULL DEFAULT '',
                    rundle_r TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_questions_season_day ON questions(season, day);
                CREATE INDEX IF NOT EXISTS idx_questions_category ON questions(category);
                CREATE INDEX IF NOT EXISTS idx_questions_percent ON questions(percent);

                CREATE TABLE IF NOT EXISTS onedays_catalog (
                    slug TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    date TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS onedays_detail (
                    slug TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS minileagues_catalog (
                    slug TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    date TEXT NOT NULL,
                    num_players TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS minileagues_detail (
                    slug TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sync_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                -- Auth-gated TTL caches (never served without verified LL session)
                CREATE TABLE IF NOT EXISTS player_profiles_cache (
                    lookup_key TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    fetched_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS leaguewide_csv_cache (
                    cache_key TEXT PRIMARY KEY,
                    season INTEGER NOT NULL,
                    matchday INTEGER NOT NULL,
                    csv_text TEXT NOT NULL,
                    fetched_at REAL NOT NULL
                );

                -- Desktop-mode local personal persistence
                CREATE TABLE IF NOT EXISTS local_practice_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    qcode TEXT NOT NULL,
                    submitted_answer TEXT NOT NULL,
                    correct INTEGER NOT NULL,
                    override INTEGER NOT NULL DEFAULT 0,
                    answered_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_local_practice_qcode
                    ON local_practice_answers(qcode);

                CREATE TABLE IF NOT EXISTS local_oneday_attempts (
                    slug TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    percentile TEXT NOT NULL DEFAULT '',
                    completed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS local_favorites (
                    username TEXT PRIMARY KEY,
                    added_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS local_mock_days (
                    uuid TEXT PRIMARY KEY,
                    code TEXT NOT NULL,
                    seed INTEGER,
                    threshold INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    # ---- Sync Meta ----

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM sync_meta WHERE key = ?", (key,)).fetchone()
            return str(row["value"]) if row else default

    def set_meta(self, key: str, value: str) -> None:
        now = _utc_now_iso()
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO sync_meta(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value, now),
            )

    # ---- Questions ----

    def count_questions(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS cnt FROM questions").fetchone()
            return int(row["cnt"]) if row else 0

    def get_existing_season_days(self) -> set[tuple[int, int]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT season, day
                FROM questions
                GROUP BY season, day
                HAVING COUNT(*) >= 6
                """
            ).fetchall()
            return {(int(r["season"]), int(r["day"])) for r in rows}

    def get_max_season_day(self) -> tuple[int, int]:
        with self._lock:
            row = self._conn.execute(
                "SELECT MAX(season) AS max_season FROM questions"
            ).fetchone()
            if not row or row["max_season"] is None:
                return 102, 0
            max_season = int(row["max_season"])
            day_row = self._conn.execute(
                "SELECT MAX(day) AS max_day FROM questions WHERE season = ?",
                (max_season,),
            ).fetchone()
            max_day = int(day_row["max_day"]) if day_row and day_row["max_day"] is not None else 0
            return max_season, max_day

    def upsert_questions(self, records: list[dict[str, Any]]) -> int:
        if not records:
            return 0
        now = _utc_now_iso()
        rows: list[tuple[Any, ...]] = []
        for rec in records:
            qcode = str(rec["qcode"]).strip()
            rows.append(
                (
                    qcode,
                    int(rec["season"]),
                    int(rec["day"]),
                    int(rec["q_num"]),
                    str(rec["question"]),
                    str(rec["answer"]),
                    str(rec["category"]),
                    _safe_int(rec.get("percent"), 0),
                    str(rec.get("defense", "")),
                    str(rec.get("date", "")),
                    str(rec.get("url", "")),
                    str(rec.get("clickable_link", "")),
                    str(rec.get("A", rec.get("rundle_a", ""))),
                    str(rec.get("B", rec.get("rundle_b", ""))),
                    str(rec.get("C", rec.get("rundle_c", ""))),
                    str(rec.get("D", rec.get("rundle_d", ""))),
                    str(rec.get("E", rec.get("rundle_e", ""))),
                    str(rec.get("R", rec.get("rundle_r", ""))),
                    now,
                )
            )
        with self._tx() as conn:
            conn.executemany(
                """
                INSERT INTO questions (
                    qcode, season, day, q_num, question, answer, category, percent,
                    defense, date, url, clickable_link,
                    rundle_a, rundle_b, rundle_c, rundle_d, rundle_e, rundle_r, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(qcode) DO UPDATE SET
                    question=excluded.question,
                    answer=excluded.answer,
                    category=excluded.category,
                    percent=excluded.percent,
                    defense=excluded.defense,
                    date=excluded.date,
                    url=excluded.url,
                    clickable_link=excluded.clickable_link,
                    rundle_a=excluded.rundle_a,
                    rundle_b=excluded.rundle_b,
                    rundle_c=excluded.rundle_c,
                    rundle_d=excluded.rundle_d,
                    rundle_e=excluded.rundle_e,
                    rundle_r=excluded.rundle_r,
                    updated_at=excluded.updated_at
                """,
                rows,
            )
        return len(rows)

    @staticmethod
    def _row_to_question(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "qcode": row["qcode"],
            "season": row["season"],
            "day": row["day"],
            "q_num": row["q_num"],
            "question_num": f"D{int(row['day']):02d}Q{int(row['q_num'])}",
            "question": row["question"],
            "answer": row["answer"],
            "category": row["category"],
            "percent": row["percent"],
            "defense": row["defense"],
            "date": row["date"],
            "url": row["url"],
            "clickable_link": row["clickable_link"],
            "rundles": {
                "A": row["rundle_a"],
                "B": row["rundle_b"],
                "C": row["rundle_c"],
                "D": row["rundle_d"],
                "E": row["rundle_e"],
                "R": row["rundle_r"],
            },
        }

    def get_question(self, qcode: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM questions WHERE qcode = ?",
                (qcode.upper().strip(),),
            ).fetchone()
            return self._row_to_question(row) if row else None

    def query_questions(
        self,
        *,
        min_pct: int = 0,
        max_pct: int = 100,
        category: str = "ALL",
        season: int | None = None,
        search: str = "",
        limit: int = 50,
        offset: int = 0,
        random_one: bool = False,
    ) -> dict[str, Any]:
        min_p = max(0, min(100, min_pct))
        max_p = max(min_p, min(100, max_pct))
        clauses = ["percent >= ? AND percent <= ?"]
        params: list[Any] = [min_p, max_p]

        if category and category.upper() != "ALL":
            clauses.append("UPPER(category) = UPPER(?)")
            params.append(category.strip())

        if season is not None:
            clauses.append("season = ?")
            params.append(season)

        if search.strip():
            clauses.append("LOWER(question) LIKE ?")
            params.append(f"%{search.strip().lower()}%")

        where_sql = " AND ".join(clauses)
        with self._lock:
            total_row = self._conn.execute(
                f"SELECT COUNT(*) AS cnt FROM questions WHERE {where_sql}",
                params,
            ).fetchone()
            total = int(total_row["cnt"]) if total_row else 0

            if random_one:
                rows = self._conn.execute(
                    f"SELECT * FROM questions WHERE {where_sql} ORDER BY RANDOM() LIMIT 1",
                    params,
                ).fetchall()
            else:
                rows = self._conn.execute(
                    f"""
                    SELECT * FROM questions
                    WHERE {where_sql}
                    ORDER BY season DESC, day DESC, q_num ASC
                    LIMIT ? OFFSET ?
                    """,
                    [*params, limit, offset],
                ).fetchall()

            cat_rows = self._conn.execute(
                "SELECT DISTINCT category FROM questions ORDER BY category ASC"
            ).fetchall()
            seas_rows = self._conn.execute(
                "SELECT DISTINCT season FROM questions ORDER BY season DESC"
            ).fetchall()

        return {
            "items": [self._row_to_question(r) for r in rows],
            "total": total,
            "categories": [str(r["category"]) for r in cat_rows if r["category"]],
            "seasons": [int(r["season"]) for r in seas_rows],
        }

    def list_questions_for_mock(self, threshold: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM questions WHERE percent > ? ORDER BY qcode ASC",
                (threshold,),
            ).fetchall()
            return [self._row_to_question(r) for r in rows]

    def export_questions_gzip(self) -> bytes:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM questions ORDER BY qcode ASC").fetchall()
        payload: dict[str, dict[str, Any]] = {}
        for r in rows:
            payload[r["qcode"]] = {
                "_question": r["question"],
                "answer": r["answer"],
                "season": str(r["season"]),
                "date": r["date"],
                "category": r["category"],
                "percent": str(r["percent"]),
                "question_num": f"D{int(r['day']):02d}Q{int(r['q_num'])}",
                "defense": r["defense"],
                "url": r["url"],
                "clickable_link": r["clickable_link"],
                "A": r["rundle_a"],
                "B": r["rundle_b"],
                "C": r["rundle_c"],
                "D": r["rundle_d"],
                "E": r["rundle_e"],
                "R": r["rundle_r"],
            }
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return gzip.compress(raw)

    def import_legacy_all_data_dict(
        self,
        data: dict[str, Any],
        *,
        import_answers: bool = False,
    ) -> tuple[int, int]:
        records: list[dict[str, Any]] = []
        answer_rows: list[tuple[str, str, int, int, str]] = []
        for qcode, rec in data.items():
            if not isinstance(rec, dict):
                continue
            season, day, q_num = _parse_qcode(qcode, rec)
            if season <= 0:
                continue
            records.append(
                {
                    "qcode": qcode,
                    "season": season,
                    "day": day,
                    "q_num": q_num,
                    "question": rec.get("_question", rec.get("question", "")),
                    "answer": rec.get("answer", ""),
                    "category": rec.get("category", ""),
                    "percent": _safe_int(rec.get("percent"), 0),
                    "defense": rec.get("defense", ""),
                    "date": rec.get("date", ""),
                    "url": rec.get("url", ""),
                    "clickable_link": rec.get("clickable_link", ""),
                    "A": rec.get("A", ""),
                    "B": rec.get("B", ""),
                    "C": rec.get("C", ""),
                    "D": rec.get("D", ""),
                    "E": rec.get("E", ""),
                    "R": rec.get("R", ""),
                }
            )
            if import_answers and isinstance(rec.get("answers"), list):
                for ans in rec["answers"]:
                    if isinstance(ans, dict) and ans.get("answer") is not None:
                        answer_rows.append(
                            (
                                qcode,
                                str(ans.get("answer", "")),
                                1 if ans.get("correct") else 0,
                                1 if ans.get("override") else 0,
                                str(ans.get("date") or _utc_now_iso()),
                            )
                        )
        inserted_q = self.upsert_questions(records)
        inserted_a = 0
        if answer_rows:
            with self._tx() as conn:
                existing = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM local_practice_answers"
                ).fetchone()
                if existing and int(existing["cnt"]) == 0:
                    conn.executemany(
                        """
                        INSERT INTO local_practice_answers
                            (qcode, submitted_answer, correct, override, answered_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        answer_rows,
                    )
                    inserted_a = len(answer_rows)
        return inserted_q, inserted_a

    def seed_from_json(self, json_path: Path, *, import_answers: bool = False) -> tuple[int, int]:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return 0, 0
        return self.import_legacy_all_data_dict(data, import_answers=import_answers)

    def seed_from_gzip(self, gz_path: Path) -> int:
        with gzip.open(gz_path, "rt", encoding="utf-8") as fp:
            data = json.load(fp)
        if not isinstance(data, dict):
            return 0
        q_count, _ = self.import_legacy_all_data_dict(data, import_answers=False)
        return q_count

    def seed_from_gzip_bytes(self, gz_bytes: bytes) -> int:
        raw = gzip.decompress(gz_bytes).decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return 0
        q_count, _ = self.import_legacy_all_data_dict(data, import_answers=False)
        return q_count

    def migrate_legacy_directory(
        self,
        legacy_dir: Path,
        *,
        import_personal: bool = True,
    ) -> dict[str, int]:
        """Non-destructively migrate v8 ~/.LearnedLeague/ files into SQLite."""
        stats = {"questions": 0, "answers": 0, "favorites": 0, "onedays": 0, "mock_days": 0}
        if self.get_meta("legacy_migrated") == "1":
            return stats

        all_data_file = legacy_dir / "all_data.json"
        if all_data_file.is_file():
            try:
                q_cnt, a_cnt = self.seed_from_json(all_data_file, import_answers=import_personal)
                stats["questions"] = q_cnt
                stats["answers"] = a_cnt
            except Exception as exc:
                logger.warning("Failed migrating legacy all_data.json: %s", exc)

        if import_personal:
            fav_file = legacy_dir / "favorites.json"
            if fav_file.is_file():
                try:
                    favs = json.loads(fav_file.read_text(encoding="utf-8"))
                    if isinstance(favs, list):
                        for u in favs:
                            if isinstance(u, str) and u.strip():
                                self.add_favorite(u.strip())
                                stats["favorites"] += 1
                except Exception as exc:
                    logger.warning("Failed migrating legacy favorites.json: %s", exc)

            onedays_dir = legacy_dir / "onedays"
            if onedays_dir.is_dir():
                for path in onedays_dir.glob("*.json"):
                    try:
                        payload = json.loads(path.read_text(encoding="utf-8"))
                        if isinstance(payload, dict) and payload.get("title"):
                            slug = re.sub(r"[^A-Za-z0-9_-]+", "_", path.stem)
                            sub_date = payload.get("submission_date")
                            if isinstance(sub_date, list) and sub_date:
                                sub_date = str(sub_date[0])
                            self.save_local_oneday_attempt(
                                slug=slug,
                                title=str(payload["title"]),
                                payload=payload,
                                score=_safe_int(payload.get("score"), 0),
                                percentile=str(payload.get("final_percentile", "")),
                                completed_at=str(sub_date or _utc_now_iso()),
                            )
                            stats["onedays"] += 1
                    except Exception as exc:
                        logger.warning("Failed migrating legacy oneday %s: %s", path.name, exc)

            mock_dir = legacy_dir / "mock_matches"
            if mock_dir.is_dir():
                for path in mock_dir.glob("*.json"):
                    try:
                        payload = json.loads(path.read_text(encoding="utf-8"))
                        if isinstance(payload, dict) and payload.get("uuid"):
                            self.save_local_mock_day(
                                uuid=str(payload["uuid"]),
                                code=str(payload.get("code", "")),
                                seed=payload.get("seed"),
                                threshold=_safe_int(payload.get("threshold"), 0),
                                payload=payload,
                            )
                            stats["mock_days"] += 1
                    except Exception as exc:
                        logger.warning("Failed migrating legacy mock match %s: %s", path.name, exc)

        self.set_meta("legacy_migrated", "1")
        return stats

    # ---- OneDays & MiniLeagues Public Cache ----

    def get_onedays_catalog(self, max_age_seconds: int = 12 * 3600) -> list[dict[str, Any]] | None:
        updated_str = self.get_meta("onedays_catalog_ts")
        if not updated_str or (time.time() - float(updated_str)) > max_age_seconds:
            return None
        with self._lock:
            rows = self._conn.execute(
                "SELECT slug, title, url, date FROM onedays_catalog ORDER BY title ASC"
            ).fetchall()
            if not rows:
                return None
            return [dict(r) for r in rows]

    def set_onedays_catalog(self, items: list[dict[str, str]]) -> None:
        now = _utc_now_iso()
        with self._tx() as conn:
            conn.execute("DELETE FROM onedays_catalog")
            conn.executemany(
                "INSERT INTO onedays_catalog(slug, title, url, date, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                [(it["slug"], it["title"], it["url"], it["date"], now) for it in items],
            )
        self.set_meta("onedays_catalog_ts", str(time.time()))

    def get_oneday_catalog_item(self, slug: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT slug, title, url, date FROM onedays_catalog WHERE slug = ?",
                (slug,),
            ).fetchone()
            return dict(row) if row else None

    def get_oneday_detail(self, slug: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM onedays_detail WHERE slug = ?",
                (slug,),
            ).fetchone()
            return json.loads(row["payload_json"]) if row else None

    def set_oneday_detail(self, slug: str, payload: dict[str, Any]) -> None:
        now = _utc_now_iso()
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO onedays_detail(slug, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (slug, json.dumps(payload), now),
            )

    def get_minileagues_catalog(
        self, max_age_seconds: int = 12 * 3600
    ) -> list[dict[str, Any]] | None:
        updated_str = self.get_meta("minileagues_catalog_ts")
        if not updated_str or (time.time() - float(updated_str)) > max_age_seconds:
            return None
        with self._lock:
            rows = self._conn.execute(
                "SELECT slug, title, url, date, num_players "
                "FROM minileagues_catalog ORDER BY title ASC"
            ).fetchall()
            if not rows:
                return None
            return [dict(r) for r in rows]

    def set_minileagues_catalog(self, items: list[dict[str, str]]) -> None:
        now = _utc_now_iso()
        with self._tx() as conn:
            conn.execute("DELETE FROM minileagues_catalog")
            conn.executemany(
                """
                INSERT INTO minileagues_catalog(slug, title, url, date, num_players, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (it["slug"], it["title"], it["url"], it["date"], it.get("num_players", ""), now)
                    for it in items
                ],
            )
        self.set_meta("minileagues_catalog_ts", str(time.time()))

    def get_minileague_catalog_item(self, slug: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT slug, title, url, date, num_players "
                "FROM minileagues_catalog WHERE slug = ?",
                (slug,),
            ).fetchone()
            return dict(row) if row else None

    def get_minileague_detail(self, slug: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM minileagues_detail WHERE slug = ?",
                (slug,),
            ).fetchone()
            return json.loads(row["payload_json"]) if row else None

    def set_minileague_detail(self, slug: str, payload: dict[str, Any]) -> None:
        now = _utc_now_iso()
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO minileagues_detail(slug, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (slug, json.dumps(payload), now),
            )

    # ---- Auth-Only TTL Caches ----

    def get_cached_profile(
        self, lookup_key: str, ttl_minutes: int = 30
    ) -> dict[str, Any] | None:
        norm_key = lookup_key.strip().lower()
        with self._lock:
            row = self._conn.execute(
                """
                SELECT payload_json, fetched_at
                FROM player_profiles_cache
                WHERE lookup_key = ? OR profile_id = ? OR LOWER(username) = ?
                LIMIT 1
                """,
                (norm_key, norm_key, norm_key),
            ).fetchone()
            if not row:
                return None
            if (time.time() - float(row["fetched_at"])) > (ttl_minutes * 60):
                return None
            return json.loads(row["payload_json"])

    def set_cached_profile(self, profile: dict[str, Any]) -> None:
        profile_id = str(profile.get("profile_id", "")).strip()
        username = str(profile.get("username", "")).strip().lower()
        now = time.time()
        payload = json.dumps(profile)
        with self._tx() as conn:
            for key in {k for k in (username, profile_id) if k}:
                conn.execute(
                    """
                    INSERT INTO player_profiles_cache(
                        lookup_key, profile_id, username, payload_json, fetched_at
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(lookup_key) DO UPDATE SET
                        profile_id=excluded.profile_id,
                        username=excluded.username,
                        payload_json=excluded.payload_json,
                        fetched_at=excluded.fetched_at
                    """,
                    (key, profile_id, username, payload, now),
                )

    def list_cached_profile_names(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT payload_json FROM player_profiles_cache"
            ).fetchall()
        names: set[str] = set()
        for r in rows:
            try:
                data = json.loads(r["payload_json"])
                if data.get("formatted_username"):
                    names.add(str(data["formatted_username"]))
            except Exception:
                pass
        return sorted(names)

    def get_leaguewide_csv(
        self, season: int, matchday: int, max_age_seconds: int = 6 * 3600
    ) -> str | None:
        key = f"LL{season}_MD{matchday}"
        with self._lock:
            row = self._conn.execute(
                "SELECT csv_text, fetched_at FROM leaguewide_csv_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if not row:
                return None
            if (time.time() - float(row["fetched_at"])) > max_age_seconds:
                return None
            return str(row["csv_text"])

    def set_leaguewide_csv(self, season: int, matchday: int, csv_text: str) -> None:
        key = f"LL{season}_MD{matchday}"
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO leaguewide_csv_cache(cache_key, season, matchday, csv_text, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    csv_text=excluded.csv_text,
                    fetched_at=excluded.fetched_at
                """,
                (key, season, matchday, csv_text, time.time()),
            )

    # ---- Desktop-Local Personal Persistence ----

    def record_practice_answer(
        self,
        *,
        qcode: str,
        submitted_answer: str,
        correct: bool,
        override: bool = False,
    ) -> int:
        now = _utc_now_iso()
        with self._tx() as conn:
            cur = conn.execute(
                """
                INSERT INTO local_practice_answers
                    (qcode, submitted_answer, correct, override, answered_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (qcode, submitted_answer, 1 if correct else 0, 1 if override else 0, now),
            )
            return int(cur.lastrowid or 0)

    def override_practice_answer(
        self, answer_id: int, correct: bool, override: bool = True
    ) -> bool:
        with self._tx() as conn:
            cur = conn.execute(
                "UPDATE local_practice_answers SET correct = ?, override = ? WHERE id = ?",
                (1 if correct else 0, 1 if override else 0, answer_id),
            )
            return cur.rowcount > 0

    def list_practice_answers(self, qcode: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if qcode:
                rows = self._conn.execute(
                    """
                    SELECT * FROM local_practice_answers
                    WHERE qcode = ?
                    ORDER BY id DESC
                    """,
                    (qcode,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM local_practice_answers ORDER BY id DESC LIMIT 500"
                ).fetchall()
            return [
                {
                    "id": r["id"],
                    "qcode": r["qcode"],
                    "submitted_answer": r["submitted_answer"],
                    "correct": bool(r["correct"]),
                    "override": bool(r["override"]),
                    "answered_at": r["answered_at"],
                }
                for r in rows
            ]

    def list_favorites(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT username FROM local_favorites ORDER BY LOWER(username) ASC"
            ).fetchall()
            return [str(r["username"]) for r in rows]

    def add_favorite(self, username: str) -> list[str]:
        clean = username.strip()
        if not clean:
            return self.list_favorites()
        with self._tx() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO local_favorites(username, added_at)
                VALUES (?, ?)
                """,
                (clean, _utc_now_iso()),
            )
        return self.list_favorites()

    def set_favorites(self, usernames: list[str]) -> list[str]:
        cleaned = sorted({u.strip() for u in usernames if u.strip()}, key=str.lower)
        now = _utc_now_iso()
        with self._tx() as conn:
            conn.execute("DELETE FROM local_favorites")
            conn.executemany(
                "INSERT INTO local_favorites(username, added_at) VALUES (?, ?)",
                [(u, now) for u in cleaned],
            )
        return cleaned

    def remove_favorite(self, username: str) -> list[str]:
        with self._tx() as conn:
            conn.execute(
                "DELETE FROM local_favorites WHERE LOWER(username) = LOWER(?)",
                (username,),
            )
        return self.list_favorites()

    def save_local_oneday_attempt(
        self,
        *,
        slug: str,
        title: str,
        payload: dict[str, Any],
        score: int,
        percentile: str,
        completed_at: str | None = None,
    ) -> None:
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO local_oneday_attempts
                    (slug, title, payload_json, score, percentile, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    title=excluded.title,
                    payload_json=excluded.payload_json,
                    score=excluded.score,
                    percentile=excluded.percentile,
                    completed_at=excluded.completed_at
                """,
                (
                    slug,
                    title,
                    json.dumps(payload),
                    score,
                    percentile,
                    completed_at or _utc_now_iso(),
                ),
            )

    def list_local_oneday_attempts(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT slug, title, score, percentile, completed_at, payload_json "
                "FROM local_oneday_attempts ORDER BY completed_at DESC"
            ).fetchall()
            return [
                {
                    "slug": r["slug"],
                    "title": r["title"],
                    "score": r["score"],
                    "percentile": r["percentile"],
                    "completed_at": r["completed_at"],
                    "payload": json.loads(r["payload_json"]),
                }
                for r in rows
            ]

    def save_local_mock_day(
        self,
        *,
        uuid: str,
        code: str,
        seed: int | None,
        threshold: int,
        payload: dict[str, Any],
    ) -> None:
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO local_mock_days(uuid, code, seed, threshold, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(uuid) DO UPDATE SET
                    payload_json=excluded.payload_json
                """,
                (uuid, code, seed, threshold, json.dumps(payload), _utc_now_iso()),
            )

    def list_local_mock_days(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT uuid, code, seed, threshold, created_at, payload_json "
                "FROM local_mock_days ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
            return [
                {
                    "uuid": r["uuid"],
                    "code": r["code"],
                    "seed": r["seed"],
                    "threshold": r["threshold"],
                    "created_at": r["created_at"],
                    "payload": json.loads(r["payload_json"]),
                }
                for r in rows
            ]

    def export_personal_data(self) -> dict[str, Any]:
        return {
            "version": 1,
            "exported_at": _utc_now_iso(),
            "practice_answers": self.list_practice_answers(),
            "favorites": self.list_favorites(),
            "oneday_attempts": self.list_local_oneday_attempts(),
            "mock_days": self.list_local_mock_days(),
        }

    def import_personal_data(self, payload: dict[str, Any]) -> dict[str, int]:
        counts = {"practice_answers": 0, "favorites": 0, "oneday_attempts": 0, "mock_days": 0}
        if isinstance(payload.get("favorites"), list):
            for u in payload["favorites"]:
                if isinstance(u, str) and u.strip():
                    self.add_favorite(u)
                    counts["favorites"] += 1

        if isinstance(payload.get("practice_answers"), list):
            with self._tx() as conn:
                for item in payload["practice_answers"]:
                    if isinstance(item, dict) and item.get("qcode"):
                        conn.execute(
                            """
                            INSERT INTO local_practice_answers
                                (qcode, submitted_answer, correct, override, answered_at)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                str(item["qcode"]),
                                str(item.get("submitted_answer", "")),
                                1 if item.get("correct") else 0,
                                1 if item.get("override") else 0,
                                str(item.get("answered_at") or _utc_now_iso()),
                            ),
                        )
                        counts["practice_answers"] += 1

        if isinstance(payload.get("oneday_attempts"), list):
            for od in payload["oneday_attempts"]:
                if isinstance(od, dict) and od.get("slug"):
                    self.save_local_oneday_attempt(
                        slug=str(od["slug"]),
                        title=str(od.get("title", od["slug"])),
                        payload=od.get("payload", {}),
                        score=_safe_int(od.get("score"), 0),
                        percentile=str(od.get("percentile", "")),
                        completed_at=od.get("completed_at"),
                    )
                    counts["oneday_attempts"] += 1

        if isinstance(payload.get("mock_days"), list):
            for md in payload["mock_days"]:
                if isinstance(md, dict) and md.get("uuid"):
                    self.save_local_mock_day(
                        uuid=str(md["uuid"]),
                        code=str(md.get("code", "")),
                        seed=md.get("seed"),
                        threshold=_safe_int(md.get("threshold"), 0),
                        payload=md.get("payload", {}),
                    )
                    counts["mock_days"] += 1
        return counts
