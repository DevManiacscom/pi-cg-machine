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

# Screen-relative coordinates, calibrated for your setup.
FULLSCREEN_X_RATIO = float(os.getenv("QUEST_FULLSCREEN_X_RATIO", "0.83"))
FULLSCREEN_Y_RATIO = float(os.getenv("QUEST_FULLSCREEN_Y_RATIO", "0.782"))


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

        center_x = width // 2
        center_y = height // 2

        fullscreen_x = int(width * FULLSCREEN_X_RATIO)
        fullscreen_y = int(height * FULLSCREEN_Y_RATIO)

        print({
            "viewport": {"width": width, "height": height},
            "center": {"x": center_x, "y": center_y},
            "fullscreen": {"x": fullscreen_x, "y": fullscreen_y},
        })

        # Reveal controls
        await click(ws, center_x, center_y)
        await asyncio.sleep(0.8)

        # Click fullscreen button
        await click(ws, fullscreen_x, fullscreen_y)
        await asyncio.sleep(0.5)

        return 0


def main() -> int:
    try:
        return asyncio.run(main_async())
    except Exception as exc:
        print(f"quest_fullscreen error: {exc!r}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
