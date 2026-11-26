from __future__ import annotations

import logging
import os
import socket
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

import httpx
import uvicorn
import webview

# Ensure project root is importable when invoked directly as `python desktop/launcher.py`
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

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


def _log_startup_failure() -> None:
    """Persist startup tracebacks for GUI launches where stderr is not visible."""
    tb = traceback.format_exc()
    logger.exception("LearnedLeague desktop launcher failed")
    try:
        log_dir = Path.home() / ".LearnedLeague"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "desktop_launcher.log").open("a", encoding="utf-8") as fh:
            fh.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}]\n{tb}")
    except OSError:
        pass


def _run_self_test() -> None:
    """Verify frozen bundle imports and FastAPI app creation headlessly."""
    from backend.api.app import create_app
    from backend.config import AppSettings

    with tempfile.TemporaryDirectory() as tmpdir:
        test_settings = AppSettings(
            mode="desktop",
            data_dir=Path(tmpdir),
            disable_background_sync=True,
            disable_update_check=True,
        )
        create_app(test_settings)
    print("OK", flush=True)


def main() -> None:
    if "--ll-browser-worker" in sys.argv:
        idx = sys.argv.index("--ll-browser-worker")
        from backend.core.browser_worker import main as worker_main

        raise SystemExit(worker_main(sys.argv[idx + 1 :]))

    try:
        if "--self-test" in sys.argv:
            _run_self_test()
            return

        from backend.api.app import create_app
        from backend.config import AppSettings

        os.environ.setdefault("LL_MODE", "desktop")
        os.environ.setdefault(
            "LL_SEED_URL", "https://ll.n890gf.com/api/questions/export.json.gz"
        )
        settings = AppSettings(mode="desktop")
        app = create_app(settings)
        app.state.ll.browser_manager.enable_in_process_mode()

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

        main_window = webview.create_window(
            "LearnedLeague Practice Tool",
            url=base_url,
            width=1440,
            height=900,
            min_size=(960, 680),
            text_select=True,
        )
        if main_window is not None:
            main_window.events.closed += app.state.ll.browser_manager.shutdown
        try:
            webview.start(private_mode=False)
        finally:
            app.state.ll.browser_manager.shutdown()
            server.should_exit = True
            server_thread.join(timeout=3.0)
    except Exception:
        _log_startup_failure()
        raise


if __name__ == "__main__":
    main()
