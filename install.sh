#!/usr/bin/env bash
set -euo pipefail

APP_NAME="cg-overlay-box"
APP_DIR="${APP_DIR:-$HOME/$APP_NAME}"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
ENV_DIR="${HOME}/.config/cg-overlay-box"
ENV_FILE="${ENV_DIR}/overlay.env"
STATE_DIR="${HOME}/.local/state/cg-overlay-box"

REPO_SYSTEMD_DIR="${APP_DIR}/systemd-user"
REQUIREMENTS_FILE="${APP_DIR}/requirements.txt"
ENV_EXAMPLE_FILE="${APP_DIR}/.env.example"

log() {
  printf '\n[%s] %s\n' "$APP_NAME" "$*"
}

fail() {
  printf '\n[%s] ERROR: %s\n' "$APP_NAME" "$*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

assert_repo_layout() {
  [[ -d "$APP_DIR/backend" ]] || fail "Missing directory: $APP_DIR/backend"
  [[ -d "$APP_DIR/scripts" ]] || fail "Missing directory: $APP_DIR/scripts"
  [[ -d "$APP_DIR/web" ]] || fail "Missing directory: $APP_DIR/web"
  [[ -d "$REPO_SYSTEMD_DIR" ]] || fail "Missing directory: $REPO_SYSTEMD_DIR"
  [[ -f "$APP_DIR/backend/main.py" ]] || fail "Missing file: $APP_DIR/backend/main.py"
  [[ -f "$REQUIREMENTS_FILE" ]] || fail "Missing file: $REQUIREMENTS_FILE"
}

install_packages() {
  log "Installing OS packages"
  sudo apt update
  sudo apt install -y \
    python3 \
    python3-venv \
    python3-pip \
    chromium \
    unclutter \
    xdotool \
    curl
}

ensure_dirs() {
  log "Creating runtime directories"
  mkdir -p "$SYSTEMD_USER_DIR"
  mkdir -p "$ENV_DIR"
  mkdir -p "$STATE_DIR"
}

setup_venv() {
  log "Setting up Python virtual environment"
  if [[ ! -d "$APP_DIR/.venv" ]]; then
    python3 -m venv "$APP_DIR/.venv"
  fi

  "$APP_DIR/.venv/bin/pip" install --upgrade pip
  "$APP_DIR/.venv/bin/pip" install -r "$REQUIREMENTS_FILE"
}

install_env_file() {
  log "Installing environment file"
  if [[ -f "$ENV_FILE" ]]; then
    log "Keeping existing env file: $ENV_FILE"
    return
  fi

  if [[ -f "$ENV_EXAMPLE_FILE" ]]; then
    cp "$ENV_EXAMPLE_FILE" "$ENV_FILE"
    log "Created $ENV_FILE from .env.example"
    log "Edit this file before using the system:"
    printf '  nano %s\n' "$ENV_FILE"
  else
    cat > "$ENV_FILE" <<'EOF'
OVERLAY_TOKEN=change_me
OVERLAY_PORT=8000
ATEM_IP=192.168.1.50
ATEM_INPUT=4
CHROME_DEBUG_HOST=127.0.0.1
CHROME_DEBUG_PORT=9223
EOF
    log "Created default $ENV_FILE"
    log "Edit this file before using the system:"
    printf '  nano %s\n' "$ENV_FILE"
  fi
}

install_systemd_units() {
  log "Installing user-level systemd units"

  local units=(
    "overlay-api.service"
    "overlay-chromium-overlay.service"
    "overlay-chromium-quest.service"
    "overlay-watchdog.service"
    "overlay-watchdog.timer"
  )

  for unit in "${units[@]}"; do
    [[ -f "$REPO_SYSTEMD_DIR/$unit" ]] || fail "Missing unit file: $REPO_SYSTEMD_DIR/$unit"
    cp "$REPO_SYSTEMD_DIR/$unit" "$SYSTEMD_USER_DIR/$unit"
  done
}

enable_user_services() {
  log "Reloading systemd user daemon"
  systemctl --user daemon-reload

  log "Enabling lingering for user services"
  sudo loginctl enable-linger "$(whoami)"

  log "Enabling services"
  systemctl --user enable overlay-api.service
  systemctl --user enable overlay-chromium-overlay.service
  systemctl --user enable overlay-chromium-quest.service
  systemctl --user enable overlay-watchdog.timer
  systemctl --user enable unclutter.service || true
}

restart_user_services() {
  log "Restarting services"
  systemctl --user restart overlay-api.service
  systemctl --user restart overlay-chromium-quest.service

  # Overlay is intentionally restarted rather than started:
  # if Quest is on screen, restart guarantees overlay returns to top.
  systemctl --user restart overlay-chromium-overlay.service || true

  systemctl --user restart overlay-watchdog.timer || true
  systemctl --user restart unclutter.service || true
}

make_scripts_executable() {
  log "Marking scripts executable"
  chmod +x "$APP_DIR/scripts/"*.sh || true
  chmod +x "$APP_DIR/scripts/"*.py || true
}

print_post_install_notes() {
  cat <<EOF

[$APP_NAME] Install complete.

Next checks:
  1. Confirm env file:
     nano $ENV_FILE

  2. Check services:
     systemctl --user status overlay-api.service --no-pager
     systemctl --user status overlay-chromium-overlay.service --no-pager
     systemctl --user status overlay-chromium-quest.service --no-pager
     systemctl --user status unclutter.service --no-pager

  3. Check API:
     curl http://127.0.0.1:8000/health

  4. Check X11 session:
     echo \$XDG_SESSION_TYPE

  5. Test Quest workflow:
     $APP_DIR/scripts/quest_prepare_and_take.sh

Stream Deck main URL:
  http://<PI_IP>:8000/api/view/quest_prepare_and_take?token=<OVERLAY_TOKEN>

EOF
}

main() {
  need_cmd python3
  need_cmd systemctl
  need_cmd sudo

  assert_repo_layout
  install_packages
  ensure_dirs
  setup_venv
  install_env_file
  install_systemd_units
  make_scripts_executable
  enable_user_services
  restart_user_services
  print_post_install_notes
}

main "$@"