from __future__ import annotations

import httpx
import pytest

from backend.core.auth import (
    AccessGateCodec,
    LLSessionData,
    SessionCookieCodec,
    login_with_cookie_header,
    login_with_credentials,
    parse_cookie_header,
)
from backend.core.http_client import LLAuthFailedError


def test_fernet_session_cookie_roundtrip_and_tamper() -> None:
    codec = SessionCookieCodec("my-super-secret-key", ttl_seconds=60)
    session = LLSessionData(
        username="alice",
        formatted_username="AlicePlayer",
        profile_id="12345",
        cookies={"phpbb3_sid": "abc123"},
    )
    token = codec.encode(session)
    decoded = codec.decode(token)
    assert decoded is not None
    assert decoded.profile_id == "12345"
    assert decoded.cookies == {"phpbb3_sid": "abc123"}

    # Tampered token (either modified byte or trailing bytes) and wrong key must fail closed
    flipped = token[:15] + ("A" if token[15] != "A" else "B") + token[16:]
    assert codec.decode(flipped) is None
    assert codec.decode(token + "tamper") is None
    assert SessionCookieCodec("other-secret").decode(token) is None

    # Expired TTL must fail closed
    expired_codec = SessionCookieCodec("my-super-secret-key", ttl_seconds=-1)
    assert expired_codec.decode(token) is None


def test_parse_cookie_header() -> None:
    parsed = parse_cookie_header("Cookie: phpbb3_sid=xyz; phpbb3_u=99; empty=")
    assert parsed == {"phpbb3_sid": "xyz", "phpbb3_u": "99"}


def test_access_gate_codec() -> None:
    gate = AccessGateCodec("secret", "open-sesame")
    assert gate.verify_code("open-sesame") is True
    assert gate.verify_code("wrong") is False
    tok = gate.issue_token()
    assert gate.verify_token(tok) is True
    assert gate.verify_token("bad-token") is False


def test_login_with_credentials_success_and_failure() -> None:
    def success_handler(request: httpx.Request) -> httpx.Response:
        if "ucp.php" in str(request.url) and request.method == "GET":
            return httpx.Response(
                200,
                text=(
                    '<form action="ucp.php?mode=login">'
                    '<input type="hidden" name="sid" value="s1"></form>'
                ),
            )
        if "ucp.php" in str(request.url) and request.method == "POST":
            return httpx.Response(
                200,
                text="ok",
                headers={"Set-Cookie": "phpbb3_sid=valid_cookie; Path=/"},
            )
        if "profiles.php?12345&1" in str(request.url):
            return httpx.Response(200, text='<h1 class="namecss">AlicePlayer</h1>')
        return httpx.Response(
            200,
            text='<a class="flag" href="profiles.php?12345"><img title="AlicePlayer"/></a>',
        )

    transport = httpx.MockTransport(success_handler)
    sess = login_with_credentials("aliceplayer", "secretpw", transport=transport)
    assert sess.profile_id == "12345"
    assert sess.formatted_username == "AlicePlayer"
    assert sess.cookies["phpbb3_sid"] == "valid_cookie"

    # Bad credentials -> clean LLAuthFailedError (not AttributeError)
    fail_transport = httpx.MockTransport(
        lambda req: httpx.Response(200, text="<html><body>Invalid login</body></html>")
    )
    with pytest.raises(LLAuthFailedError):
        login_with_credentials("alice", "badpw", transport=fail_transport)


def test_login_with_cookie_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "profiles.php?777&1" in str(request.url):
            return httpx.Response(200, text='<h1 class="namecss">CookieUser</h1>')
        return httpx.Response(
            200,
            text='<a class="flag" href="profiles.php?777"><img title="CookieUser"/></a>',
        )

    sess = login_with_cookie_header(
        "phpbb3_sid=abc", transport=httpx.MockTransport(handler)
    )
    assert sess.profile_id == "777"
    assert sess.formatted_username == "CookieUser"
