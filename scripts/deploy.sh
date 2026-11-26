#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="rsync"
SKIP_CHECKS=false
DRY_RUN=false

usage() {
  cat <<'EOF'
Usage: ./scripts/deploy.sh [OPTIONS]

Deploy and manage the LearnedLeague Practice Tool on your local Linux server.
Configuration is loaded from .deploy.env (see .deploy.env.example).

Modes (pick at most one; default is rsync local working tree):
  (default)       Run local checks, rsync code (excluding .env & data), rebuild & restart Docker
  --git           Pull latest branch on Linux server and rebuild/restart Docker
  --image         Pull prebuilt ghcr.io/georgefahmy/ll:latest image and restart Docker
  --init          Bootstrap remote DEPLOY_DIR and generate .env with LL_SECRET_KEY if absent
  --seed          Compress local all_data.json and upload into server /data/seed_questions.json.gz
  --status        Show remote container status and /api/meta JSON
  --logs          Tail live Docker logs from the server

Flags:
  --skip-checks   Skip local ruff / pytest / frontend typecheck before rsync deploy
  --dry-run       Show what would run without modifying the remote server
  -h, --help      Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --git) MODE="git"; shift ;;
    --image) MODE="image"; shift ;;
    --init) MODE="init"; shift ;;
    --seed) MODE="seed"; shift ;;
    --status) MODE="status"; shift ;;
    --logs) MODE="logs"; shift ;;
    --skip-checks) SKIP_CHECKS=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -f "$ROOT_DIR/.deploy.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.deploy.env"
  set +a
fi

DEPLOY_HOST="${DEPLOY_HOST:-}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/learnedleague}"
DEPLOY_PORT="${DEPLOY_PORT:-22}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
DEPLOY_HEALTH_URL="${DEPLOY_HEALTH_URL:-}"
DEPLOY_USE_CADDY="${DEPLOY_USE_CADDY:-false}"

COMPOSE_PROFILES_FLAG=""
if [[ "$DEPLOY_USE_CADDY" == "true" ]]; then
  COMPOSE_PROFILES_FLAG="--profile https"
fi

if [[ -z "$DEPLOY_HOST" ]]; then
  echo "ERROR: DEPLOY_HOST is not set. Copy .deploy.env.example to .deploy.env first." >&2
  exit 1
fi

SSH_OPTS=(-p "$DEPLOY_PORT" -o BatchMode=yes -o ConnectTimeout=10)
RSYNC_EXCLUDES=(
  "--exclude=.env"
  "--exclude=.deploy.env"
  "--exclude=.git"
  "--exclude=node_modules"
  "--exclude=.venv"
  "--exclude=resources"
  "--exclude=build"
  "--exclude=dist"
  "--exclude=__pycache__"
  "--exclude=.pytest_cache"
  "--exclude=.ruff_cache"
  "--exclude=.data"
  "--exclude=*.csv"
  "--exclude=seed_questions.json.gz"
)

run_ssh() {
  if [[ "$DRY_RUN" == true ]]; then
    echo "[dry-run] ssh ${SSH_OPTS[*]} $DEPLOY_HOST $*"
  else
    ssh "${SSH_OPTS[@]}" "$DEPLOY_HOST" "$@"
  fi
}

run_local_checks() {
  if [[ "$SKIP_CHECKS" == true ]]; then
    echo "Skipping local checks (--skip-checks)."
    return
  fi
  echo "==> Running local checks..."
  if command -v uv >/dev/null 2>&1; then
    uv run --no-sync ruff check backend desktop tests
    uv run --no-sync pytest -q
  fi
  if [[ -d "$ROOT_DIR/frontend/node_modules" ]]; then
    (cd "$ROOT_DIR/frontend" && npm run typecheck)
  fi
}

verify_remote_health() {
  if [[ "$DRY_RUN" == true ]]; then
    echo "[dry-run] Verify /api/health on $DEPLOY_HOST"
    return
  fi
  echo "==> Waiting for container health check..."
  local ok=false
  for _ in $(seq 1 20); do
    if ssh "${SSH_OPTS[@]}" "$DEPLOY_HOST" \
      "curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1"; then
      ok=true
      break
    fi
    sleep 2
  done
  if [[ "$ok" != true ]]; then
    echo "ERROR: Health check failed on $DEPLOY_HOST. Recent logs:" >&2
    ssh "${SSH_OPTS[@]}" "$DEPLOY_HOST" \
      "cd '$DEPLOY_DIR' && docker compose logs --tail=60" || true
    exit 1
  fi
  if [[ -n "$DEPLOY_HEALTH_URL" ]]; then
    curl -fsS "$DEPLOY_HEALTH_URL" >/dev/null
    echo "Public endpoint healthy: $DEPLOY_HEALTH_URL"
  fi
  echo "Deploy successful! Container is healthy on $DEPLOY_HOST."
}

case "$MODE" in
  init)
    echo "==> Bootstrapping $DEPLOY_HOST:$DEPLOY_DIR ..."
    SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
    run_ssh "mkdir -p '$DEPLOY_DIR'"
    if [[ "$DRY_RUN" == true ]]; then
      echo "[dry-run] rsync initial files and create .env if missing"
    else
      rsync -az -e "ssh -p $DEPLOY_PORT" "${RSYNC_EXCLUDES[@]}" \
        "$ROOT_DIR/" "$DEPLOY_HOST:$DEPLOY_DIR/"
      ssh "${SSH_OPTS[@]}" "$DEPLOY_HOST" "bash -s" <<EOF
set -euo pipefail
cd '$DEPLOY_DIR'
if [[ ! -f .env ]]; then
  cp .env.example .env
  sed -i "s|replace-with-a-strong-random-secret-key|$SECRET|" .env
  chmod 600 .env
  echo "Created new .env with generated LL_SECRET_KEY."
else
  echo "Existing .env preserved."
fi
EOF
    fi
    ;;

  rsync)
    run_local_checks
    echo "==> Syncing files to $DEPLOY_HOST:$DEPLOY_DIR ..."
    RSYNC_FLAGS=(-az --delete)
    if [[ "$DRY_RUN" == true ]]; then
      echo "[dry-run] rsync ${RSYNC_FLAGS[*]} -e 'ssh -p $DEPLOY_PORT' ${RSYNC_EXCLUDES[*]} '$ROOT_DIR/' '$DEPLOY_HOST:$DEPLOY_DIR/'"
    else
      rsync "${RSYNC_FLAGS[@]}" -e "ssh -p $DEPLOY_PORT" "${RSYNC_EXCLUDES[@]}" \
        "$ROOT_DIR/" "$DEPLOY_HOST:$DEPLOY_DIR/"
    fi
    echo "==> Rebuilding and restarting Docker Compose on $DEPLOY_HOST..."
    run_ssh "cd '$DEPLOY_DIR' && docker compose $COMPOSE_PROFILES_FLAG up -d --build --remove-orphans"
    verify_remote_health
    ;;

  git)
    echo "==> Pulling branch '$DEPLOY_BRANCH' and rebuilding on $DEPLOY_HOST..."
    run_ssh "cd '$DEPLOY_DIR' && git fetch origin && git checkout '$DEPLOY_BRANCH' && git pull --ff-only origin '$DEPLOY_BRANCH' && docker compose $COMPOSE_PROFILES_FLAG up -d --build --remove-orphans"
    verify_remote_health
    ;;

  image)
    echo "==> Pulling prebuilt image from GHCR on $DEPLOY_HOST..."
    run_ssh "cd '$DEPLOY_DIR' && LL_IMAGE=ghcr.io/georgefahmy/ll:latest docker compose $COMPOSE_PROFILES_FLAG pull && LL_IMAGE=ghcr.io/georgefahmy/ll:latest docker compose $COMPOSE_PROFILES_FLAG up -d --remove-orphans"
    verify_remote_health
    ;;

  seed)
    SRC_JSON=""
    if [[ -f "$ROOT_DIR/resources/all_data.json" ]]; then
      SRC_JSON="$ROOT_DIR/resources/all_data.json"
    elif [[ -f "$HOME/.LearnedLeague/all_data.json" ]]; then
      SRC_JSON="$HOME/.LearnedLeague/all_data.json"
    else
      echo "ERROR: Could not find resources/all_data.json or ~/.LearnedLeague/all_data.json" >&2
      exit 1
    fi
    TMP_GZ="/tmp/ll-seed-$$.json.gz"
    echo "==> Compressing $SRC_JSON..."
    if [[ "$DRY_RUN" == true ]]; then
      echo "[dry-run] gzip -c '$SRC_JSON' > '$TMP_GZ' && scp to $DEPLOY_HOST && docker compose cp into /data/seed_questions.json.gz"
    else
      trap 'rm -f "$TMP_GZ"' EXIT
      gzip -c "$SRC_JSON" > "$TMP_GZ"
      scp -P "$DEPLOY_PORT" "$TMP_GZ" "$DEPLOY_HOST:/tmp/ll_seed_questions.json.gz"
      ssh "${SSH_OPTS[@]}" "$DEPLOY_HOST" "bash -s" <<EOF
set -euo pipefail
cd '$DEPLOY_DIR'
docker compose cp /tmp/ll_seed_questions.json.gz learnedleague:/data/seed_questions.json.gz
rm -f /tmp/ll_seed_questions.json.gz
docker compose restart learnedleague
EOF
      verify_remote_health
    fi
    ;;

  status)
    run_ssh "cd '$DEPLOY_DIR' && docker compose ps && echo '' && curl -fsS http://127.0.0.1:8000/api/meta | python3 -m json.tool"
    ;;

  logs)
    run_ssh "cd '$DEPLOY_DIR' && docker compose logs -f --tail=100"
    ;;
esac
