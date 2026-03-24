#!/usr/bin/env bash
set -euo pipefail

DISPLAY_VALUE="${DISPLAY:-:0}"
XDG_RUNTIME_DIR_VALUE="${XDG_RUNTIME_DIR:-/run/user/1000}"
XAUTHORITY_VALUE="${XAUTHORITY:-$HOME/.Xauthority}"

export DISPLAY="$DISPLAY_VALUE"
export XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR_VALUE"
export XAUTHORITY="$XAUTHORITY_VALUE"

QUEST_WINDOW_PATTERN="${QUEST_WINDOW_PATTERN:-www\.oculus\.com__casting\.Chromium}"

# Volume button absolute coordinates.
QUEST_VOLUME_BUTTON_X="${QUEST_VOLUME_BUTTON_X:-1837}"
QUEST_VOLUME_BUTTON_Y="${QUEST_VOLUME_BUTTON_Y:-1058}"

# Volume slider drag coordinates.
QUEST_VOLUME_SLIDER_BOTTOM_X="${QUEST_VOLUME_SLIDER_BOTTOM_X:-1838}"
QUEST_VOLUME_SLIDER_BOTTOM_Y="${QUEST_VOLUME_SLIDER_BOTTOM_Y:-1033}"
QUEST_VOLUME_SLIDER_TOP_X="${QUEST_VOLUME_SLIDER_TOP_X:-1838}"
QUEST_VOLUME_SLIDER_TOP_Y="${QUEST_VOLUME_SLIDER_TOP_Y:-979}"

# Cursor parking position after the interaction is complete.
QUEST_CURSOR_PARK_Y="${QUEST_CURSOR_PARK_Y:-120}"

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

  # Click the center of the player to reveal controls.
  local center_x=$((X + WIDTH / 2))
  local center_y=$((Y + HEIGHT / 2))

  xdotool mousemove "$center_x" "$center_y"
  sleep 0.2
  xdotool click 1
  sleep 1

  # Open the volume control.
  xdotool mousemove "$QUEST_VOLUME_BUTTON_X" "$QUEST_VOLUME_BUTTON_Y"
  sleep 0.2
  xdotool click 1
  sleep 0.5

  # Drag the volume slider to maximum.
  xdotool mousemove "$QUEST_VOLUME_SLIDER_BOTTOM_X" "$QUEST_VOLUME_SLIDER_BOTTOM_Y"
  sleep 0.2
  xdotool mousedown 1
  sleep 0.2
  xdotool mousemove --sync "$QUEST_VOLUME_SLIDER_TOP_X" "$QUEST_VOLUME_SLIDER_TOP_Y"
  sleep 0.2
  xdotool mouseup 1
  sleep 0.5

  # Move the cursor away so the controls can fade out.
  xdotool mousemove "$center_x" "$QUEST_CURSOR_PARK_Y"
}

main "$@"