from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import AppSettings
from backend.core.auth import LLSessionData


def _make_test_app(
    tmp_path: Path,
    *,
    mode: str = "web",
    access_code: str = "",
):
    settings = AppSettings(
        mode=mode,
        data_dir=tmp_path,
        secret_key="test-secret-key",
        access_code=access_code,
        cookie_secure=False,
        disable_background_sync=True,
        disable_update_check=True,
    )
    app = create_app(settings)
    app.state.ll.cache.upsert_questions(
        [
            {
                "qcode": f"S100D01Q{i}",
                "season": 100,
                "day": 1,
                "q_num": i,
                "question": f"Sample question {i}",
                "answer": f"ANSWER {i}",
                "category": "SCIENCE",
                "percent": 10 * i,
                "defense": "1.5",
                "date": "Feb 12, 2024",
                "url": f"https://www.learnedleague.com/question.php?100&1&{i}",
                "clickable_link": "",
            }
            for i in range(1, 8)
        ]
    )
    return app


def test_public_endpoints_and_auth_guards(tmp_path: Path) -> None:
    app = _make_test_app(tmp_path)
    with TestClient(app) as client:
        r_health = client.get("/api/health")
        assert r_health.status_code == 200
        assert r_health.json()["status"] == "ok"

        r_qs = client.get("/api/questions?category=SCIENCE")
        assert r_qs.status_code == 200
        assert r_qs.json()["total"] == 7

        r_grade = client.post(
            "/api/questions/grade",
            json={"submitted_answer": "answer 1", "correct_answer": "ANSWER 1"},
        )
        assert r_grade.status_code == 200
        assert r_grade.json()["correct"] is True

        r_mock = client.post("/api/mock-day/generate", json={"seed": 7, "threshold": 0})
        assert r_mock.status_code == 200
        assert len(r_mock.json()["questions"]) == 6

        # Logged-in routes require auth
        assert client.get("/api/players/me").status_code == 401
        assert client.post("/api/luck/analyze", json={"season": 100}).status_code == 401
        assert (
            client.post(
                "/api/defense/recommend",
                json={
                    "opponent": "Bob",
                    "categories": [
                        "SCIENCE",
                        "ART",
                        "FILM",
                        "MATH",
                        "GEOGRAPHY",
                        "WORLD HIST",
                    ],
                },
            ).status_code
            == 401
        )
        assert (
            client.get("/api/defense/todays-questions?season=100&day=1").status_code == 401
        )

        # Web mode disables server-side personal storage
        assert client.get("/api/local-store/favorites").status_code == 400


def test_access_gate_enforcement(tmp_path: Path) -> None:
    app = _make_test_app(tmp_path, access_code="secret-pass")
    with TestClient(app) as client:
        assert client.get("/api/questions").status_code == 403
        assert (
            client.post("/api/auth/gate", json={"code": "wrong"}).status_code == 403
        )
        assert (
            client.post("/api/auth/gate", json={"code": "secret-pass"}).status_code
            == 200
        )
        assert client.get("/api/questions").status_code == 200


def test_image_proxy_ssrf_protection(tmp_path: Path) -> None:
    app = _make_test_app(tmp_path)
    with TestClient(app) as client:
        for bad_url in [
            "http://169.254.169.254/latest/meta-data/",
            "http://127.0.0.1:8000/api/health",
            "https://evil.example.com/payload.png",
            "http://www.learnedleague.com/images/a.png",
        ]:
            resp = client.get("/api/proxy/image", params={"url": bad_url})
            assert resp.status_code == 400


def test_session_cookie_isolation_between_clients(tmp_path: Path) -> None:
    app = _make_test_app(tmp_path)
    codec = app.state.ll.session_codec
    tok_a = codec.encode(
        LLSessionData(
            username="alice",
            formatted_username="Alice",
            profile_id="101",
            cookies={"sid": "a"},
        )
    )
    tok_b = codec.encode(
        LLSessionData(
            username="bob",
            formatted_username="Bob",
            profile_id="202",
            cookies={"sid": "b"},
        )
    )

    with TestClient(app) as client_a, TestClient(app) as client_b:
        client_a.cookies.set("ll_session", tok_a)
        client_b.cookies.set("ll_session", tok_b)
        me_a = client_a.get("/api/auth/me").json()
        me_b = client_b.get("/api/auth/me").json()
        assert me_a["username"] == "alice"
        assert me_a["profile_id"] == "101"
        assert me_b["username"] == "bob"
        assert me_b["profile_id"] == "202"


def test_defense_recommend_category_only_and_irt_modes(tmp_path: Path) -> None:
    app = _make_test_app(tmp_path)
    cats = ["SCIENCE", "ART", "FILM", "MATH", "GEOGRAPHY", "WORLD HIST"]

    app.state.ll.cache.set_cached_profile(
        {
            "profile_id": "101",
            "username": "alice",
            "formatted_username": "Alice",
            "link": "https://www.learnedleague.com/profiles.php?101",
            "opponents": {"Bob": "202"},
            "category_metrics": {
                "SCIENCE": {"correct": 90, "total": 100, "percent": 0.90},
                "ART": {"correct": 40, "total": 100, "percent": 0.40},
                "FILM": {"correct": 50, "total": 100, "percent": 0.50},
                "MATH": {"correct": 50, "total": 100, "percent": 0.50},
                "GEOGRAPHY": {"correct": 50, "total": 100, "percent": 0.50},
                "WORLD HIST": {"correct": 50, "total": 100, "percent": 0.50},
            },
            "question_history": {},
            "stats": {"total": {}, "current_season": {}},
            "past_seasons": {},
        }
    )
    app.state.ll.cache.set_cached_profile(
        {
            "profile_id": "202",
            "username": "bob",
            "formatted_username": "Bob",
            "link": "https://www.learnedleague.com/profiles.php?202",
            "opponents": {},
            "category_metrics": {
                "SCIENCE": {"correct": 75, "total": 100, "percent": 0.75},
                "ART": {"correct": 25, "total": 100, "percent": 0.25},
                "FILM": {"correct": 50, "total": 100, "percent": 0.50},
                "MATH": {"correct": 80, "total": 100, "percent": 0.80},
                "GEOGRAPHY": {"correct": 40, "total": 100, "percent": 0.40},
                "WORLD HIST": {"correct": 60, "total": 100, "percent": 0.60},
            },
            "question_history": {},
            "stats": {"total": {}, "current_season": {}},
            "past_seasons": {},
        }
    )

    tok_a = app.state.ll.session_codec.encode(
        LLSessionData(
            username="alice",
            formatted_username="Alice",
            profile_id="101",
            cookies={"sid": "a"},
        )
    )

    with TestClient(app) as client:
        client.cookies.set("ll_session", tok_a)

        # 1. Category-only fallback when difficulties omitted
        resp_cat = client.post(
            "/api/defense/recommend",
            json={"opponent": "Bob", "opponent_profile_id": "202", "categories": cats},
        )
        assert resp_cat.status_code == 200
        data_cat = resp_cat.json()
        assert data_cat["mode"] == "category_only"
        assert data_cat["player"] is None
        assert "expected_opponent_points" in data_cat
        pts_cat = {r["category"]: r["recommended_points"] for r in data_cat["recommendations"]}
        assert pts_cat["ART"] == 3
        assert pts_cat["MATH"] == 0
        assert all(r["estimated_ground_truth_pct"] is None for r in data_cat["recommendations"])

        # 2. IRT mode when difficulties are supplied
        resp_irt = client.post(
            "/api/defense/recommend",
            json={
                "opponent": "Bob",
                "opponent_profile_id": "202",
                "categories": cats,
                "difficulties": [5, 1, 3, 3, 3, 3],
            },
        )
        assert resp_irt.status_code == 200
        data_irt = resp_irt.json()
        assert data_irt["mode"] == "irt"
        assert data_irt["player"] == "Alice"
        assert isinstance(data_irt["expected_opponent_points"], float)
        by_cat = {r["category"]: r for r in data_irt["recommendations"]}
        assert by_cat["SCIENCE"]["recommended_points"] == 3
        assert by_cat["SCIENCE"]["estimated_ground_truth_pct"] is not None
        assert by_cat["ART"]["recommended_points"] == 0
        assert by_cat["ART"]["estimated_ground_truth_pct"] is not None


def test_defense_screenshot_and_manual_endpoints_without_ll_login(tmp_path: Path) -> None:
    app = _make_test_app(tmp_path)
    cats = ["SCIENCE", "ART", "FILM", "MATH", "GEOGRAPHY", "WORLD HIST"]

    with TestClient(app) as client:
        # 1. Parse stats text without LL login
        r_parse = client.post(
            "/api/defense/parse-stats-screenshot",
            json={
                "raw_text": (
                    "SCIENCE 15-20 .750\n"
                    "ART 5-20 .250\n"
                    "FILM 10-20 .500\n"
                    "MATH 16-20 .800\n"
                    "GEOGRAPHY 8-20 .400\n"
                    "WORLD HIST 12-20 .600\n"
                )
            },
        )
        assert r_parse.status_code == 200
        parsed = r_parse.json()
        assert parsed["matched_count"] == 6
        assert parsed["category_metrics"]["ART"]["correct"] == 5

        # Invalid base64 -> 400
        r_bad = client.post(
            "/api/defense/parse-stats-screenshot",
            json={"image_base64": "not-valid-base64!!!"},
        )
        assert r_bad.status_code == 400

        # 2. Manual defense category-only mode without LL login
        opp_metrics = parsed["category_metrics"]
        r_cat = client.post(
            "/api/defense/recommend-manual",
            json={"categories": cats, "opponent_metrics": opp_metrics},
        )
        assert r_cat.status_code == 200
        d_cat = r_cat.json()
        assert d_cat["mode"] == "category_only"
        cat_pts = {r["category"]: r["recommended_points"] for r in d_cat["recommendations"]}
        assert cat_pts["ART"] == 3

        # 3. Manual defense IRT mode without LL login
        player_metrics = {
            "SCIENCE": {"correct": 18, "total": 20, "percent": 0.90},
            "ART": {"correct": 8, "total": 20, "percent": 0.40},
            "FILM": {"correct": 10, "total": 20, "percent": 0.50},
            "MATH": {"correct": 10, "total": 20, "percent": 0.50},
            "GEOGRAPHY": {"correct": 10, "total": 20, "percent": 0.50},
            "WORLD HIST": {"correct": 10, "total": 20, "percent": 0.50},
        }
        r_irt = client.post(
            "/api/defense/recommend-manual",
            json={
                "categories": cats,
                "opponent_metrics": opp_metrics,
                "player_metrics": player_metrics,
                "difficulties": [5, 1, 3, 3, 3, 3],
            },
        )
        assert r_irt.status_code == 200
        d_irt = r_irt.json()
        assert d_irt["mode"] == "irt"
        assert isinstance(d_irt["expected_opponent_points"], float)
        by_cat = {r["category"]: r for r in d_irt["recommendations"]}
        assert by_cat["SCIENCE"]["recommended_points"] == 3
        assert by_cat["SCIENCE"]["estimated_ground_truth_pct"] is not None
        assert by_cat["ART"]["recommended_points"] == 0
