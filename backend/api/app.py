from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ..config import AppSettings, resolve_bundle_path
from ..core.auth import AccessGateCodec, DesktopKeychainStore, SessionCookieCodec
from ..core.browser_session import InteractiveBrowserManager
from ..core.cache import CacheStore
from ..core.http_client import (
    LLAuthExpiredError,
    LLAuthFailedError,
    LLInvalidUrlError,
    LLNetworkError,
    LLNotFoundError,
    LLParseError,
    LLRateLimitError,
    TokenBucketRateLimiter,
)
from ..core.scrapers.seasons import SeasonSyncWorker
from .deps import SESSION_COOKIE_NAME, AppState
from .routes import (
    auth,
    defense,
    extension,
    health,
    luck,
    minileagues,
    mock_day,
    onedays,
    players,
    questions,
)
from .security import (
    AuthRateLimiter,
    CsrfOriginMiddleware,
    MaxBodySizeMiddleware,
    SecurityHeadersMiddleware,
    is_request_https,
)

logger = logging.getLogger(__name__)


def _seed_initial_questions(settings: AppSettings, cache: CacheStore) -> None:
    data_dir = settings.resolved_data_dir

    if settings.mode == "desktop":
        mig = cache.migrate_legacy_directory(data_dir, import_personal=True)
        if any(mig.values()):
            logger.info("Migrated legacy ~/.LearnedLeague data: %s", mig)

    # 1) Gzip seed dropped in data_dir (e.g. via deploy.sh --seed); apply if new or updated
    data_dir_gz = data_dir / "seed_questions.json.gz"
    if data_dir_gz.is_file():
        stat = data_dir_gz.stat()
        sig = f"{stat.st_mtime_ns}:{stat.st_size}"
        if cache.get_meta("seed_gz_sig") != sig:
            try:
                count = cache.seed_from_gzip(data_dir_gz)
                cache.set_meta("seed_gz_sig", sig)
                logger.info("Seeded %d questions from %s", count, data_dir_gz)
                return
            except Exception as exc:
                logger.warning("Failed reading %s: %s", data_dir_gz, exc)

    if cache.count_questions() > 0:
        return

    # 2) Gzip seed bundled inside PyInstaller or Docker image
    bundled_gz = resolve_bundle_path("seed_questions.json.gz")
    if bundled_gz.is_file():
        try:
            count = cache.seed_from_gzip(bundled_gz)
            logger.info("Seeded %d questions from bundled archive", count)
            return
        except Exception as exc:
            logger.warning("Failed reading bundled seed_questions.json.gz: %s", exc)

    # 3) Local dev resources/all_data.json (gitignored)
    dev_json = resolve_bundle_path("resources/all_data.json")
    if dev_json.is_file():
        try:
            count, _ = cache.seed_from_json(dev_json, import_answers=False)
            logger.info("Seeded %d questions from %s", count, dev_json)
        except Exception as exc:
            logger.warning("Failed reading %s: %s", dev_json, exc)


def create_app(settings: AppSettings | None = None) -> FastAPI:
    cfg = settings or AppSettings()
    data_dir = cfg.resolved_data_dir
    secret = cfg.get_secret_key()

    cache = CacheStore(data_dir / "app.db")
    rate_limiter = TokenBucketRateLimiter(cfg.rate_limit_rps)
    auth_rate_limiter = AuthRateLimiter(
        max_attempts=cfg.auth_rate_limit_max,
        window_seconds=cfg.auth_rate_limit_window_seconds,
    )
    session_codec = SessionCookieCodec(secret)
    gate_codec = AccessGateCodec(secret, cfg.access_code)
    keychain = DesktopKeychainStore(enabled=(cfg.mode == "desktop"))
    browser_manager = InteractiveBrowserManager()
    sync_worker = SeasonSyncWorker(
        cache,
        rate_limiter,
        seed_url=cfg.seed_url,
        sync_interval_hours=cfg.sync_interval_hours,
        sync_delay_seconds=cfg.sync_delay_seconds,
        max_days_per_run=cfg.sync_max_days_per_run,
        browser_manager=browser_manager,
    )

    state = AppState(
        settings=cfg,
        cache=cache,
        rate_limiter=rate_limiter,
        auth_rate_limiter=auth_rate_limiter,
        session_codec=session_codec,
        gate_codec=gate_codec,
        keychain=keychain,
        sync_worker=sync_worker,
        browser_manager=browser_manager,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        _seed_initial_questions(cfg, cache)
        if not cfg.disable_background_sync:
            sync_worker.start()
        try:
            yield
        finally:
            sync_worker.stop()
            browser_manager.shutdown()
            cache.close()

    expose_docs = cfg.mode == "desktop" or cfg.debug_docs
    app = FastAPI(
        title="LearnedLeague Practice Tool",
        version=cfg.app_version,
        lifespan=lifespan,
        docs_url="/docs" if expose_docs else None,
        redoc_url="/redoc" if expose_docs else None,
        openapi_url="/openapi.json" if expose_docs else None,
    )
    app.state.ll = state

    # Register inner -> outer middleware
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=cfg.max_request_body_bytes)
    app.add_middleware(CsrfOriginMiddleware)
    allowed_hosts = cfg.parsed_allowed_hosts
    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.add_middleware(SecurityHeadersMiddleware, mode=cfg.mode)

    # ---- Structured Domain Error Handlers ----

    @app.exception_handler(LLAuthExpiredError)
    async def _handle_auth_expired(req: Request, exc: LLAuthExpiredError) -> JSONResponse:
        resp = JSONResponse(
            status_code=401,
            content={"detail": str(exc), "code": "LL_AUTH_EXPIRED"},
        )
        resp.delete_cookie(
            key=SESSION_COOKIE_NAME,
            path="/",
            httponly=True,
            samesite="lax",
            secure=cfg.is_cookie_secure(is_request_https(req)),
        )
        return resp

    @app.exception_handler(LLAuthFailedError)
    async def _handle_auth_failed(_: Request, exc: LLAuthFailedError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": str(exc), "code": "LL_AUTH_FAILED"},
        )

    @app.exception_handler(LLRateLimitError)
    async def _handle_rate_limit(_: Request, exc: LLRateLimitError) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": str(exc), "code": "LL_RATE_LIMITED"},
        )

    @app.exception_handler(LLNotFoundError)
    async def _handle_not_found(_: Request, exc: LLNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc), "code": "LL_NOT_FOUND"},
        )

    @app.exception_handler(LLInvalidUrlError)
    async def _handle_invalid_url(_: Request, exc: LLInvalidUrlError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc), "code": "LL_INVALID_URL"},
        )

    @app.exception_handler(LLParseError)
    async def _handle_parse_error(_: Request, exc: LLParseError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"detail": str(exc), "code": "LL_PARSE_ERROR"},
        )

    @app.exception_handler(LLNetworkError)
    async def _handle_network_error(_: Request, exc: LLNetworkError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"detail": str(exc), "code": "LL_NETWORK_ERROR"},
        )

    # ---- API Routers ----

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(questions.router)
    app.include_router(onedays.router)
    app.include_router(minileagues.router)
    app.include_router(mock_day.router)
    app.include_router(players.router)
    app.include_router(defense.router)
    app.include_router(extension.router)
    app.include_router(luck.router)

    # ---- Static SPA Frontend ----

    frontend_dist = resolve_bundle_path("frontend/dist")
    assets_dir = frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found.")
        if not expose_docs and full_path in {"docs", "redoc", "openapi.json"}:
            raise HTTPException(status_code=404, detail="Not found.")

        index_file = frontend_dist / "index.html"
        if not index_file.is_file():
            raise HTTPException(
                status_code=503,
                detail="Frontend assets are not built. Run 'npm run build' in frontend/.",
            )

        if full_path:
            candidate = (frontend_dist / full_path).resolve()
            if (
                candidate.is_file()
                and frontend_dist.resolve() in candidate.parents
            ):
                return FileResponse(candidate)

        return FileResponse(index_file)

    return app

