from __future__ import annotations

import logging
import os
import secrets
import sys
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def resolve_bundle_path(rel_path: str) -> Path:
    """Resolve a project-relative resource path in dev, Docker, or PyInstaller builds."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate = Path(meipass) / rel_path
        if candidate.exists():
            return candidate
    return Path(__file__).resolve().parent.parent / rel_path


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables (LL_*) or .env."""

    model_config = SettingsConfigDict(
        env_prefix="LL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mode: Literal["web", "desktop"] = "web"
    data_dir: Path | None = None
    secret_key: str = ""
    access_code: str = ""
    cookie_secure: bool | None = None
    enforce_https: bool = False
    allowed_hosts: str = ""
    debug_docs: bool = False
    auth_rate_limit_max: int = 10
    auth_rate_limit_window_seconds: int = 300
    max_request_body_bytes: int = 15 * 1024 * 1024
    seed_url: str = ""
    rate_limit_rps: float = 2.0
    sync_interval_hours: int = 6
    sync_delay_seconds: float = 2.5
    sync_max_days_per_run: int = 25
    profile_cache_ttl_minutes: int = 30
    disable_background_sync: bool = False
    disable_update_check: bool = False
    app_version: str = "9.1.0"
    github_repo: str = "georgefahmy/LL"

    @property
    def parsed_allowed_hosts(self) -> list[str]:
        raw = [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]
        if not raw:
            return []
        for local_host in ("127.0.0.1", "localhost"):
            if local_host not in raw:
                raw.append(local_host)
        return raw

    @property
    def resolved_data_dir(self) -> Path:
        if self.data_dir is not None:
            path = self.data_dir.expanduser()
        elif self.mode == "desktop":
            path = Path.home() / ".LearnedLeague"
        elif Path("/data").exists() and os.access("/data", os.W_OK):
            path = Path("/data")
        else:
            path = Path.cwd() / ".data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_secret_key(self) -> str:
        placeholder = "replace-with-a-strong-random-secret-key"
        if self.secret_key.strip() == placeholder:
            raise ValueError(
                "LL_SECRET_KEY is still set to the example placeholder value. "
                "Generate a strong random secret key before starting the server."
            )
        if self.secret_key.strip():
            return self.secret_key.strip()

        key_file = self.resolved_data_dir / ".secret_key"
        if key_file.is_file():
            existing = key_file.read_text(encoding="utf-8").strip()
            if existing:
                return existing

        generated = secrets.token_urlsafe(48)
        try:
            key_file.write_text(generated, encoding="utf-8")
            os.chmod(key_file, 0o600)
        except OSError:
            logger.warning("Could not persist generated secret key to %s", key_file)

        if self.mode == "web":
            logger.warning(
                "LL_SECRET_KEY is not set; using auto-generated key in %s. "
                "Set LL_SECRET_KEY in .env for production deployments.",
                key_file,
            )
        return generated

    def is_cookie_secure(self, request_is_https: bool) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        if self.mode == "desktop":
            return False
        return request_is_https
