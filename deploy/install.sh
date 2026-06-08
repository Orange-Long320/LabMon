#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${LABMON_INSTALL_DIR:-$(cd -- "$SCRIPT_DIR/.." && pwd)}"
ENV_DIR="${LABMON_ENV_DIR:-/etc/labmon}"
ENV_FILE="${LABMON_ENV_FILE:-$ENV_DIR/labmon.env}"
SERVICE_FILE="${LABMON_SERVICE_FILE:-/etc/systemd/system/labmon.service}"
SERVICE_NAME="${LABMON_SERVICE_NAME:-labmon}"
LABMON_HOST="${LABMON_HOST:-0.0.0.0}"
LABMON_PORT="${LABMON_PORT:-8765}"

log() {
  printf '[labmon] %s\n' "$*"
}

fail() {
  printf '[labmon] error: %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
  fi
}

find_uv() {
  if command -v uv >/dev/null 2>&1; then
    command -v uv
    return
  fi
  if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
    sudo -u "$SUDO_USER" sh -lc 'command -v uv' 2>/dev/null || true
  fi
}

run_as_owner() {
  if [ "$(id -u)" -eq 0 ] && [ -n "${INSTALL_OWNER:-}" ] && [ "$INSTALL_OWNER" != "root" ]; then
    sudo -u "$INSTALL_OWNER" "$@"
  else
    "$@"
  fi
}

generate_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
    return
  fi
  python3 -c 'import secrets; print(secrets.token_hex(32))'
}

[ -d "$INSTALL_DIR" ] || fail "install directory does not exist: $INSTALL_DIR"
[ -f "$INSTALL_DIR/labmon/app.py" ] || fail "run this script from a LabMon checkout"
case "$INSTALL_DIR" in
  *" "*) fail "install directory cannot contain spaces: $INSTALL_DIR" ;;
esac

need_cmd git
need_cmd systemctl
UV_BIN="${UV_BIN:-$(find_uv)}"
[ -n "$UV_BIN" ] || fail "uv is required. Install uv first, then rerun this script."

INSTALL_OWNER="${LABMON_INSTALL_OWNER:-${SUDO_USER:-}}"
if [ "$(id -u)" -eq 0 ] && [ -n "$INSTALL_OWNER" ] && [ "$INSTALL_OWNER" != "root" ]; then
  log "setting $INSTALL_DIR owner to $INSTALL_OWNER"
  as_root chown -R "$INSTALL_OWNER:$(id -gn "$INSTALL_OWNER")" "$INSTALL_DIR"
fi

log "syncing Python environment with uv"
(
  cd "$INSTALL_DIR"
  run_as_owner env UV_CACHE_DIR="${UV_CACHE_DIR:-$INSTALL_DIR/.uv-cache}" "$UV_BIN" sync --no-dev
)

log "writing environment file"
as_root mkdir -p "$ENV_DIR"
if [ ! -f "$ENV_FILE" ]; then
  tmp_env="$(mktemp)"
  secret="$(generate_secret)"
  cat > "$tmp_env" <<EOF
LABMON_HOST=$LABMON_HOST
LABMON_PORT=$LABMON_PORT
LABMON_LOG_ROOTS=/home/*/runs,/home/*/logs,/data/runs,/data/logs
LABMON_HISTORY_SECONDS=3600
LABMON_HISTORY_INTERVAL_SECONDS=1
LABMON_AUTH=1
LABMON_USERS_FILE=$INSTALL_DIR/labmon-users.json
LABMON_AUTH_SECRET=$secret
LABMON_AUTH_SESSION_HOURS=168
LABMON_AUTH_COOKIE_SECURE=0
EOF
  as_root install -m 600 "$tmp_env" "$ENV_FILE"
  rm -f "$tmp_env"
else
  log "environment file already exists, keeping it: $ENV_FILE"
fi

log "installing systemd service"
tmp_service="$(mktemp)"
sed \
  -e "s#^WorkingDirectory=.*#WorkingDirectory=$INSTALL_DIR#" \
  -e "s#^EnvironmentFile=.*#EnvironmentFile=$ENV_FILE#" \
  -e "s#^ExecStart=.*#ExecStart=$INSTALL_DIR/.venv/bin/uvicorn labmon.app:app --host \${LABMON_HOST} --port \${LABMON_PORT}#" \
  "$INSTALL_DIR/deploy/labmon.service" > "$tmp_service"
as_root install -m 644 "$tmp_service" "$SERVICE_FILE"
rm -f "$tmp_service"

log "starting $SERVICE_NAME"
as_root systemctl daemon-reload
as_root systemctl enable --now "$SERVICE_NAME"
as_root systemctl restart "$SERVICE_NAME"

if [ -n "${LABMON_ADMIN_USER:-}" ]; then
  log "creating LabMon user: $LABMON_ADMIN_USER"
  run_as_owner env LABMON_USERS_FILE="$INSTALL_DIR/labmon-users.json" "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/scripts/manage_users.py" add "$LABMON_ADMIN_USER"
else
  log "create a LabMon user with:"
  log "  sudo env LABMON_USERS_FILE=$INSTALL_DIR/labmon-users.json $INSTALL_DIR/.venv/bin/python $INSTALL_DIR/scripts/manage_users.py add alice"
fi

log "done"
log "status: sudo systemctl status $SERVICE_NAME"
log "logs:   sudo journalctl -u $SERVICE_NAME -f"
