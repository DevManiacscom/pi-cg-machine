#!/usr/bin/env bash
set -euo pipefail

DISPLAY_VALUE="${DISPLAY:-:0}"
XDG_RUNTIME_DIR_VALUE="${XDG_RUNTIME_DIR:-/run/user/1000}"
XAUTHORITY_VALUE="${XAUTHORITY:-$HOME/.Xauthority}"

export DISPLAY="$DISPLAY_VALUE"
export XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR_VALUE"
export XAUTHORITY="$XAUTHORITY_VALUE"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-/etc/overlay-box/overlay.env}"
LOCKFILE="${LOCKFILE:-/tmp/quest_prepare.lock}"

SWITCH_VIEW_SCRIPT="${SWITCH_VIEW_SCRIPT:-$SCRIPT_DIR/switch_view.sh}"
QUEST_DETECT_SCRIPT="${QUEST_DETECT_SCRIPT:-$SCRIPT_DIR/quest_detect_ready.py}"
QUEST_FULLSCREEN_SCRIPT="${QUEST_FULLSCREEN_SCRIPT:-$SCRIPT_DIR/quest_fullscreen.sh}"
QUEST_AUDIO_MAX_SCRIPT="${QUEST_AUDIO_MAX_SCRIPT:-$SCRIPT_DIR/quest_audio_max.sh}"
ATEM_TAKE_SCRIPT="${ATEM_TAKE_SCRIPT:-$SCRIPT_DIR/atem_take_pi.py}"

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

log "Switching visible window to Quest"
"$SWITCH_VIEW_SCRIPT" quest
sleep 1

log "Waiting for Quest casting stream"

for (( i=1; i<=MAX_ATTEMPTS; i++ )); do
  if "$QUEST_DETECT_SCRIPT"; then
    log "Quest casting detected, preparing output"

    "$QUEST_FULLSCREEN_SCRIPT" || true
    sleep 1

    "$QUEST_AUDIO_MAX_SCRIPT" || true
    sleep 1

    xdotool mousemove 100 100 || true
    sleep 0.5

    if [[ -f "$ENV_FILE" ]]; then
      # shellcheck disable=SC1090
      set -a
      source "$ENV_FILE"
      set +a
    fi

    log "Taking ATEM program to Pi input"
    "$ATEM_TAKE_SCRIPT"

    log "Quest output is ready"
    exit 0
  fi

  sleep "$POLL_INTERVAL_SEC"
done

log "Quest casting was not detected in time"
exit 1