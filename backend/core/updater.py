from __future__ import annotations

import threading
import time
from typing import Any

import httpx
from packaging import version

_CACHE_TTL_SECONDS = 6 * 3600
_cache_lock = threading.Lock()
_cached_result: dict[str, Any] | None = None
_cached_at: float = 0.0


def check_latest_release(
    current_version: str,
    repo: str = "georgefahmy/LL",
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Read-only check against GitHub Releases API (never downloads or runs sudo)."""
    global _cached_result, _cached_at

    with _cache_lock:
        is_fresh = (time.time() - _cached_at) < _CACHE_TTL_SECONDS
        if not force and _cached_result is not None and is_fresh:
            return dict(_cached_result)

    default_res = {
        "current_version": current_version,
        "latest_version": current_version,
        "update_available": False,
        "release_url": f"https://github.com/{repo}/releases/latest",
    }

    try:
        resp = httpx.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "LearnedLeagueTool/9.0",
            },
            timeout=5.0,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return default_res
        payload = resp.json()
        tag_name = str(payload.get("tag_name", "")).strip()
        latest_ver = tag_name.lstrip("v")
        if not latest_ver:
            return default_res
        update_available = version.parse(latest_ver) > version.parse(current_version.lstrip("v"))
        res = {
            "current_version": current_version,
            "latest_version": latest_ver,
            "update_available": update_available,
            "release_url": str(payload.get("html_url") or default_res["release_url"]),
        }
    except Exception:
        return default_res

    with _cache_lock:
        _cached_result = dict(res)
        _cached_at = time.time()
    return res
