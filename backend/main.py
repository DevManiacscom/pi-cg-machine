from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

APP_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = APP_ROOT / "scripts"
DATA_DIR = Path(os.getenv("CG_OVERLAY_DATA_DIR", "/var/lib/overlay-box"))

TOKEN = os.getenv("OVERLAY_TOKEN")
if not TOKEN:
    raise RuntimeError("OVERLAY_TOKEN is not set")

OVERLAY_PORT = int(os.getenv("OVERLAY_PORT", "8000"))

KOFI_POLL_URL = os.getenv("KOFI_POLL_URL")
KOFI_RELAY_TOKEN = os.getenv("KOFI_RELAY_TOKEN")
KOFI_SINCE_FILE = Path(
    os.getenv("KOFI_SINCE_FILE", str(DATA_DIR / "kofi_since.txt"))
)

HEARTBEAT_INTERVAL_SEC = 2.0
KOFI_POLL_INTERVAL_SEC = 4

app = FastAPI(title="CG Overlay Box API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TitleIn(BaseModel):
    title: str


class KofiToastIn(BaseModel):
    id: str
    text: str


class SceneIn(BaseModel):
    name: str


state: dict[str, Any] = {
    "scene": "clock",
    "show_clock": True,
    "title": "",
    "title_current": "Live",
    "kofi_enabled": True,
    "kofi_toast": None,
    "_clean_prev": None,
}

clients: set[WebSocket] = set()

SCENES: dict[str, dict[str, Any]] = {
    "clean": {
        "show_clock": False,
        "title": None,
        "kofi_enabled": False,
    },
    "clock": {
        "show_clock": True,
        "title": None,
        "kofi_enabled": None,
    },
    "title": {
        "show_clock": False,
        "title": "USE_CURRENT",
        "kofi_enabled": None,
    },
    "clock_title": {
        "show_clock": True,
        "title": "USE_CURRENT",
        "kofi_enabled": None,
    },
    "clock_kofi": {
        "show_clock": True,
        "title": None,
        "kofi_enabled": True,
    },
}


def auth(token: str | None) -> None:
    if token != TOKEN:
        raise HTTPException(status_code=401, detail="bad token")


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    KOFI_SINCE_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_since(path: Path) -> int:
    try:
        return int(path.read_text().strip() or "0")
    except Exception:
        return 0


def save_since(path: Path, value: int) -> None:
    try:
        path.write_text(str(value))
    except Exception:
        pass


def sanitize_toast_text(
    from_name: str | None,
    message: str | None,
    amount: str | None = None,
    currency: str | None = None,
) -> str:
    safe_from = (from_name or "Ko-fi").strip()
    safe_msg = (message or "").strip()
    safe_amount = (amount or "").strip()
    safe_currency = (currency or "").strip()

    if safe_amount:
        return f"{safe_from} ({safe_amount} {safe_currency}): {safe_msg}".strip()
    return f"{safe_from}: {safe_msg}".strip()



def run_script(script_name: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    script_path = SCRIPTS_DIR / script_name
    return subprocess.run([str(script_path), *args], check=check)


def run_script_background(script_name: str, *args: str) -> subprocess.Popen:
    script_path = SCRIPTS_DIR / script_name
    return subprocess.Popen([str(script_path), *args])


def switch_view(view: str) -> None:
    run_script("switch_view.sh", view)


def current_public_state() -> dict[str, Any]:
    return {
        k: v
        for k, v in state.items()
        if not k.startswith("_")
    }


async def broadcast_state() -> None:
    payload = current_public_state()
    dead: list[WebSocket] = []

    for ws in clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)

    for ws in dead:
        clients.discard(ws)


def snapshot_visible_state() -> dict[str, Any]:
    return {
        "scene": state.get("scene"),
        "show_clock": state.get("show_clock"),
        "title": state.get("title"),
        "kofi_enabled": state.get("kofi_enabled"),
    }


async def apply_scene(name: str) -> None:
    if name not in SCENES:
        raise HTTPException(status_code=400, detail="unknown scene")

    if name == "clean":
        if state.get("scene") == "clean" and state.get("_clean_prev"):
            prev = state["_clean_prev"]
            state["_clean_prev"] = None

            state["scene"] = prev.get("scene", "clock")
            state["show_clock"] = bool(prev.get("show_clock", True))
            state["title"] = prev.get("title", "") or ""
            state["kofi_enabled"] = bool(prev.get("kofi_enabled", True))

            await broadcast_state()
            return

        state["_clean_prev"] = snapshot_visible_state()
        state["scene"] = "clean"
        state["show_clock"] = False
        state["title"] = ""
        state["kofi_enabled"] = False

        await broadcast_state()
        return

    cfg = SCENES[name]

    state["scene"] = name
    state["show_clock"] = bool(cfg["show_clock"])

    scene_title = cfg["title"]
    if scene_title == "USE_CURRENT":
        state["title"] = state["title_current"]
    elif scene_title is None:
        state["title"] = ""
    else:
        state["title"] = str(scene_title)

    if cfg.get("kofi_enabled") is not None:
        state["kofi_enabled"] = bool(cfg["kofi_enabled"])

    state["_clean_prev"] = None
    await broadcast_state()


async def heartbeat_loop() -> None:
    while True:
        await broadcast_state()
        await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)


async def kofi_poller_loop() -> None:
    if not KOFI_POLL_URL or not KOFI_RELAY_TOKEN:
        return

    since = load_since(KOFI_SINCE_FILE)

    while True:
        try:
            qs = urllib.parse.urlencode(
                {
                    "since": since,
                    "limit": 20,
                }
            )
            url = f"{KOFI_POLL_URL}?{qs}"

            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", "cg-overlay-box/1.0")
            req.add_header("X-Relay-Token", KOFI_RELAY_TOKEN)

            with urllib.request.urlopen(req, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

            events = payload.get("events", [])
            changed = False

            for event in events:
                event_id = int(event["id"])
                since = max(since, event_id)
                save_since(KOFI_SINCE_FILE, since)

                if not event.get("is_public", True):
                    continue

                message = (event.get("message") or "").strip()
                if not message:
                    continue

                toast_text = sanitize_toast_text(
                    from_name=event.get("from_name"),
                    message=message,
                    amount=event.get("amount"),
                    currency=event.get("currency"),
                )

                state["kofi_toast"] = {
                    "id": event.get("message_id") or str(event_id),
                    "text": toast_text[:400],
                    "ts": int(time.time()),
                }
                changed = True

            if changed:
                await broadcast_state()

        except Exception as exc:
            print(f"Ko-fi poller error: {exc!r}", flush=True)

        await asyncio.sleep(KOFI_POLL_INTERVAL_SEC)


@app.on_event("startup")
async def startup() -> None:
    ensure_runtime_dirs()
    asyncio.create_task(heartbeat_loop())
    asyncio.create_task(kofi_poller_loop())


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/state")
async def get_state() -> dict[str, Any]:
    return current_public_state()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    clients.add(ws)
    await ws.send_json(current_public_state())

    try:
        while True:
            await asyncio.sleep(3600)
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)


@app.get("/api/scene/list")
async def scene_list() -> dict[str, Any]:
    return {
        "scenes": list(SCENES.keys()),
        "current": state["scene"],
    }


@app.get("/api/scene/set")
async def scene_set_get(name: str, token: str | None = None) -> dict[str, Any]:
    auth(token)
    await apply_scene(name)
    return {"ok": True, "scene": state["scene"]}


@app.post("/api/scene/set")
async def scene_set_post(payload: SceneIn, token: str | None = None) -> dict[str, Any]:
    auth(token)
    await apply_scene(payload.name)
    return {"ok": True, "scene": state["scene"]}


@app.get("/api/title/set")
async def title_set_get(text: str, token: str | None = None) -> dict[str, Any]:
    auth(token)
    state["title_current"] = text

    if state["scene"] in {"title", "clock_title"}:
        state["title"] = state["title_current"]

    await broadcast_state()
    return {"ok": True, "title_current": state["title_current"]}


@app.post("/api/title")
async def title_set_post(payload: TitleIn, token: str | None = None) -> dict[str, Any]:
    auth(token)
    state["title_current"] = payload.title

    if state["scene"] in {"title", "clock_title"}:
        state["title"] = state["title_current"]

    await broadcast_state()
    return {"ok": True, "title_current": state["title_current"]}


@app.get("/api/kofi/enabled")
async def kofi_enabled_get() -> dict[str, bool]:
    return {"kofi_enabled": bool(state.get("kofi_enabled", True))}


@app.get("/api/kofi/enabled/set")
async def kofi_enabled_set_get(enabled: bool, token: str | None = None) -> dict[str, Any]:
    auth(token)
    state["kofi_enabled"] = bool(enabled)
    await broadcast_state()
    return {"ok": True, "kofi_enabled": state["kofi_enabled"]}


@app.post("/api/kofi/enabled/set")
async def kofi_enabled_set_post(enabled: bool, token: str | None = None) -> dict[str, Any]:
    auth(token)
    state["kofi_enabled"] = bool(enabled)
    await broadcast_state()
    return {"ok": True, "kofi_enabled": state["kofi_enabled"]}


@app.get("/api/kofi/enabled/toggle")
async def kofi_enabled_toggle_get(token: str | None = None) -> dict[str, Any]:
    auth(token)
    state["kofi_enabled"] = not bool(state.get("kofi_enabled", True))
    await broadcast_state()
    return {"ok": True, "kofi_enabled": state["kofi_enabled"]}


@app.post("/api/kofi/enabled/toggle")
async def kofi_enabled_toggle_post(token: str | None = None) -> dict[str, Any]:
    auth(token)
    state["kofi_enabled"] = not bool(state.get("kofi_enabled", True))
    await broadcast_state()
    return {"ok": True, "kofi_enabled": state["kofi_enabled"]}


@app.post("/api/kofi/toast")
async def kofi_toast(payload: KofiToastIn, token: str | None = None) -> dict[str, bool]:
    auth(token)
    state["kofi_toast"] = {
        "id": payload.id[:64],
        "text": payload.text[:400],
        "ts": int(time.time()),
    }
    await broadcast_state()
    return {"ok": True}


@app.get("/api/view/overlay")
async def view_overlay(token: str | None = None) -> dict[str, str | bool]:
    auth(token)
    switch_view("overlay")
    return {"ok": True, "view": "overlay"}


@app.get("/api/view/quest")
async def view_quest(token: str | None = None) -> dict[str, str | bool]:
    auth(token)
    switch_view("quest")
    return {"ok": True, "view": "quest"}


@app.get("/api/view/quest_fullscreen")
async def view_quest_fullscreen(token: str | None = None) -> dict[str, str | bool]:
    auth(token)
    run_script("quest_fullscreen.sh")
    return {"ok": True, "view": "quest_fullscreen"}


@app.get("/api/view/quest_audio_max")
async def view_quest_audio_max(token: str | None = None) -> dict[str, str | bool]:
    auth(token)
    run_script("quest_audio_max.sh")
    return {"ok": True, "view": "quest_audio_max"}


@app.get("/api/view/quest_prepare_and_take")
async def view_quest_prepare_and_take(token: str | None = None) -> dict[str, str | bool]:
    auth(token)
    run_script_background("quest_prepare_and_take.sh")
    return {"ok": True, "view": "quest_prepare_and_take"}