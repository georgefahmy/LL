from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from pathlib import Path

from bs4 import BeautifulSoup
from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel

from .constants import BASE_URL, LOGIN_URL
from .http_client import LLAuthFailedError, LLHttpClient, TokenBucketRateLimiter

logger = logging.getLogger(__name__)

KEYCHAIN_SERVICE = "LearnedLeaguePracticeTool"
KEYCHAIN_ACCOUNT = "ll_session"


class LLSessionData(BaseModel):
    """Serializable authenticated LearnedLeague session payload."""

    username: str
    formatted_username: str
    profile_id: str
    cookies: dict[str, str]


def _derive_fernet_key(secret_key: str) -> bytes:
    raw = secret_key.encode("utf-8")
    try:
        decoded = base64.urlsafe_b64decode(raw)
        if len(decoded) == 32:
            return raw
    except Exception:
        pass
    digest = hashlib.sha256(raw).digest()
    return base64.urlsafe_b64encode(digest)


class SessionCookieCodec:
    """Encrypts/decrypts LLSessionData into stateless Fernet tokens."""

    def __init__(self, secret_key: str, ttl_seconds: int = 7 * 86400) -> None:
        self._fernet = Fernet(_derive_fernet_key(secret_key))
        self._ttl = ttl_seconds

    def encode(self, session: LLSessionData) -> str:
        payload = session.model_dump_json().encode("utf-8")
        return self._fernet.encrypt(payload).decode("ascii")

    def decode(self, token: str) -> LLSessionData | None:
        if not token:
            return None
        try:
            raw_token = token.encode("ascii")
            # Reject non-canonical base64 or trailing bytes after padding
            if base64.urlsafe_b64encode(base64.urlsafe_b64decode(raw_token)) != raw_token:
                return None
            plaintext = self._fernet.decrypt(raw_token, ttl=self._ttl)
            return LLSessionData.model_validate_json(plaintext)
        except (InvalidToken, ValueError, Exception):
            return None


class AccessGateCodec:
    """Signs/verifies optional shared access-code cookies."""

    def __init__(self, secret_key: str, access_code: str) -> None:
        self._secret = secret_key.encode("utf-8")
        self._access_code = access_code

    def verify_code(self, candidate: str) -> bool:
        if not self._access_code:
            return True
        return hmac.compare_digest(candidate.encode("utf-8"), self._access_code.encode("utf-8"))

    def issue_token(self) -> str:
        digest = hmac.new(
            self._secret, self._access_code.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return digest

    def verify_token(self, token: str) -> bool:
        if not self._access_code:
            return True
        if not token:
            return False
        expected = self.issue_token()
        return hmac.compare_digest(token, expected)


def _extract_verified_session(
    home_html: str,
    cookies: dict[str, str],
    fallback_username: str = "",
) -> LLSessionData:
    soup = BeautifulSoup(home_html, "html.parser")
    flag_link = soup.find("a", {"class": "flag"})
    if not flag_link or not flag_link.get("href"):
        raise LLAuthFailedError(
            "LearnedLeague authentication failed. Check your username, password, or session cookie."
        )

    href = str(flag_link.get("href"))
    profile_id = href.split("?")[-1].strip()
    if not profile_id.isdigit():
        raise LLAuthFailedError("Could not determine LearnedLeague profile ID from session.")

    formatted_username = ""
    if flag_link.img and flag_link.img.get("title"):
        formatted_username = str(flag_link.img.get("title")).strip()
    if not formatted_username:
        formatted_username = flag_link.get_text(strip=True) or fallback_username

    username = (fallback_username or formatted_username).strip().lower()
    if not formatted_username:
        formatted_username = username

    if not cookies:
        raise LLAuthFailedError("LearnedLeague did not issue valid session cookies.")

    return LLSessionData(
        username=username,
        formatted_username=formatted_username,
        profile_id=profile_id,
        cookies=cookies,
    )


def _extract_hidden_login_fields(login_html: str) -> dict[str, str]:
    soup = BeautifulSoup(login_html, "html.parser")
    hidden: dict[str, str] = {}
    form = soup.find("form", {"action": lambda a: bool(a and "login" in str(a))})
    scope = form if form is not None else soup
    for inp in scope.find_all("input", {"type": "hidden"}):
        name = inp.get("name")
        if name:
            hidden[str(name)] = str(inp.get("value") or "")
    return hidden


def login_with_credentials(
    username: str,
    password: str,
    *,
    rate_limiter: TokenBucketRateLimiter | None = None,
    transport=None,
) -> LLSessionData:
    """Authenticate against LearnedLeague via phpBB form POST; never stores password."""
    clean_user = username.strip()
    if not clean_user or not password:
        raise LLAuthFailedError("Username and password are required.")

    with LLHttpClient(rate_limiter=rate_limiter, transport=transport) as client:
        login_page_html = client.get_text(LOGIN_URL)
        hidden_fields = _extract_hidden_login_fields(login_page_html)
        payload: dict[str, str] = {
            **hidden_fields,
            "login": "Login",
            "username": clean_user,
            "password": password,
        }
        client.post_form(
            LOGIN_URL,
            data=payload,
            extra_headers={"Referer": LOGIN_URL, "Origin": BASE_URL},
        )
        home_html = client.get_text(BASE_URL)
        session = _extract_verified_session(
            home_html,
            client.cookies,
            fallback_username=clean_user,
        )
        # If homepage flag didn't include formatted name, fetch profile header cleanly
        if session.formatted_username.lower() == session.username and session.profile_id:
            try:
                profile_html = client.get_text(
                    f"{BASE_URL}/profiles.php?{session.profile_id}&1",
                    require_auth=True,
                )
                prof_soup = BeautifulSoup(profile_html, "html.parser")
                name_el = prof_soup.find("h1", {"class": "namecss"})
                if name_el and name_el.get_text(strip=True):
                    session.formatted_username = name_el.get_text(strip=True)
                    session.username = session.formatted_username.lower()
            except Exception:
                pass
        return session


def parse_cookie_header(raw_cookie: str) -> dict[str, str]:
    """Parse a browser Cookie header or semicolon-delimited key=value pairs."""
    cleaned = raw_cookie.strip()
    if cleaned.lower().startswith("cookie:"):
        cleaned = cleaned[7:].strip()
    cookies: dict[str, str] = {}
    for part in cleaned.split(";"):
        segment = part.strip()
        if not segment or "=" not in segment:
            continue
        k, v = segment.split("=", 1)
        key = k.strip()
        val = v.strip()
        if key and val:
            cookies[key] = val
    return cookies


def login_with_cookie_header(
    raw_cookie: str,
    *,
    rate_limiter: TokenBucketRateLimiter | None = None,
    transport=None,
) -> LLSessionData:
    """Verify a pasted LearnedLeague browser Cookie header against learnedleague.com."""
    cookies = parse_cookie_header(raw_cookie)
    if not cookies:
        raise LLAuthFailedError("No valid key=value cookies found in input.")

    with LLHttpClient(
        cookies=cookies,
        rate_limiter=rate_limiter,
        transport=transport,
    ) as client:
        home_html = client.get_text(BASE_URL)
        merged_cookies = {**cookies, **client.cookies}
        session = _extract_verified_session(home_html, merged_cookies)
        try:
            profile_html = client.get_text(
                f"{BASE_URL}/profiles.php?{session.profile_id}&1",
                require_auth=True,
            )
            prof_soup = BeautifulSoup(profile_html, "html.parser")
            name_el = prof_soup.find("h1", {"class": "namecss"})
            if name_el and name_el.get_text(strip=True):
                session.formatted_username = name_el.get_text(strip=True)
                session.username = session.formatted_username.lower()
        except Exception:
            pass
        return session


class DesktopKeychainStore:
    """Safe wrapper around OS Keychain via keyring (desktop mode only)."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled

    def is_available(self) -> bool:
        if not self._enabled:
            return False
        try:
            import keyring

            backend = keyring.get_keyring()
            return backend is not None and "fail" not in type(backend).__name__.lower()
        except Exception:
            return False

    def save_session(self, session: LLSessionData) -> bool:
        if not self.is_available():
            return False
        try:
            import keyring

            keyring.set_password(
                KEYCHAIN_SERVICE,
                KEYCHAIN_ACCOUNT,
                session.model_dump_json(),
            )
            return True
        except Exception as exc:
            logger.warning("Failed to save session to OS Keychain: %s", exc)
            return False

    def load_session(self) -> LLSessionData | None:
        if not self.is_available():
            return None
        try:
            import keyring

            raw = keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
            if not raw:
                return None
            return LLSessionData.model_validate_json(raw)
        except Exception as exc:
            logger.warning("Failed to load session from OS Keychain: %s", exc)
            return None

    def clear_session(self) -> None:
        if not self.is_available():
            return
        try:
            import keyring

            keyring.delete_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
        except Exception:
            pass

    @staticmethod
    def legacy_login_path(data_dir: Path) -> Path:
        return data_dir / "login_info.json"

    @classmethod
    def has_legacy_login_file(cls, data_dir: Path) -> bool:
        path = cls.legacy_login_path(data_dir)
        if not path.is_file():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return bool(isinstance(data, dict) and ("password" in data or "username" in data))
        except Exception:
            return True

    @classmethod
    def delete_legacy_login_file(cls, data_dir: Path) -> bool:
        path = cls.legacy_login_path(data_dir)
        if path.is_file():
            path.unlink()
            return True
        return False
