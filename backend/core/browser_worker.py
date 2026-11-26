from __future__ import annotations

import argparse
import hmac
import json
import logging
import sys
import threading
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .constants import LOGIN_URL


def _import_webview() -> Any:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "Interactive browser login requires pywebview, which is not installed."
        ) from exc
    return webview

logger = logging.getLogger(__name__)

_WAF_MARKERS = (
    "cf-browser-verification",
    "attention required! | cloudflare",
    "just a moment...",
    "enable javascript and cookies to continue",
)


def is_allowed_ll_url(url: str) -> bool:
    """Allow only https://(www.)learnedleague.com URLs."""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and host in {
        "www.learnedleague.com",
        "learnedleague.com",
    }


@dataclass
class _PendingFetch:
    event: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] = field(default_factory=dict)


class _WorkerBridgeState:
    def __init__(self, token: str) -> None:
        self.token = token
        self.window: Any | None = None
        self.lock = threading.Lock()
        self.loaded_event = threading.Event()
        self.nav_event = threading.Event()
        self.nav_lock = threading.Lock()
        self.closed = False
        self.authenticated = False
        self.username: str | None = None
        self.formatted_username: str | None = None
        self.profile_id: str | None = None
        self.hidden_after_login = False
        self.pending_fetches: dict[str, _PendingFetch] = {}

    def verify_token(self, header_val: str | None) -> bool:
        if not header_val:
            return False
        return hmac.compare_digest(header_val.encode("utf-8"), self.token.encode("utf-8"))

    def register_fetch(self) -> tuple[str, _PendingFetch]:
        req_id = uuid.uuid4().hex
        pending = _PendingFetch()
        with self.lock:
            self.pending_fetches[req_id] = pending
        return req_id, pending

    def pop_fetch(self, req_id: str) -> _PendingFetch | None:
        with self.lock:
            return self.pending_fetches.pop(req_id, None)

    def complete_fetch(
        self,
        req_id: str,
        ok: bool,
        status: int,
        final_url: str,
        body: str,
    ) -> None:
        with self.lock:
            pending = self.pending_fetches.get(req_id)
        if pending is None:
            return
        pending.result = {
            "ok": bool(ok),
            "status": int(status),
            "final_url": str(final_url),
            "body": str(body),
        }
        pending.event.set()

    def set_authenticated(self, profile_id: str, formatted_username: str) -> None:
        clean_name = formatted_username.strip() or profile_id.strip()
        with self.lock:
            self.authenticated = True
            self.profile_id = profile_id.strip()
            self.formatted_username = clean_name
            self.username = clean_name.lower()
            should_hide = not self.hidden_after_login
            if should_hide:
                self.hidden_after_login = True
        if should_hide and self.window is not None:
            try:
                self.window.hide()
            except Exception:
                pass

    def show_window(self) -> None:
        with self.lock:
            self.hidden_after_login = False
        if self.window is not None and not self.closed:
            try:
                self.window.show()
            except Exception:
                pass

    def mark_loaded(self) -> None:
        self.loaded_event.set()
        self.nav_event.set()

    def mark_closed(self) -> None:
        with self.lock:
            self.closed = True
            pending_items = list(self.pending_fetches.values())
            self.pending_fetches.clear()
        self.nav_event.set()
        for p in pending_items:
            p.result = {
                "ok": False,
                "status": 0,
                "final_url": "",
                "body": "Interactive browser window was closed.",
            }
            p.event.set()


class _WorkerJsApi:
    """JS bridge exposed to the pywebview window via window.pywebview.api."""

    def __init__(self, state: _WorkerBridgeState) -> None:
        self._state = state

    def complete_fetch(
        self,
        req_id: str,
        ok: bool,
        status: int,
        final_url: str,
        body: str,
    ) -> None:
        self._state.complete_fetch(req_id, ok, status, final_url, body)

    def report_login_state(
        self,
        authenticated: bool,
        profile_id: str = "",
        formatted_username: str = "",
    ) -> None:
        if authenticated and profile_id.isdigit():
            self._state.set_authenticated(profile_id, formatted_username)


_AUTH_CHECK_JS = """
(() => {
  try {
    const host = (window.location.hostname || "").toLowerCase();
    if (!host.endsWith("learnedleague.com")) {
      return { authenticated: false };
    }
    const links = Array.from(document.querySelectorAll("a.flag"));
    for (const a of links) {
      const href = a.getAttribute("href") || "";
      const match = href.match(/profiles\\.php\\?(\\d+)/);
      if (match) {
        const img = a.querySelector("img");
        const title = img ? (img.getAttribute("title") || "").trim() : "";
        const text = (a.textContent || "").trim();
        const name = title || text || match[1];
        return {
          authenticated: true,
          profile_id: match[1],
          formatted_username: name,
        };
      }
    }
    return { authenticated: false };
  } catch (err) {
    return { authenticated: false };
  }
})()
"""


def _check_dom_login(state: _WorkerBridgeState) -> dict[str, Any]:
    with state.lock:
        if state.closed:
            return {"running": False, "authenticated": False}
        if state.authenticated and state.profile_id:
            return {
                "running": True,
                "authenticated": True,
                "username": state.username,
                "formatted_username": state.formatted_username,
                "profile_id": state.profile_id,
            }

    if state.window is None or not state.loaded_event.is_set():
        return {"running": True, "authenticated": False}

    try:
        res = state.window.evaluate_js(_AUTH_CHECK_JS)
    except Exception:
        return {"running": True, "authenticated": False}

    if (
        isinstance(res, dict)
        and res.get("authenticated")
        and str(res.get("profile_id", "")).isdigit()
    ):
        pid = str(res["profile_id"])
        fname = str(res.get("formatted_username") or pid)
        state.set_authenticated(pid, fname)
        return {
            "running": True,
            "authenticated": True,
            "username": state.username,
            "formatted_username": state.formatted_username,
            "profile_id": state.profile_id,
        }

    return {"running": True, "authenticated": False}


def _is_transient_or_cors_fetch_error(result: dict[str, Any]) -> bool:
    if result.get("ok") or int(result.get("status", 0)) != 0:
        return False
    body_lower = str(result.get("body", "")).lower()
    if "window was closed" in body_lower or "not ready" in body_lower:
        return False
    return any(
        marker in body_lower
        for marker in ("load failed", "failed to fetch", "networkerror", "typeerror")
    )


def _dispatch_js_fetch(state: _WorkerBridgeState, url: str) -> dict[str, Any]:
    req_id, pending = state.register_fetch()
    fetch_js = f"""
    (() => {{
      const reqId = {json.dumps(req_id)};
      const rawUrl = {json.dumps(url)};
      let targetUrl = rawUrl;
      try {{
        const parsed = new URL(rawUrl, window.location.origin);
        const curHost = (window.location.hostname || "").toLowerCase();
        if (
          parsed.hostname.toLowerCase().endsWith("learnedleague.com")
          && curHost.endsWith("learnedleague.com")
        ) {{
          targetUrl = window.location.origin + parsed.pathname + parsed.search;
        }}
      }} catch (_) {{}}
      fetch(targetUrl, {{ credentials: "include" }})
        .then(async (resp) => {{
          const text = await resp.text();
          if (window.pywebview && window.pywebview.api) {{
            window.pywebview.api.complete_fetch(
              reqId, true, resp.status, resp.url || targetUrl, text
            );
          }}
        }})
        .catch((err) => {{
          if (window.pywebview && window.pywebview.api) {{
            window.pywebview.api.complete_fetch(
              reqId, false, 0, targetUrl, String(err || "Fetch failed")
            );
          }}
        }});
      return "dispatched";
    }})()
    """
    try:
        state.window.evaluate_js(fetch_js)
    except Exception as exc:
        state.pop_fetch(req_id)
        return {
            "ok": False,
            "status": 0,
            "final_url": url,
            "body": f"Browser evaluation failed: {exc}",
        }

    if not pending.event.wait(timeout=25.0):
        state.pop_fetch(req_id)
        return {
            "ok": False,
            "status": 0,
            "final_url": url,
            "body": "Timed out waiting for browser fetch.",
        }

    state.pop_fetch(req_id)
    return pending.result


_READ_DOC_JS = """
(() => ({
  url: window.location.href || "",
  html: document.documentElement ? document.documentElement.outerHTML : ""
}))()
"""


def _navigate_and_read_html(state: _WorkerBridgeState, url: str) -> dict[str, Any]:
    with state.nav_lock:
        if state.window is None or state.closed:
            return {
                "ok": False,
                "status": 0,
                "final_url": url,
                "body": "Interactive browser session is not ready.",
            }
        state.nav_event.clear()
        try:
            state.window.load_url(url)
        except Exception as exc:
            return {
                "ok": False,
                "status": 0,
                "final_url": url,
                "body": f"Browser navigation failed: {exc}",
            }

        if not state.nav_event.wait(timeout=20.0) or state.closed:
            return {
                "ok": False,
                "status": 0,
                "final_url": url,
                "body": "Timed out waiting for browser navigation.",
            }

        try:
            nav_res = state.window.evaluate_js(_READ_DOC_JS)
        except Exception as exc:
            return {
                "ok": False,
                "status": 0,
                "final_url": url,
                "body": f"Browser DOM read failed: {exc}",
            }

    if isinstance(nav_res, dict) and nav_res.get("html"):
        return {
            "ok": True,
            "status": 200,
            "final_url": str(nav_res.get("url") or url),
            "body": str(nav_res["html"]),
        }
    return {
        "ok": False,
        "status": 0,
        "final_url": url,
        "body": "Empty document returned after browser navigation.",
    }


def _run_in_browser_fetch(
    state: _WorkerBridgeState,
    url: str,
    *,
    require_auth: bool,
) -> dict[str, Any]:
    if not is_allowed_ll_url(url):
        raise ValueError("Only https://learnedleague.com URLs are allowed.")
    if state.window is None or state.closed or not state.loaded_event.is_set():
        return {
            "ok": False,
            "status": 0,
            "final_url": url,
            "body": "Interactive browser session is not ready.",
        }

    result = _dispatch_js_fetch(state, url)
    if _is_transient_or_cors_fetch_error(result) and not state.closed:
        result = _dispatch_js_fetch(state, url)
    if _is_transient_or_cors_fetch_error(result) and not state.closed:
        nav_result = _navigate_and_read_html(state, url)
        if nav_result.get("ok"):
            result = nav_result

    status = int(result.get("status", 0))
    body_lower = str(result.get("body", ""))[:6000].lower()
    final_url_lower = str(result.get("final_url", "")).lower()

    if require_auth and (
        any(marker in body_lower for marker in _WAF_MARKERS)
        or "ucp.php?mode=login" in final_url_lower
        or (status == 403 and any(marker in body_lower for marker in _WAF_MARKERS))
    ):
        state.show_window()

    return result


def _make_handler(state: _WorkerBridgeState, server_ref: dict[str, ThreadingHTTPServer]):
    class _BridgeHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_json(self, code: int, payload: dict[str, Any]) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length) if length > 0 else b"{}"
            return json.loads(raw.decode("utf-8"))

        def _authorized(self) -> bool:
            if not state.verify_token(self.headers.get("X-Bridge-Token")):
                self._send_json(HTTPStatus.UNAUTHORIZED, {"detail": "Unauthorized"})
                return False
            return True

        def do_GET(self) -> None:
            if not self._authorized():
                return
            if self.path == "/status":
                self._send_json(HTTPStatus.OK, _check_dom_login(state))
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"detail": "Not found"})

        def do_POST(self) -> None:
            if not self._authorized():
                return
            if self.path == "/fetch":
                try:
                    payload = self._read_json()
                    url = str(payload.get("url") or "")
                    require_auth = bool(payload.get("require_auth", False))
                    res = _run_in_browser_fetch(state, url, require_auth=require_auth)
                    self._send_json(HTTPStatus.OK, res)
                except ValueError as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"detail": str(exc)})
                except Exception as exc:
                    self._send_json(HTTPStatus.BAD_GATEWAY, {"detail": str(exc)})
                return

            if self.path == "/show":
                state.show_window()
                self._send_json(HTTPStatus.OK, {"shown": True})
                return

            if self.path == "/shutdown":
                self._send_json(HTTPStatus.OK, {"shutting_down": True})
                state.mark_closed()
                if state.window is not None:
                    try:
                        state.window.destroy()
                    except Exception:
                        pass
                srv = server_ref.get("server")
                if srv is not None:
                    threading.Thread(target=srv.shutdown, daemon=True).start()
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"detail": "Not found"})

    return _BridgeHandler


class InProcessBrowserBridge:
    """In-process pywebview login window controller for single-Dock-icon desktop launches."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state: _WorkerBridgeState | None = None

    def start_or_show(self) -> dict[str, Any]:
        with self._lock:
            if self._state is not None and not self._state.closed:
                status = _check_dom_login(self._state)
                if status.get("authenticated"):
                    return {"status": "authenticated", **status}
                self._state.show_window()
                return {"status": "waiting_for_user", "authenticated": False}

            wv = _import_webview()
            state = _WorkerBridgeState(token="in-process")
            js_api = _WorkerJsApi(state)
            self._state = state
            window = wv.create_window(
                "LearnedLeague Interactive Sign-In",
                url=LOGIN_URL,
                js_api=js_api,
                width=1024,
                height=760,
                min_size=(760, 580),
                text_select=True,
            )
            if window is None:
                self._state = None
                raise RuntimeError("Could not create interactive login window.")
            state.window = window
            if window.events.loaded.is_set():
                state.mark_loaded()
            window.events.loaded += state.mark_loaded
            window.events.closed += state.mark_closed
            return {"status": "waiting_for_user", "authenticated": False}

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            state = self._state
        if state is None or state.closed:
            return {"running": False, "authenticated": False}
        return _check_dom_login(state)

    def fetch(self, url: str, *, require_auth: bool = False) -> dict[str, Any]:
        with self._lock:
            state = self._state
        if state is None or state.closed:
            raise RuntimeError("Interactive browser session is not running.")
        return _run_in_browser_fetch(state, url, require_auth=require_auth)

    def shutdown(self) -> None:
        with self._lock:
            state = self._state
            self._state = None
        if state is None:
            return
        win = state.window
        state.mark_closed()
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Interactive LearnedLeague pywebview worker.")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--token", type=str, required=True)
    args = parser.parse_args(argv)
    wv = _import_webview()

    state = _WorkerBridgeState(token=args.token)
    server_ref: dict[str, ThreadingHTTPServer] = {}
    handler_cls = _make_handler(state, server_ref)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_cls)
    server_ref["server"] = server

    server_thread = threading.Thread(
        target=server.serve_forever,
        name="ll-browser-bridge",
        daemon=True,
    )
    server_thread.start()

    js_api = _WorkerJsApi(state)
    window = wv.create_window(
        "LearnedLeague Interactive Sign-In",
        url=LOGIN_URL,
        js_api=js_api,
        width=1024,
        height=760,
        min_size=(760, 580),
        text_select=True,
    )
    if window is None:
        server.shutdown()
        return 1

    state.window = window

    def _on_loaded() -> None:
        state.mark_loaded()

    def _on_closed() -> None:
        state.mark_closed()
        srv = server_ref.get("server")
        if srv is not None:
            threading.Thread(target=srv.shutdown, daemon=True).start()

    window.events.loaded += _on_loaded
    window.events.closed += _on_closed

    try:
        wv.start(private_mode=False)
    finally:
        state.mark_closed()
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
