# CG Overlay Box

A lightweight, self-hosted CG (character generator) system for live streaming, built around Chromium, FastAPI, and systemd user services.

Designed for:
- reliability (always-on kiosk mode)
- automation (StreamDeck / scripts)
- hardware integration (ATEM switchers)
- low-latency local workflows

---

## Features

- FastAPI backend for control and automation
- Chromium-based overlay (kiosk mode)
- Meta Quest casting integration
- ATEM switcher control
- WebSocket updates for UI
- Fully headless automation via systemd user services
- No Docker required

---

## Architecture Overview

```
[ StreamDeck ] → [ FastAPI API ] → [ Scripts ]
                              ↓
                    [ Chromium Windows ]
                       ├─ Overlay UI
                       └─ Quest Casting
                              ↓
                          HDMI → ATEM
```

---

## Quick Start (5 minutes)

```bash
git clone https://github.com/DevManiacscom/pi-cg-machine.git
cd pi-cg-machine

python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

mkdir -p ~/.config/cg-overlay-box
cp .env.example ~/.config/cg-overlay-box/overlay.env

mkdir -p ~/.local/state/cg-overlay-box

mkdir -p ~/.config/systemd/user
cp systemd-user/*.service ~/.config/systemd/user/

systemctl --user daemon-reload
systemctl --user enable --now overlay-api.service
systemctl --user enable --now overlay-chromium-overlay.service
systemctl --user enable --now overlay-chromium-quest.service
systemctl --user enable --now hide-cursor.service
```

---

## Repository Layout

```
cg-overlay-box/
├── backend/
├── web/
├── scripts/
├── systemd-user/
├── .env.example
└── README.md
```

---

## Configuration

Main config file:

```
~/.config/cg-overlay-box/overlay.env
```

Example:

```
OVERLAY_TOKEN=my_token
OVERLAY_PORT=8000

ATEM_IP=192.168.1.150
ATEM_PI_INPUT=2

CHROME_DEBUG_PORT=9223
```

---

## Systemd Services

All services are user-level.

### Enable all

```bash
systemctl --user enable --now overlay-api.service
systemctl --user enable --now overlay-chromium-overlay.service
systemctl --user enable --now overlay-chromium-quest.service
systemctl --user enable --now hide-cursor.service
```

### Logs

```bash
journalctl --user -u overlay-api.service -f
```

---

## Troubleshooting

### Chromium not starting
- Check X11 session is running
- Verify DISPLAY is available
- Run manually:
```bash
chromium --kiosk
```

### Quest casting not detected
- Ensure DevTools port matches `CHROME_DEBUG_PORT`
- Check casting page is open and logged in

### ATEM not switching
- Verify `ATEM_IP`
- Verify input port
- Check network connectivity

---

## Security

- Change default token:
```
OVERLAY_TOKEN=my_token
```

- Do not expose API to public internet

---

## Development

Run backend manually:

```bash
source .venv/bin/activate
cd backend
uvicorn main:app --reload
```


---

## License

MIT
