#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import Any

import requests
import websockets

DEBUG_HOST = os.getenv("CHROME_DEBUG_HOST", "127.0.0.1")
DEBUG_PORT = int(os.getenv("CHROME_DEBUG_PORT", "9223"))

CASTING_URL_SUBSTRING = "oculus.com/casting"
CASTING_TITLE_SUBSTRING = "Casting | Meta Horizon"


def get_target_ws_url() -> str:
    response = requests.get(
        f"http://{DEBUG_HOST}:{DEBUG_PORT}/json/list",
        timeout=2,
    )
    response.raise_for_status()

    targets = response.json()
    if not isinstance(targets, list):
        raise RuntimeError("Unexpected Chrome DevTools response")

    for target in targets:
        url = str(target.get("url", ""))
        title = str(target.get("title", ""))
        ws_url = target.get("webSocketDebuggerUrl")

        if not ws_url:
            continue

        if CASTING_URL_SUBSTRING in url or CASTING_TITLE_SUBSTRING in title:
            return str(ws_url)

    raise RuntimeError("Quest casting target not found")


async def evaluate_expression(
    ws: websockets.WebSocketClientProtocol,
    expression: str,
) -> Any:
    message_id = int(time.time() * 1000) % 1_000_000

    payload = {
        "id": message_id,
        "method": "Runtime.evaluate",
        "params": {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        },
    }

    await ws.send(json.dumps(payload))

    while True:
        raw_message = await ws.recv()
        message = json.loads(raw_message)

        if message.get("id") != message_id:
            continue

        result = message.get("result", {}).get("result", {})
        if "value" in result:
            return result["value"]

        raise RuntimeError(f"Unexpected CDP response: {message}")


async def detect_casting_state() -> tuple[dict[str, Any], dict[str, Any], bool]:
    ws_url = get_target_ws_url()

    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))

        js_expression = r"""
(() => {
  const video = document.querySelector("video");

  if (!video) {
    return {
      hasVideo: false,
      ready: false,
      paused: null,
      currentTime: null,
      videoWidth: 0,
      videoHeight: 0,
      muted: null,
      volume: null
    };
  }

  return {
    hasVideo: true,
    ready: video.readyState >= 2,
    paused: video.paused,
    currentTime: video.currentTime,
    videoWidth: video.videoWidth || 0,
    videoHeight: video.videoHeight || 0,
    muted: video.muted,
    volume: video.volume
  };
})()
"""

        state_1 = await evaluate_expression(ws, js_expression)
        await asyncio.sleep(0.8)
        state_2 = await evaluate_expression(ws, js_expression)

        has_video = bool(state_2.get("hasVideo"))
        has_size = (
            int(state_2.get("videoWidth", 0)) > 0
            and int(state_2.get("videoHeight", 0)) > 0
        )
        ready = bool(state_2.get("ready"))
        not_paused = state_2.get("paused") is False

        current_time_1 = state_1.get("currentTime")
        current_time_2 = state_2.get("currentTime")
        current_time_moves = (
            isinstance(current_time_1, (int, float))
            and isinstance(current_time_2, (int, float))
            and current_time_2 > current_time_1
        )

        is_ready = has_video and has_size and ready and (not_paused or current_time_moves)

        return state_1, state_2, is_ready


def main() -> int:
    try:
        state_1, state_2, is_ready = asyncio.run(detect_casting_state())

        print(f"state1={state_1}")
        print(f"state2={state_2}")

        return 0 if is_ready else 1

    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130

    except Exception as exc:
        print(f"quest_detect_ready error: {exc!r}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())