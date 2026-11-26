from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import AppSettings


def _make_secure_app(tmp_path: Path, **overrides) -> tuple:
    kwargs = {
        "mode": "web",
        "data_dir": tmp_path,
        "secret_key": "strong-test-secret-key-for-security-tests",
        "access_code": "shared-pass",
        "enforce_https": True,
        "allowed_hosts": "ll.n890gf.com",
        "auth_rate_limit_max": 3,
        "auth_rate_limit_window_seconds": 300,
        "max_request_body_bytes": 1024,
        "disable_background_sync": True,
        "disable_update_check": True,
    }
    kwargs.update(overrides)
    settings = AppSettings(**kwargs)
    return create_app(settings), settings


def test_security_headers_hsts_csp_and_no_store(tmp_path: Path) -> None:
    app, _ = _make_secure_app(tmp_path)
    with TestClient(app) as client:
        r_http = client.get("/api/health", headers={"Host": "ll.n890gf.com"})
        assert r_http.status_code == 200
        assert r_http.headers["x-content-type-options"] == "nosniff"
        assert r_http.headers["x-frame-options"] == "DENY"
        assert r_http.headers["referrer-policy"] == "no-referrer"
        assert "camera=()" in r_http.headers["permissions-policy"]
        csp = r_http.headers["content-security-policy"]
        assert "script-src 'self'" in csp
        assert "'unsafe-inline'" not in csp.split("style-src")[0]
        assert "strict-transport-security" not in r_http.headers

        r_https = client.get(
            "/api/auth/me",
            headers={"Host": "ll.n890gf.com", "X-Forwarded-Proto": "https"},
        )
        assert "strict-transport-security" in r_https.headers
        assert "upgrade-insecure-requests" in r_https.headers["content-security-policy"]
        assert r_https.headers["cache-control"] == "no-store"


def test_openapi_disabled_in_web_mode_by_default(tmp_path: Path) -> None:
    app, _ = _make_secure_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/docs", headers={"Host": "ll.n890gf.com"}).status_code == 404
        assert client.get("/openapi.json", headers={"Host": "ll.n890gf.com"}).status_code == 404


def test_csrf_origin_and_sec_fetch_site_protection(tmp_path: Path) -> None:
    app, _ = _make_secure_app(tmp_path, access_code="", enforce_https=False)
    payload = {"submitted_answer": "a", "correct_answer": "b"}

    with TestClient(app) as client:
        r_cross = client.post(
            "/api/questions/grade",
            json=payload,
            headers={"Host": "ll.n890gf.com", "Sec-Fetch-Site": "cross-site"},
        )
        assert r_cross.status_code == 403

        r_bad_origin = client.post(
            "/api/questions/grade",
            json=payload,
            headers={"Host": "ll.n890gf.com", "Origin": "https://evil.example"},
        )
        assert r_bad_origin.status_code == 403

        r_good_origin = client.post(
            "/api/questions/grade",
            json=payload,
            headers={
                "Host": "ll.n890gf.com",
                "X-Forwarded-Proto": "https",
                "Origin": "https://ll.n890gf.com",
                "Sec-Fetch-Site": "same-origin",
            },
        )
        assert r_good_origin.status_code == 200


def test_auth_rate_limiter_blocks_brute_force(tmp_path: Path) -> None:
    app, _ = _make_secure_app(tmp_path)
    with TestClient(app) as client:
        headers = {"Host": "ll.n890gf.com", "X-Forwarded-Proto": "https"}
        for _ in range(3):
            resp = client.post("/api/auth/gate", json={"code": "wrong"}, headers=headers)
            assert resp.status_code == 403

        blocked = client.post("/api/auth/gate", json={"code": "shared-pass"}, headers=headers)
        assert blocked.status_code == 429
        assert int(blocked.headers["retry-after"]) >= 1


def test_enforce_https_on_auth_endpoints(tmp_path: Path) -> None:
    app, _ = _make_secure_app(tmp_path)
    with TestClient(app) as client:
        r_http = client.post(
            "/api/auth/gate",
            json={"code": "shared-pass"},
            headers={"Host": "ll.n890gf.com"},
        )
        assert r_http.status_code == 400

        r_https = client.post(
            "/api/auth/gate",
            json={"code": "shared-pass"},
            headers={"Host": "ll.n890gf.com", "X-Forwarded-Proto": "https"},
        )
        assert r_https.status_code == 200
        set_cookie = r_https.headers.get("set-cookie", "").lower()
        assert "httponly" in set_cookie
        assert "secure" in set_cookie


def test_trusted_host_rejects_unrecognized_host(tmp_path: Path) -> None:
    app, _ = _make_secure_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
        assert client.get("/api/health", headers={"Host": "ll.n890gf.com"}).status_code == 200
        assert client.get("/api/health", headers={"Host": "127.0.0.1:8000"}).status_code == 200


def test_placeholder_secret_key_rejected(tmp_path: Path) -> None:
    cfg = AppSettings(
        mode="web",
        data_dir=tmp_path,
        secret_key="replace-with-a-strong-random-secret-key",
    )
    with pytest.raises(ValueError, match="placeholder"):
        cfg.get_secret_key()


def test_oversized_body_rejected(tmp_path: Path) -> None:
    app, _ = _make_secure_app(tmp_path, access_code="", enforce_https=False)
    with TestClient(app) as client:
        resp = client.post(
            "/api/questions/grade",
            content=b"x" * 2048,
            headers={
                "Host": "ll.n890gf.com",
                "Content-Type": "application/json",
                "Content-Length": "2048",
            },
        )
        assert resp.status_code == 413
