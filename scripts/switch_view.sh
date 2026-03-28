#!/usr/bin/env bash
set -euo pipefail

VIEW="${1:-}"

if [[ -z "$VIEW" ]]; then
  echo "Usage: $0 <overlay|quest>" >&2
  exit 2
fi

case "$VIEW" in
  overlay)
    systemctl --user restart overlay-chromium-overlay.service
    ;;
  quest)
    systemctl --user stop overlay-chromium-overlay.service
    ;;
  *)
    echo "Unknown view: $VIEW" >&2
    exit 2
    ;;
esac
