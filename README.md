# LearnedLeague Practice Tool & Analytics Suite (v9.0)

Practice past LearnedLeague seasons, OneDay Specials, Mini Leagues, and Mock Match Days, or sign in with your LearnedLeague account to analyze player statistics, defense tactics, HUN similarity, OLS Luck Analysis, and full player question histories.

Runs identically in **two modes from one unified FastAPI + React codebase**:
1. **Self-Hosted Web App** on your Linux server at `https://ll.n890gf.com`.
2. **Downloadable Desktop App** for **macOS** and **Windows** via GitHub Releases (`pywebview` native window).

---

## Option 1: Online Web App (`https://ll.n890gf.com`)

### 1. Initial Server Bootstrap (from your laptop)

1. Copy `.deploy.env.example` to `.deploy.env` and set your Linux server SSH details (`DEPLOY_HOST`, `DEPLOY_DIR`, `DEPLOY_HEALTH_URL=https://ll.n890gf.com/api/health`).
2. Run one-time setup to initialize `/opt/learnedleague` and generate a strong `LL_SECRET_KEY` in `.env` on the server:
   ```bash
   ./scripts/deploy.sh --init
   ```
3. *(Optional)* To require a shared passphrase before anyone can open the web app, SSH into the server and set `LL_ACCESS_CODE=...` inside `/opt/learnedleague/.env`.
4. *(Optional)* Seed the Linux server instantaneously from your local `resources/all_data.json` (or `~/.LearnedLeague/all_data.json`) so it doesn't have to scrape all historical seasons from scratch:
   ```bash
   ./scripts/deploy.sh --seed
   ```
5. Deploy updates anytime after iterating locally:
   ```bash
   ./scripts/deploy.sh
   ```

Other useful `scripts/deploy.sh` commands:
- `./scripts/deploy.sh --git` — pull `main` on the server and rebuild/restart
- `./scripts/deploy.sh --image` — pull prebuilt `ghcr.io/georgefahmy/ll:latest` and restart
- `./scripts/deploy.sh --status` — check container status and `/api/meta`
- `./scripts/deploy.sh --logs` — stream container logs

### 2. Automatic HTTPS & Reverse Proxy (`ll.n890gf.com`)

You have two easy ways to serve `https://ll.n890gf.com` with automatic TLS certificates:
- **Built-in Docker Caddy (`DEPLOY_USE_CADDY=true`):** Set `DEPLOY_USE_CADDY=true` in `.deploy.env` (requires ports `80` and `443` open on your Linux server pointing to `ll.n890gf.com`). `./scripts/deploy.sh` will launch [deploy/Caddyfile](deploy/Caddyfile) with automatic Let's Encrypt HTTPS, TLS 1.2/1.3, and HSTS.
- **External Reverse Proxy / Tunnel:** Leave `DEPLOY_USE_CADDY=false` and point your existing host Caddy ([deploy/Caddyfile.example](deploy/Caddyfile.example)), Nginx ([deploy/nginx.conf.example](deploy/nginx.conf.example)), or Cloudflare Tunnel ([deploy/cloudflared.example.yml](deploy/cloudflared.example.yml)) to `127.0.0.1:8000`.

### Security & Privacy in Hosted Mode
- **HTTPS & Transport:** `.env.example` sets `LL_ENFORCE_HTTPS=true` and `LL_COOKIE_SECURE=true`, rejects non-HTTPS auth submissions, and sends HSTS (`Strict-Transport-Security`), strict CSP (`script-src 'self'`), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and `Cache-Control: no-store` on authenticated routes.
- **CSRF, Host & Brute-Force Protection:** Mutating `/api/*` routes validate `Origin` / `Sec-Fetch-Site`, `LL_ALLOWED_HOSTS` prevents Host header injection, and `LL_AUTH_RATE_LIMIT_MAX` rate-limits login/gate attempts per IP.
- **Container Hardening:** Runs as non-root `appuser` with `read_only: true` root filesystem, `cap_drop: ALL`, `no-new-privileges:true`, and memory/PID caps.
- **Zero Password Storage:** LearnedLeague passwords are sent over HTTPS once to `learnedleague.com/ucp.php?mode=login` and **immediately discarded** (never written to disk, database, or logs). Only encrypted session cookies (`HttpOnly`, `SameSite=Lax`, `Secure`) are kept in the user's browser, with a **Paste Session Cookie** tab as fallback.
- **Browser-Local Personal Data:** Practice answers, completed OneDays, and favorite players are stored privately inside each user's browser (IndexedDB) with JSON Export/Import in **Settings**.

---

## Option 2: Desktop Download (macOS & Windows)

Download the latest release from [GitHub Releases](https://github.com/georgefahmy/LL/releases/latest):
- **macOS:** Open `LearnedLeague-<version>-macos-<arch>.dmg`, drag **LearnedLeague.app** into **Applications**. First launch on unsigned builds: Right-click -> **Open** (or allow in System Settings -> Privacy & Security).
- **Windows:** Extract `LearnedLeague-Windows.zip` and launch `LearnedLeague.exe` (click **More info -> Run anyway** if SmartScreen prompts for unsigned binaries).

Existing `~/.LearnedLeague/` data (questions, practice answer history, favorites, OneDays, Mock Match Days) is imported automatically and non-destructively into `~/.LearnedLeague/app.db`, and optional Remember Me sessions use your OS Keychain instead of plaintext files.

### Releasing & Building macOS `.dmg`

Use `scripts/release.py` to keep versions synchronized across `pyproject.toml`, `backend/config.py`, `frontend/package.json`, and `desktop/learnedleague.spec`, package a compressed macOS `.dmg` + `.sha256`, tag git, and publish to GitHub Releases (requires `gh auth login`):

```bash
# 1. Build locally (.app + .dmg in dist/, no git/GitHub changes)
uv run python scripts/release.py build

# 2. Dry-run a release (preview version bump, git tag, and GitHub Release)
uv run python scripts/release.py dry-run patch

# 3. Build, bump version, tag git, and publish to GitHub Releases
uv run python scripts/release.py publish patch   # or minor, major, 9.1.0 (optional --draft)
```

---

## Local Development

```bash
# Backend (Python 3.12+)
uv sync --extra dev --extra desktop
uv run pytest -v

# Frontend
cd frontend && npm ci && npm run dev
# In another terminal, run the FastAPI backend:
uv run uvicorn backend.api.app:create_app --factory --reload --port 8000
```
