from __future__ import annotations

import json
from pathlib import Path

from backend.core.cache import CacheStore


def test_cache_questions_query_and_gzip_roundtrip(tmp_path: Path) -> None:
    cache = CacheStore(tmp_path / "app.db")
    try:
        cache.upsert_questions(
            [
                {
                    "qcode": "S100D01Q1",
                    "season": 100,
                    "day": 1,
                    "q_num": 1,
                    "question": "Question about fast fashion",
                    "answer": "FAST FASHION",
                    "category": "BUS/ECON",
                    "percent": 78,
                    "defense": "1.0",
                    "date": "February 12, 2024",
                    "url": "https://www.learnedleague.com/question.php?100&1&1",
                    "clickable_link": "",
                    "A": "87",
                },
                {
                    "qcode": "S101D02Q3",
                    "season": 101,
                    "day": 2,
                    "q_num": 3,
                    "question": "Question about quantum physics",
                    "answer": "PHOTON",
                    "category": "SCIENCE",
                    "percent": 32,
                    "defense": "2.5",
                    "date": "May 1, 2024",
                    "url": "https://www.learnedleague.com/question.php?101&2&3",
                    "clickable_link": "",
                },
            ]
        )
        assert cache.count_questions() == 2

        res = cache.query_questions(category="SCIENCE", max_pct=50)
        assert res["total"] == 1
        assert res["items"][0]["qcode"] == "S101D02Q3"

        gz = cache.export_questions_gzip()
        cache2 = CacheStore(tmp_path / "app2.db")
        try:
            imported = cache2.seed_from_gzip_bytes(gz)
            assert imported == 2
            assert cache2.get_question("S100D01Q1")["answer"] == "FAST FASHION"
        finally:
            cache2.close()
    finally:
        cache.close()


def test_legacy_non_destructive_migration(tmp_path: Path) -> None:
    legacy_dir = tmp_path / "legacy"
    (legacy_dir / "onedays").mkdir(parents=True)
    (legacy_dir / "mock_matches").mkdir(parents=True)

    all_data_path = legacy_dir / "all_data.json"
    all_data_path.write_text(
        json.dumps(
            {
                "S100D01Q1": {
                    "_question": "Legacy question?",
                    "answer": "ANSWER",
                    "category": "SCIENCE",
                    "percent": "60",
                    "season": "100",
                    "question_num": "D01Q1",
                    "answers": [
                        {
                            "answer": "answer",
                            "date": "2024-05-01T12:00:00",
                            "correct": True,
                            "override": False,
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    (legacy_dir / "favorites.json").write_text(json.dumps(["Alice", "Bob"]), encoding="utf-8")
    (legacy_dir / "onedays" / "Space_Quiz.json").write_text(
        json.dumps({"title": "Space Quiz", "score": 120, "final_percentile": "90"}),
        encoding="utf-8",
    )
    (legacy_dir / "mock_matches" / "uuid-123.json").write_text(
        json.dumps({"uuid": "uuid-123", "code": "S100D01Q1", "seed": 5, "threshold": 0}),
        encoding="utf-8",
    )

    cache = CacheStore(legacy_dir / "app.db")
    try:
        stats = cache.migrate_legacy_directory(legacy_dir, import_personal=True)
        assert stats["questions"] == 1
        assert stats["answers"] == 1
        assert stats["favorites"] == 2
        assert stats["onedays"] == 1
        assert stats["mock_days"] == 1

        # Original files untouched
        assert all_data_path.is_file()
        assert cache.list_favorites() == ["Alice", "Bob"]
        assert len(cache.list_practice_answers("S100D01Q1")) == 1
    finally:
        cache.close()


def test_profile_ttl_cache(tmp_path: Path) -> None:
    cache = CacheStore(tmp_path / "ttl.db")
    try:
        cache.set_cached_profile(
            {
                "profile_id": "999",
                "username": "bob",
                "formatted_username": "Bob",
            }
        )
        assert cache.get_cached_profile("bob", ttl_minutes=30)["profile_id"] == "999"
        assert cache.get_cached_profile("bob", ttl_minutes=-1) is None
    finally:
        cache.close()
