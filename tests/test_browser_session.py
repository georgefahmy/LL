from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import AppSettings
from backend.core.browser_session import (
    INTERACTIVE_BROWSER_SENTINEL,
    InteractiveBrowserManager,
    is_valid_ll_https_url,
    validate_browser_fetch_response,
)
from backend.core.http_client import (
    LLAuthExpiredError,
    LLInvalidUrlError,
    LLNotFoundError,
    LLRateLimitError,
)


def _make_test_app(tmp_path: Path, *, mode: str = "web"):
    settings = AppSettings(
        mode=mode,
        data_dir=tmp_path,
        secret_key="test-secret-key",
        cookie_secure=False,
        disable_background_sync=True,
        disable_update_check=True,
    )
    return create_app(settings)


def test_browser_session_url_ssrf_and_response_validation() -> None:
    assert is_valid_ll_https_url("https://www.learnedleague.com/profiles.php?123&1")
    assert is_valid_ll_https_url("https://learnedleague.com/match.php?109&1")
    assert not is_valid_ll_https_url("http://www.learnedleague.com/profiles.php?123")
    assert not is_valid_ll_https_url("https://evil.example.com/profiles.php?123")
    assert not is_valid_ll_https_url("http://127.0.0.1:8000/api/health")

    mgr = InteractiveBrowserManager()
    with pytest.raises(LLInvalidUrlError):
        mgr.fetch_text("https://evil.example.com/secret")

    # 200 OK
    assert (
        validate_browser_fetch_response(
            "https://www.learnedleague.com/profiles.php?1",
            ok=True,
            status=200,
            final_url="https://www.learnedleague.com/profiles.php?1",
            body="<html><body>OK</body></html>",
            require_auth=True,
        )
        == "<html><body>OK</body></html>"
    )

    # 403 WAF -> LLRateLimitError
    with pytest.raises(LLRateLimitError):
        validate_browser_fetch_response(
            "https://www.learnedleague.com/profiles.php?1",
            ok=True,
            status=403,
            final_url="https://www.learnedleague.com/profiles.php?1",
            body="Just a moment... cf-browser-verification",
            require_auth=True,
        )

    # Login redirect -> LLAuthExpiredError
    with pytest.raises(LLAuthExpiredError):
        validate_browser_fetch_response(
            "https://www.learnedleague.com/profiles.php?1",
            ok=True,
            status=200,
            final_url="https://www.learnedleague.com/ucp.php?mode=login",
            body="<html>login</html>",
            require_auth=True,
        )

    # 404 -> LLNotFoundError
    with pytest.raises(LLNotFoundError):
        validate_browser_fetch_response(
            "https://www.learnedleague.com/profiles.php?999999",
            ok=True,
            status=404,
            final_url="https://www.learnedleague.com/profiles.php?999999",
            body="Not found",
            require_auth=False,
        )


def test_browser_backed_client_against_mock_bridge_server() -> None:
    token = "bridge-secret"

    class _MockBridge(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            if self.headers.get("X-Bridge-Token") != token:
                self.send_response(HTTPStatus.UNAUTHORIZED)
                self.end_headers()
                return
            if self.path == "/status":
                body = json.dumps(
                    {
                        "running": True,
                        "authenticated": True,
                        "username": "alice",
                        "formatted_username": "Alice",
                        "profile_id": "101",
                    }
                ).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def do_POST(self) -> None:
            if self.headers.get("X-Bridge-Token") != token:
                self.send_response(HTTPStatus.UNAUTHORIZED)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length") or "0")
            req = json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path == "/fetch":
                url = req["url"]
                if "waf" in url:
                    resp = {
                        "ok": True,
                        "status": 403,
                        "final_url": url,
                        "body": "Just a moment...",
                    }
                elif "expired" in url:
                    resp = {
                        "ok": True,
                        "status": 200,
                        "final_url": "https://www.learnedleague.com/ucp.php?mode=login",
                        "body": "login",
                    }
                else:
                    resp = {
                        "ok": True,
                        "status": 200,
                        "final_url": url,
                        "body": "<html>Profile HTML</html>",
                    }
                raw = json.dumps(resp).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

    class _AliveProc:
        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockBridge)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    try:
        mgr = InteractiveBrowserManager()
        mgr._proc = _AliveProc()  # type: ignore[assignment]
        mgr._port = port
        mgr._token = token

        assert mgr.is_authenticated() is True
        with mgr.as_client() as client:
            assert (
                client.get_text(
                    "https://www.learnedleague.com/profiles.php?101&1",
                    require_auth=True,
                )
                == "<html>Profile HTML</html>"
            )
            with pytest.raises(LLRateLimitError):
                client.get_text("https://www.learnedleague.com/waf", require_auth=True)
            with pytest.raises(LLAuthExpiredError):
                client.get_text("https://www.learnedleague.com/expired", require_auth=True)
    finally:
        server.shutdown()
        server.server_close()


def test_interactive_auth_endpoints_issue_session_and_route_get_ll_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    web_app = _make_test_app(tmp_path / "web", mode="web")
    with TestClient(web_app) as web_client:
        assert web_client.post("/api/auth/interactive/start").status_code == 400
        assert web_client.get("/api/auth/interactive/status").status_code == 400

    app = _make_test_app(tmp_path / "desktop", mode="desktop")
    mgr = app.state.ll.browser_manager

    state_box = {"auth": False}

    monkeypatch.setattr(mgr, "is_supported", lambda: True)
    monkeypatch.setattr(
        mgr,
        "start_or_show",
        lambda: {"status": "waiting_for_user", "authenticated": False},
    )
    monkeypatch.setattr(
        mgr,
        "get_status",
        lambda: (
            {
                "running": True,
                "authenticated": True,
                "username": "alice",
                "formatted_username": "Alice",
                "profile_id": "101",
            }
            if state_box["auth"]
            else {"running": True, "authenticated": False}
        ),
    )
    monkeypatch.setattr(mgr, "is_authenticated", lambda: state_box["auth"])
    monkeypatch.setattr(
        mgr,
        "fetch_text",
        lambda url, require_auth=False: (
            '<html><div class="flagdiv"><a href="/profiles.php?202"></a></div>'
            '<h1 class="namecss">Bob</h1>'
            '<table class="this_sea"><tbody>'
            '<tr><td>SCIENCE</td><td>15-20</td></tr>'
            "</tbody></table></html>"
            if "&1" in url
            else "<html></html>"
        ),
    )

    with TestClient(app) as client:
        r_start = client.post("/api/auth/interactive/start")
        assert r_start.status_code == 200
        assert r_start.json()["status"] == "waiting_for_user"
        assert r_start.json()["authenticated"] is False

        r_wait = client.get("/api/auth/interactive/status")
        assert r_wait.status_code == 200
        assert r_wait.json()["status"] == "waiting_for_user"
        assert r_wait.json()["authenticated"] is False

        # Simulate user completing Cloudflare + login in window
        state_box["auth"] = True
        r_done = client.get("/api/auth/interactive/status")
        assert r_done.status_code == 200
        done_json = r_done.json()
        assert done_json["status"] == "authenticated"
        assert done_json["authenticated"] is True
        assert done_json["username"] == "alice"
        assert done_json["profile_id"] == "101"

        # Session cookie must contain sentinel and route get_ll_client via browser_manager
        token = client.cookies.get("ll_session")
        assert token
        decoded = app.state.ll.session_codec.decode(token.strip('"'))
        assert decoded is not None
        assert decoded.cookies == {INTERACTIVE_BROWSER_SENTINEL: "1"}

        r_prof = client.get("/api/players/Bob?profile_id=202")
        assert r_prof.status_code == 200
        prof = r_prof.json()
        assert prof["formatted_username"] == "Bob"
        assert prof["category_metrics"]["SCIENCE"]["correct"] == 15

        # If interactive browser closes/stops, get_ll_client rejects with 401
        state_box["auth"] = False
        r_expired = client.get("/api/players/Bob2?profile_id=303")
        assert r_expired.status_code == 401


def test_luck_latest_season_parses_live_season_and_persists_meta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _make_test_app(tmp_path)
    mgr = app.state.ll.browser_manager

    monkeypatch.setattr(mgr, "is_authenticated", lambda: True)
    monkeypatch.setattr(
        mgr,
        "fetch_text",
        lambda url, require_auth=False: (
            "<html><h1>LL 110</h1><h3>Match Day 14</h3></html>"
            if "allrundles.php" in url
            else "<html></html>"
        ),
    )

    from backend.core.auth import LLSessionData

    tok = app.state.ll.session_codec.encode(
        LLSessionData(
            username="alice",
            formatted_username="Alice",
            profile_id="101",
            cookies={INTERACTIVE_BROWSER_SENTINEL: "1"},
        )
    )

    with TestClient(app) as client:
        client.cookies.set("ll_session", tok)
        resp = client.get("/api/luck/latest-season")
        assert resp.status_code == 200
        assert resp.json() == {"latest_season": 110, "current_day": 14}

        meta = client.get("/api/meta")
        assert meta.status_code == 200
        assert meta.json()["latest_season"] == 110
        assert meta.json()["current_day"] == 14


def test_season_sync_worker_uses_authenticated_browser_manager(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.core.cache import CacheStore
    from backend.core.http_client import TokenBucketRateLimiter
    from backend.core.scrapers import seasons as seasons_mod

    fixtures_dir = Path(__file__).parent / "fixtures"
    allrundles_html = (fixtures_dir / "allrundles.html").read_text(encoding="utf-8")
    matchday_html = (fixtures_dir / "match_day_past.html").read_text(encoding="utf-8")

    cache = CacheStore(tmp_path / "sync.db")
    try:
        # Mark S109 D1..D13 as already synced so only S109 D14 is fetched
        existing_records = [
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
            for d in range(1, 14)
            for q in range(1, 7)
        ]
        cache.upsert_questions(existing_records)

        mgr = InteractiveBrowserManager()
        fetched_urls: list[str] = []
        monkeypatch.setattr(mgr, "is_authenticated", lambda: True)

        def fake_fetch(url: str, require_auth: bool = False) -> str:
            fetched_urls.append(url)
            if "allrundles.php" in url:
                return allrundles_html
            return matchday_html

        monkeypatch.setattr(mgr, "fetch_text", fake_fetch)
        monkeypatch.setattr(seasons_mod, "MIN_AVAILABLE_SEASON", 109)

        worker = seasons_mod.SeasonSyncWorker(
            cache,
            TokenBucketRateLimiter(1000.0),
            sync_delay_seconds=0.0,
            browser_manager=mgr,
        )
        worker.sync_once()

        status = worker.status()
        assert status["phase"] == "idle"
        assert status["last_error"] is None
        assert status["latest_season"] == 109
        assert status["current_day"] == 14
        assert status["remaining_missing_days"] == 0
        assert cache.get_meta("latest_season") == "109"
        assert cache.get_meta("current_day") == "14"
        assert cache.count_questions() == len(existing_records) + 6
        assert any("allrundles.php" in u for u in fetched_urls)
        assert any("match.php?109&14" in u for u in fetched_urls)
    finally:
        cache.close()


def test_season_sync_worker_respects_batch_cap_and_aborts_on_rate_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.core.cache import CacheStore
    from backend.core.http_client import TokenBucketRateLimiter
    from backend.core.scrapers import seasons as seasons_mod

    fixtures_dir = Path(__file__).parent / "fixtures"
    allrundles_html = (fixtures_dir / "allrundles.html").read_text(encoding="utf-8")
    matchday_html = (fixtures_dir / "match_day_past.html").read_text(encoding="utf-8")

    # 1. Batch cap: S109 D1..D9 cached -> D10..D14 missing (5 days), max_days_per_run=2
    cache = CacheStore(tmp_path / "sync_cap.db")
    try:
        cache.upsert_questions(
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

        mgr = InteractiveBrowserManager()
        fetched_urls: list[str] = []
        monkeypatch.setattr(mgr, "is_authenticated", lambda: True)

        def fake_fetch(url: str, require_auth: bool = False) -> str:
            fetched_urls.append(url)
            if "allrundles.php" in url:
                return allrundles_html
            return matchday_html

        monkeypatch.setattr(mgr, "fetch_text", fake_fetch)
        monkeypatch.setattr(seasons_mod, "MIN_AVAILABLE_SEASON", 109)

        worker = seasons_mod.SeasonSyncWorker(
            cache,
            TokenBucketRateLimiter(1000.0),
            sync_delay_seconds=0.0,
            max_days_per_run=2,
            browser_manager=mgr,
        )
        worker.sync_once()

        match_fetches = [u for u in fetched_urls if "match.php" in u]
        assert len(match_fetches) == 2
        status = worker.status()
        assert status["phase"] == "idle"
        assert status["total_missing_days"] == 2
        assert status["completed_days"] == 2
        assert status["remaining_missing_days"] == 3
    finally:
        cache.close()

    # 2. Immediate abort on LLRateLimitError
    cache2 = CacheStore(tmp_path / "sync_rl.db")
    try:
        mgr2 = InteractiveBrowserManager()
        rl_fetches: list[str] = []
        monkeypatch.setattr(mgr2, "is_authenticated", lambda: True)

        def fake_fetch_rl(url: str, require_auth: bool = False) -> str:
            rl_fetches.append(url)
            if "allrundles.php" in url:
                return allrundles_html
            raise LLRateLimitError("HTTP 429 rate limited")

        monkeypatch.setattr(mgr2, "fetch_text", fake_fetch_rl)
        monkeypatch.setattr(seasons_mod, "MIN_AVAILABLE_SEASON", 109)

        worker2 = seasons_mod.SeasonSyncWorker(
            cache2,
            TokenBucketRateLimiter(1000.0),
            sync_delay_seconds=0.0,
            max_days_per_run=10,
            browser_manager=mgr2,
        )
        worker2.sync_once()

        assert len([u for u in rl_fetches if "match.php" in u]) == 1
        st2 = worker2.status()
        assert st2["phase"] == "error"
        assert st2["last_error"] is not None and "429" in st2["last_error"]
    finally:
        cache2.close()


def test_interactive_browser_manager_in_process_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib
    import subprocess
    import sys

    from backend.core import browser_worker

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *_a, **_kw: pytest.fail("In-process mode must not spawn a subprocess"),
    )

    # Simulate Linux CI / web-only installs where pywebview is not installed
    monkeypatch.setitem(sys.modules, "webview", None)
    importlib.reload(browser_worker)

    mgr = InteractiveBrowserManager()
    mgr.enable_in_process_mode()
    assert mgr.is_supported() is False
    with pytest.raises(RuntimeError, match="pywebview"):
        mgr._in_process_bridge.start_or_show()

    bridge_state = {"running": True, "auth": False, "shutdown": False}

    class _FakeInProcessBridge:
        def start_or_show(self):
            bridge_state["running"] = True
            return {"status": "waiting_for_user", "authenticated": False}

        def get_status(self):
            if not bridge_state["running"]:
                return {"running": False, "authenticated": False}
            if bridge_state["auth"]:
                return {
                    "running": True,
                    "authenticated": True,
                    "username": "alice",
                    "formatted_username": "Alice",
                    "profile_id": "101",
                }
            return {"running": True, "authenticated": False}

        def fetch(self, url: str, *, require_auth: bool = False):
            if not bridge_state["running"]:
                raise RuntimeError("Interactive browser session is not running.")
            if "waf" in url:
                return {"ok": True, "status": 403, "final_url": url, "body": "Just a moment..."}
            if "expired" in url:
                return {
                    "ok": True,
                    "status": 200,
                    "final_url": "https://www.learnedleague.com/ucp.php?mode=login",
                    "body": "login",
                }
            return {"ok": True, "status": 200, "final_url": url, "body": "<html>OK</html>"}

        def shutdown(self):
            bridge_state["running"] = False
            bridge_state["shutdown"] = True

    mgr._in_process_bridge = _FakeInProcessBridge()
    monkeypatch.setattr(mgr, "is_supported", lambda: True)

    start_res = mgr.start_or_show()
    assert start_res == {"status": "waiting_for_user", "authenticated": False}
    assert mgr.is_authenticated() is False

    bridge_state["auth"] = True
    assert mgr.is_authenticated() is True
    assert mgr.get_status()["profile_id"] == "101"

    assert mgr.fetch_text("https://www.learnedleague.com/profiles.php?101", require_auth=True) == (
        "<html>OK</html>"
    )
    with pytest.raises(LLInvalidUrlError):
        mgr.fetch_text("https://example.com/")
    with pytest.raises(LLRateLimitError):
        mgr.fetch_text("https://www.learnedleague.com/waf", require_auth=True)
    with pytest.raises(LLAuthExpiredError):
        mgr.fetch_text("https://www.learnedleague.com/expired", require_auth=True)

    mgr.shutdown()
    assert bridge_state["shutdown"] is True
    assert mgr.is_authenticated() is False
    with pytest.raises(LLAuthExpiredError):
        mgr.fetch_text("https://www.learnedleague.com/profiles.php?101", require_auth=True)
