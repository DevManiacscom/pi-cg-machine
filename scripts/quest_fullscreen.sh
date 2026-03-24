#!/usr/bin/env bash
set -euo pipefail

DISPLAY_VALUE="${DISPLAY:-:0}"
XDG_RUNTIME_DIR_VALUE="${XDG_RUNTIME_DIR:-/run/user/1000}"
XAUTHORITY_VALUE="${XAUTHORITY:-$HOME/.Xauthority}"

export DISPLAY="$DISPLAY_VALUE"
export XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR_VALUE"
export XAUTHORITY="$XAUTHORITY_VALUE"

QUEST_WINDOW_PATTERN="${QUEST_WINDOW_PATTERN:-www\.oculus\.com__casting\.Chromium}"

# Fullscreen button position relative to the Quest window size.
# These defaults were calibrated for the Meta casting player layout.
QUEST_FULLSCREEN_X_RATIO_NUM="${QUEST_FULLSCREEN_X_RATIO_NUM:-830}"
QUEST_FULLSCREEN_X_RATIO_DEN="${QUEST_FULLSCREEN_X_RATIO_DEN:-1000}"
QUEST_FULLSCREEN_Y_RATIO_NUM="${QUEST_FULLSCREEN_Y_RATIO_NUM:-782}"
QUEST_FULLSCREEN_Y_RATIO_DEN="${QUEST_FULLSCREEN_Y_RATIO_DEN:-1000}"

get_window_id() {
  wmctrl -lx | awk -v pattern="$QUEST_WINDOW_PATTERN" '
    $0 ~ pattern { print $1; exit }
  '
}

main() {
  local window_id
  window_id="$(get_window_id)"

  if [[ -z "$window_id" ]]; then
    echo "Quest casting window not found" >&2
    return 1
  fi

  # Bring the Quest window to the foreground.
  wmctrl -ia "$window_id"
  sleep 1

  xdotool windowactivate --sync "$window_id"
  sleep 0.7

  # Read window geometry from X11.
  local geometry
  geometry="$(xdotool getwindowgeometry --shell "$window_id")"
  eval "$geometry"

  # Click the center of the player area to reveal controls.
  local center_x=$((X + WIDTH / 2))
  local center_y=$((Y + HEIGHT / 2))

  xdotool mousemove "$center_x" "$center_y"
  sleep 0.2
  xdotool click 1
  sleep 1

  # Click the fullscreen button based on relative window coordinates.
  local fullscreen_x=$((X + WIDTH * QUEST_FULLSCREEN_X_RATIO_NUM / QUEST_FULLSCREEN_X_RATIO_DEN))
  local fullscreen_y=$((Y + HEIGHT * QUEST_FULLSCREEN_Y_RATIO_NUM / QUEST_FULLSCREEN_Y_RATIO_DEN))

  xdotool mousemove "$fullscreen_x" "$fullscreen_y"
  sleep 0.2
  xdotool click 1
}

main "$@"