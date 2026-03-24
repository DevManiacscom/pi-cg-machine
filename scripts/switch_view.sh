#!/usr/bin/env bash
set -euo pipefail

VIEW="${1:-}"

if [[ -z "$VIEW" ]]; then
  echo "Usage: $0 <overlay|quest>" >&2
  exit 2
fi

DISPLAY_VALUE="${DISPLAY:-:0}"
XDG_RUNTIME_DIR_VALUE="${XDG_RUNTIME_DIR:-/run/user/1000}"
XAUTHORITY_VALUE="${XAUTHORITY:-$HOME/.Xauthority}"

export DISPLAY="$DISPLAY_VALUE"
export XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR_VALUE"
export XAUTHORITY="$XAUTHORITY_VALUE"

OVERLAY_WINDOW_PATTERN="${OVERLAY_WINDOW_PATTERN:-127\.0\.0\.1\.Chromium}"
QUEST_WINDOW_PATTERN="${QUEST_WINDOW_PATTERN:-www\.oculus\.com__casting\.Chromium}"

get_window_id() {
  local pattern="$1"
  wmctrl -lx | awk -v pattern="$pattern" '
    $0 ~ pattern { print $1; exit }
  '
}

case "$VIEW" in
  overlay)
    WINDOW_ID="$(get_window_id "$OVERLAY_WINDOW_PATTERN")"
    ;;
  quest)
    WINDOW_ID="$(get_window_id "$QUEST_WINDOW_PATTERN")"
    ;;
  *)
    echo "Unknown view: $VIEW" >&2
    exit 2
    ;;
esac

if [[ -z "${WINDOW_ID:-}" ]]; then
  echo "Target window not found for view: $VIEW" >&2
  exit 1
fi

wmctrl -ia "$WINDOW_ID"