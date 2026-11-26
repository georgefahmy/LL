from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import AppSettings

FIXTURES = Path(__file__).parent / "fixtures"


def _make_app(tmp_path: Path, *, access_code: str = ""):
    settings = AppSettings(
        mode="web",
        data_dir=tmp_path,
        secret_key="test-secret-key",
        access_code=access_code,
        cookie_secure=False,
        disable_background_sync=True,
        disable_update_check=True,
    )
    return create_app(settings)


def test_extension_endpoints_work_without_ll_session(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    latest_html = (FIXTURES / "profile_latest.html").read_text(encoding="utf-8")
    qhist_html = (FIXTURES / "profile_qhistory.html").read_text(encoding="utf-8")
    stats_html = (FIXTURES / "profile_stats.html").read_text(encoding="utf-8")
    past_html = (FIXTURES / "profile_past_seasons.html").read_text(encoding="utf-8")
    today_html = (FIXTURES / "match_day_today.html").read_text(encoding="utf-8")
    allrundles_html = (FIXTURES / "allrundles.html").read_text(encoding="utf-8")
    lgwide_csv = (FIXTURES / "lgwide.csv").read_text(encoding="utf-8")

    with TestClient(app) as client:
        # 1. Parse full player profile
        r_prof = client.post(
            "/api/extension/parse-profile",
            json={
                "latest_html": latest_html,
                "qhist_html": qhist_html,
                "stats_html": stats_html,
                "past_html": past_html,
            },
        )
        assert r_prof.status_code == 200
        prof = r_prof.json()
        assert prof["profile_id"]
        assert prof["formatted_username"]
        assert len(prof["category_metrics"]) > 0
        assert len(prof["question_history"]) > 0

        # 2. Parse today's questions (hidden + revealed)
        r_today = client.post(
            "/api/extension/parse-todays-questions",
            json={"html": today_html, "season": 109, "day": 14, "show_answers": True},
        )
        assert r_today.status_code == 200
        today = r_today.json()
        assert today["status"] == "ok"
        assert len(today["questions"]) == 6
        assert today["questions"][0]["submitted_answer"] == "MY ANS 1"

        # 3. Parse season & day
        r_sd = client.post(
            "/api/extension/parse-season-day",
            json={"html": allrundles_html},
        )
        assert r_sd.status_code == 200
        assert r_sd.json() == {"latest_season": 109, "current_day": 14}

        # 4. Compute HUN
        r_hun = client.post(
            "/api/extension/hun",
            json={
                "player1": "Alice",
                "player2": "Bob",
                "qhist_1": {
                    "S109D01Q1": {"correct": True},
                    "S109D01Q2": {"correct": False},
                },
                "qhist_2": {
                    "S109D01Q1": {"correct": True},
                    "S109D01Q2": {"correct": True},
                },
            },
        )
        assert r_hun.status_code == 200
        assert r_hun.json()["score"] == 0.5
        assert r_hun.json()["shared_questions"] == 2

        # 5. Similarity radar
        r_sim = client.post(
            "/api/extension/similarity",
            json={
                "player1": "Alice",
                "player2": "Bob",
                "metrics_1": {"SCIENCE": {"percent": 0.8}},
                "metrics_2": {"SCIENCE": {"percent": 0.4}},
            },
        )
        assert r_sim.status_code == 200
        sci = next(s for s in r_sim.json()["series"] if s["category"] == "SCIENCE")
        assert sci["player1_pct"] == 80.0
        assert sci["player2_pct"] == 40.0

        # 6. Analyze luck from CSV
        r_luck = client.post(
            "/api/extension/analyze-luck",
            json={
                "csv_text": lgwide_csv,
                "season": 109,
                "matchday": 25,
                "usernames": ["AlicePlayer", "BobOpp"],
                "use_sos": True,
            },
        )
        assert r_luck.status_code == 200
        luck = r_luck.json()
        assert luck["season"] == 109
        assert luck["matched_usernames"] == ["AlicePlayer", "BobOpp"]
        assert len(luck["rows"]) == 2


def test_extension_endpoints_respect_access_gate(tmp_path: Path) -> None:
    app = _make_app(tmp_path, access_code="gate-pass")
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/extension/parse-season-day",
                json={"html": "<h1>LL 110</h1><h3>Day 1</h3>"},
            ).status_code
            == 403
        )


def test_extension_sync_plan_and_ingest_matchday(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from backend.api.routes import extension as ext_routes

    app = _make_app(tmp_path)
    allrundles_html = (FIXTURES / "allrundles.html").read_text(encoding="utf-8")
    matchday_html = (FIXTURES / "match_day_past.html").read_text(encoding="utf-8")

    monkeypatch.setattr(ext_routes, "MIN_AVAILABLE_SEASON", 109)
    # Seed S109 D1..D9 so D10..D14 (5 days) are missing
    app.state.ll.cache.upsert_questions(
        [
            {
                "qcode": f"S109D{d:02d}Q{q}",
                "season": 109,
                "day": d,
                "q_num": q,
                "question": f"Q{q}",
                "answer": f"A{q}",
                "category": "SCIENCE",
                "percent": 50,
            }
            for d in range(1, 10)
            for q in range(1, 7)
        ]
    )

    with TestClient(app) as client:
        # Simulate an initial background sync 403 error prior to extension sync
        app.state.ll.sync_worker._update_status(
            phase="error",
            last_error="Request blocked by upstream security check (HTTP 403).",
        )
        initial_meta = client.get("/api/meta").json()
        assert initial_meta["sync_status"]["phase"] == "error"
        assert "HTTP 403" in initial_meta["sync_status"]["last_error"]

        r_plan = client.post(
            "/api/extension/sync-plan",
            json={"allrundles_html": allrundles_html, "max_days": 2},
        )
        assert r_plan.status_code == 200
        plan = r_plan.json()
        assert plan["latest_season"] == 109
        assert plan["current_day"] == 14
        assert len(plan["batch"]) == 2
        assert plan["remaining_missing_days"] == 3
        assert app.state.ll.cache.get_meta("latest_season") == "109"
        assert app.state.ll.cache.get_meta("current_day") == "14"

        after_plan_meta = client.get("/api/meta").json()
        assert after_plan_meta["sync_status"]["phase"] == "idle"
        assert after_plan_meta["sync_status"]["last_error"] is None

        r_ingest = client.post(
            "/api/extension/ingest-matchday",
            json={"season": 109, "day": 14, "html": matchday_html},
        )
        assert r_ingest.status_code == 200
        ing = r_ingest.json()
        assert ing == {"season": 109, "day": 14, "imported": 6}
        assert app.state.ll.cache.count_questions() == 9 * 6 + 6
        assert app.state.ll.cache.get_meta("last_synced_at") is not None

        final_meta = client.get("/api/meta").json()
        assert final_meta["sync_status"]["phase"] == "idle"
        assert final_meta["sync_status"]["last_error"] is None
        assert final_meta["sync_status"]["last_synced_at"] is not None
