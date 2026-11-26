# Changelog

### [v9.0.0] - 2026-11-19
- **Unified Web + Desktop Architecture:** Replaced the macOS-only `FreeSimpleGUI` desktop app with a unified FastAPI + React/TypeScript/Vite application that runs both self-hosted via Docker on Linux and as a native desktop app (`pywebview` + PyInstaller) for macOS and Windows.
- **Full Feature Parity + Luck Analysis:** Practice Past Seasons (S60–latest), OneDay Specials, Mini Leagues (supports dynamic question counts), Mock Match Day, Player Tracker/Stats, Defense Tactics (HUN, interactive 18-category SVG Radar Chart, Category Metrics, live Today's Questions, Defense Point Recommender), OLS Luck Analysis (with SOS, Rundle filter, custom ratio columns, and missing-player warnings), and Question History.
- **Scraping & Startup Reliability:** Instant `<1s` launch from SQLite WAL cache with non-blocking incremental background match-day syncing, unified browser headers across every scraper, request timeouts/retries/rate limiting, and safe fallbacks for missing OneDay metrics and rookie profiles.
- **Security & Auth:** Discards passwords immediately in web mode using Fernet-encrypted `HttpOnly` session cookies + "Paste Session Cookie" fallback; uses OS Keychain (`keyring`) in desktop mode with one-click cleanup for legacy plaintext `login_info.json`; SSRF-hardened image proxy; safe read-only GitHub release check replacing the `sudo` updater.
- **Deployment & CI/CD:** Added multi-stage `Dockerfile`, `docker-compose.yml`, reverse proxy templates, `scripts/deploy.sh` for fast laptop-to-Linux server iteration, and GitHub Actions workflows for CI, macOS `.dmg`, Windows `.zip`, and GHCR Docker releases.

### [v8.1.0] - 2026-05-26
Fixed a requests session header issue.
