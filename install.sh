#!/usr/bin/env bash
set -euo pipefail

echo "[+] CG Overlay Box install start"

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
VENV_DIR="$APP_DIR/.venv"

echo "[+] App dir: $APP_DIR"

# -----------------------------
# Python venv
# -----------------------------
if [ ! -d "$VENV_DIR" ]; then
  echo "[+] Creating virtualenv"
  python3 -m venv "$VENV_DIR"
fi

echo "[+] Activating virtualenv"
source "$VENV_DIR/bin/activate"

echo "[+] Installing Python deps"
pip install --upgrade pip
pip install -r "$APP_DIR/requirements.txt"

# -----------------------------
# Ensure systemd user dir
# -----------------------------
mkdir -p "$SYSTEMD_USER_DIR"

# -----------------------------
# Install user services
# -----------------------------
echo "[+] Installing systemd user services"

SERVICES=(
  overlay-backend.service
  overlay-chromium-overlay.service
  overlay-chromium-quest.service
  disable-screen-blanking.service
)

for svc in "${SERVICES[@]}"; do
  SRC="$APP_DIR/systemd-user/$svc"
  DST="$SYSTEMD_USER_DIR/$svc"

  if [ -f "$SRC" ]; then
    echo "  -> $svc"
    cp "$SRC" "$DST"
  else
    echo "  !! missing $SRC"
  fi
done

# -----------------------------
# Reload systemd
# -----------------------------
echo "[+] Reloading systemd user daemon"
systemctl --user daemon-reload

# -----------------------------
# Enable services
# -----------------------------
echo "[+] Enabling services"

for svc in "${SERVICES[@]}"; do
  if [ -f "$SYSTEMD_USER_DIR/$svc" ]; then
    systemctl --user enable "$svc"
  fi
done

# -----------------------------
# Start services
# -----------------------------
echo "[+] Starting services"

for svc in "${SERVICES[@]}"; do
  if [ -f "$SYSTEMD_USER_DIR/$svc" ]; then
    systemctl --user restart "$svc" || true
  fi
done

# -----------------------------
# Ensure linger (important for kiosk setups)
# -----------------------------
if command -v loginctl >/dev/null 2>&1; then
  USER_NAME="$(id -un)"
  echo "[+] Enabling linger for $USER_NAME"
  sudo loginctl enable-linger "$USER_NAME" || true
fi

# -----------------------------
# Done
# -----------------------------
echo "[+] Install complete"

echo
echo "Useful commands:"
echo "  systemctl --user status overlay-backend.service"
echo "  systemctl --user status overlay-chromium-overlay.service"
echo "  systemctl --user status overlay-chromium-quest.service"
echo "  systemctl --user status disable-screen-blanking.service"
echo