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
  overlay-api.service
  overlay-chromium-overlay.service
  overlay-chromium-quest.service
  overlay-watchdog.service
  overlay-watchdog.timer
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

# Use system-provided unclutter service if present
if systemctl --user list-unit-files | grep -q '^unclutter\.service'; then
  systemctl --user enable unclutter.service || true
fi

# -----------------------------
# Start services
# -----------------------------
echo "[+] Starting services"

systemctl --user restart overlay-api.service || true
systemctl --user restart overlay-chromium-quest.service || true
systemctl --user restart overlay-chromium-overlay.service || true
systemctl --user restart overlay-watchdog.timer || true
systemctl --user restart unclutter.service || true

# -----------------------------
# Ensure linger
# -----------------------------
if command -v loginctl >/dev/null 2>&1; then
  USER_NAME="$(id -un)"
  echo "[+] Enabling linger for $USER_NAME"
  sudo loginctl enable-linger "$USER_NAME" || true
fi

# -----------------------------
# Reminder about console blanking
# -----------------------------
echo
echo "[!] Make sure /boot/firmware/cmdline.txt contains: consoleblank=0"
echo "    (same single line, no line breaks)"

# -----------------------------
# Done
# -----------------------------
echo "[+] Install complete"

echo
echo "Useful commands:"
echo "  systemctl --user status overlay-api.service --no-pager"
echo "  systemctl --user status overlay-chromium-overlay.service --no-pager"
echo "  systemctl --user status overlay-chromium-quest.service --no-pager"
echo "  systemctl --user status overlay-watchdog.timer --no-pager"
echo "  DISPLAY=:0 XAUTHORITY=\$HOME/.Xauthority xset q"
echo