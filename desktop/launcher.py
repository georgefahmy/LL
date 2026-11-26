from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn
import webview

# Ensure project root is importable when invoked directly as `python desktop/launcher.py`
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.api.app import create_app  # noqa: E402
from backend.config import AppSettings  # noqa: E402

logger = logging.getLogger(__name__)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_health(url: str, timeout_seconds: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=1.0)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.15)
    return False


def main() -> None:
    if "--ll-browser-worker" in sys.argv:
        idx = sys.argv.index("--ll-browser-worker")
        from backend.core.browser_worker import main as worker_main

        raise SystemExit(worker_main(sys.argv[idx + 1 :]))

    os.environ.setdefault("LL_MODE", "desktop")
    os.environ.setdefault(
        "LL_SEED_URL", "https://ll.n890gf.com/api/questions/export.json.gz"
    )
    settings = AppSettings(mode="desktop")
    app = create_app(settings)

    port = _find_free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server_thread = threading.Thread(
        target=server.run,
        name="ll-desktop-uvicorn",
        daemon=True,
    )
    server_thread.start()

    base_url = f"http://127.0.0.1:{port}"
    if not _wait_for_health(f"{base_url}/api/health", timeout_seconds=15.0):
        logger.error("Backend failed to start on %s", base_url)
        server.should_exit = True
        sys.exit(1)

    webview.create_window(
        "LearnedLeague Practice Tool",
        url=base_url,
        width=1440,
        height=900,
        min_size=(960, 680),
        text_select=True,
    )
    try:
        webview.start(private_mode=False)
    finally:
        server.should_exit = True
        server_thread.join(timeout=3.0)


if __name__ == "__main__":
    main()
