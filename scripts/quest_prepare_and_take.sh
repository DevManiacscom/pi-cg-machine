#!/usr/bin/env bash
set -euo pipefail

DISPLAY_VALUE="${DISPLAY:-:0}"
XDG_RUNTIME_DIR_VALUE="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
XAUTHORITY_VALUE="${XAUTHORITY:-$HOME/.Xauthority}"

export DISPLAY="$DISPLAY_VALUE"
export XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR_VALUE"
export XAUTHORITY="$XAUTHORITY_VALUE"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$HOME/.config/cg-overlay-box/overlay.env}"
LOCKFILE="${LOCKFILE:-/tmp/quest_prepare.lock}"

QUEST_DETECT_SCRIPT="${QUEST_DETECT_SCRIPT:-$SCRIPT_DIR/quest_detect_ready.py}"
QUEST_FULLSCREEN_SCRIPT="${QUEST_FULLSCREEN_SCRIPT:-$SCRIPT_DIR/quest_fullscreen.py}"
QUEST_AUDIO_MAX_SCRIPT="${QUEST_AUDIO_MAX_SCRIPT:-$SCRIPT_DIR/quest_audio_max.py}"
SWITCH_VIEW_SCRIPT="${SWITCH_VIEW_SCRIPT:-$SCRIPT_DIR/switch_view.sh}"
ATEM_TAKE_SCRIPT="${ATEM_TAKE_SCRIPT:-$SCRIPT_DIR/atem_take_pi.py}"
PYTHON_BIN="${PYTHON_BIN:-$HOME/cg-overlay-box/.venv/bin/python}"

MAX_ATTEMPTS="${QUEST_PREPARE_MAX_ATTEMPTS:-120}"
POLL_INTERVAL_SEC="${QUEST_PREPARE_POLL_INTERVAL_SEC:-1}"

log() {
  printf '[quest_prepare_and_take] %s\n' "$*" >&2
}

cleanup() {
  rm -f "$LOCKFILE"
}

if [[ -f "$LOCKFILE" ]]; then
  log "Another Quest prepare process is already running"
  exit 0
fi

touch "$LOCKFILE"
trap cleanup EXIT

log "Waiting for Quest casting stream"

for (( i=1; i<=MAX_ATTEMPTS; i++ )); do
  if "$PYTHON_BIN" "$QUEST_DETECT_SCRIPT"; then
    log "Quest casting detected, preparing output"

    "$PYTHON_BIN" "$QUEST_FULLSCREEN_SCRIPT"
    sleep 0.3

    "$PYTHON_BIN" "$QUEST_AUDIO_MAX_SCRIPT"
    sleep 0.8

    log "Switching visible output to Quest"
    "$SWITCH_VIEW_SCRIPT" quest
    sleep 0.3

    if [[ -f "$ENV_FILE" ]]; then
      set -a
      # shellcheck disable=SC1090
      source "$ENV_FILE"
      set +a
    fi

    log "Taking ATEM to Pi input"
    "$PYTHON_BIN" "$ATEM_TAKE_SCRIPT"

    log "Quest output is ready"
    exit 0
  fi

  sleep "$POLL_INTERVAL_SEC"
done

log "Quest casting was not detected in time"
exit 1