#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import requests
import websockets

DEBUG_HOST = os.getenv("CHROME_DEBUG_HOST", "127.0.0.1")
DEBUG_PORT = int(os.getenv("CHROME_DEBUG_PORT", "9223"))
CASTING_URL_SUBSTRING = "horizon.meta.com/casting"

CENTER_X_RATIO = float(os.getenv("QUEST_CENTER_X_RATIO", "0.5"))
CENTER_Y_RATIO = float(os.getenv("QUEST_CENTER_Y_RATIO", "0.5"))

VOLUME_BUTTON_X_RATIO = float(os.getenv("QUEST_VOLUME_BUTTON_X_RATIO", "0.9568"))
VOLUME_BUTTON_Y_RATIO = float(os.getenv("QUEST_VOLUME_BUTTON_Y_RATIO", "0.9796"))

VOLUME_SLIDER_X_RATIO = float(os.getenv("QUEST_VOLUME_SLIDER_X_RATIO", "0.9573"))
VOLUME_SLIDER_TOP_Y_RATIO = float(os.getenv("QUEST_VOLUME_SLIDER_TOP_Y_RATIO", "0.9065"))


def get_target_ws_url() -> str:
    response = requests.get(
        f"http://{DEBUG_HOST}:{DEBUG_PORT}/json/list",
        timeout=2,
    )
    response.raise_for_status()

    for target in response.json():
        url = str(target.get("url", ""))
        ws_url = target.get("webSocketDebuggerUrl")
        if ws_url and CASTING_URL_SUBSTRING in url:
            return str(ws_url)

    raise RuntimeError("Quest casting target not found")


async def cdp_call(ws, method: str, params: dict | None = None):
    message_id = int(time.time() * 1000) % 1_000_000
    payload = {
        "id": message_id,
        "method": method,
        "params": params or {},
    }
    await ws.send(json.dumps(payload))

    while True:
        raw_message = await ws.recv()
        message = json.loads(raw_message)

        if message.get("id") != message_id:
            continue

        if "error" in message:
            raise RuntimeError(f"CDP error for {method}: {message['error']}")

        return message.get("result", {})


async def eval_js(ws, expression: str):
    result = await cdp_call(
        ws,
        "Runtime.evaluate",
        {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        },
    )
    remote = result.get("result", {})
    return remote.get("value")


async def mouse_move(ws, x: int, y: int):
    await cdp_call(ws, "Input.dispatchMouseEvent", {
        "type": "mouseMoved",
        "x": x,
        "y": y,
        "button": "none",
    })


async def click(ws, x: int, y: int):
    await cdp_call(ws, "Input.dispatchMouseEvent", {
        "type": "mousePressed",
        "x": x,
        "y": y,
        "button": "left",
        "clickCount": 1,
    })
    await cdp_call(ws, "Input.dispatchMouseEvent", {
        "type": "mouseReleased",
        "x": x,
        "y": y,
        "button": "left",
        "clickCount": 1,
    })


async def main_async() -> int:
    ws_url = get_target_ws_url()

    async with websockets.connect(ws_url) as ws:
        await cdp_call(ws, "Runtime.enable")
        await cdp_call(ws, "Page.enable")

        viewport = await eval_js(ws, """
(() => ({
  width: window.innerWidth,
  height: window.innerHeight
}))()
""")

        if not viewport or not viewport.get("width") or not viewport.get("height"):
            raise RuntimeError("Could not determine viewport size")

        width = int(viewport["width"])
        height = int(viewport["height"])

        center_x = int(width * CENTER_X_RATIO)
        center_y = int(height * CENTER_Y_RATIO)

        volume_button_x = int(width * VOLUME_BUTTON_X_RATIO)
        volume_button_y = int(height * VOLUME_BUTTON_Y_RATIO)

        slider_x = int(width * VOLUME_SLIDER_X_RATIO)
        slider_top_y = int(height * VOLUME_SLIDER_TOP_Y_RATIO)

        print({
            "viewport": {"width": width, "height": height},
            "center": {"x": center_x, "y": center_y},
            "volume_button": {"x": volume_button_x, "y": volume_button_y},
            "slider_top": {"x": slider_x, "y": slider_top_y},
        })

        # Show controls
        await click(ws, center_x, center_y)
        await asyncio.sleep(0.5)

        # Open volume control / unmute
        await click(ws, volume_button_x, volume_button_y)
        await asyncio.sleep(0.4)

        # Set volume to maximum by clicking the top of the slider
        await click(ws, slider_x, slider_top_y)
        await asyncio.sleep(0.4)

        # Move pointer outside viewport so the player loses hover state
        await mouse_move(ws, width + 200, height // 2)
        await asyncio.sleep(0.2)

        # Force mouseleave/mouseout/blur and hide cursor as fallback
        await eval_js(ws, """
(() => {
  const video = document.querySelector("video");
  const targets = [video, document.body, document.documentElement].filter(Boolean);

  for (const target of targets) {
    target.dispatchEvent(new MouseEvent("mouseout", { bubbles: true }));
    target.dispatchEvent(new MouseEvent("mouseleave", { bubbles: true }));
  }

  if (document.activeElement && typeof document.activeElement.blur === "function") {
    document.activeElement.blur();
  }

  // Fallback: hide cursor and common player overlays if they linger
  let style = document.getElementById("cg-player-cleanup-style");
  if (!style) {
    style = document.createElement("style");
    style.id = "cg-player-cleanup-style";
    style.textContent = `
      html, body, video, * {
        cursor: none !important;
      }

      [role="slider"],
      [aria-label*="volume" i],
      [class*="control" i],
      [class*="controls" i],
      [class*="overlay" i],
      [class*="player" i] button,
      [class*="player" i] [role="button"] {
        transition: opacity 0.15s linear !important;
      }
    `;
    document.documentElement.appendChild(style);
  }

  return true;
})()
""")

        # Give the page a moment to auto-hide controls
        await asyncio.sleep(1.2)

        return 0


def main() -> int:
    try:
        return asyncio.run(main_async())
    except Exception as exc:
        print(f"quest_audio_max error: {exc!r}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
