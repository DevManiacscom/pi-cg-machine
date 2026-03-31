# CG Overlay Box

A lightweight, self-hosted CG (character generator) system for live streaming, built around Chromium, FastAPI, and systemd user services.

Designed for:
- reliability (always-on kiosk mode)
- automation (StreamDeck / HTTP API)
- hardware integration (ATEM switchers)
- low-latency local workflows

---

## Important: X11 Required

This system **requires X11**.

Wayland is **not supported** for this setup because several production-critical parts depend on predictable X11 behavior:

- Chromium DevTools control
- window automation / focus handling
- `xdotool`
- stable cursor behavior with `unclutter`

### Switch Raspberry Pi to X11

```bash
sudo raspi-config
```

Then go to:

```text
Advanced Options → Wayland → Disable Wayland (use X11)
```

Reboot:

```bash
sudo reboot
```

Verify:

```bash
echo $XDG_SESSION_TYPE
```

Expected output:

```text
x11
```

---

## Features

- FastAPI backend for control and automation
- Chromium-based overlay (kiosk mode)
- Meta Quest casting integration
- ATEM switcher control via `PyATEMMax`
- WebSocket updates for UI
- Fully automated through systemd user services
- StreamDeck-ready HTTP API
- No Docker

---

## Architecture Overview

```text
[ StreamDeck ] → [ FastAPI API ] → [ Scripts ]
                              ↓
                    [ Chromium Windows ]
                       ├─ Overlay UI
                       └─ Quest Casting
                              ↓
                          HDMI → ATEM
```

---

## systemd Startup Flow

The project uses **user-level** systemd services.

```text
login / X11 session
        ↓
systemd --user
        ├─ overlay-api.service
        │      └─ FastAPI backend (backend/main.py)
        │
        ├─ overlay-chromium-overlay.service
        │      ├─ Chromium overlay window
        │      └─ ExecStartPost → xset s off / -dpms / noblank
        │
        ├─ overlay-chromium-quest.service
        │      ├─ Chromium Meta Quest casting window
        │      └─ ExecStartPost → xset s off / -dpms / noblank
        │
        ├─ overlay-watchdog.timer
        │      └─ overlay-watchdog.service
        │             └─ health check / restart logic
        │
        └─ unclutter.service
               └─ hides mouse cursor
```

### Runtime control flow

```text
StreamDeck button
    ↓
HTTP GET request in background
    ↓
FastAPI endpoint
    ↓
shell/Python script
    ↓
Chromium / Quest / ATEM action
```

### Main Quest production path

```text
/api/view/quest_prepare_and_take
    ↓
quest_prepare_and_take.sh
    ├─ quest_detect_ready.py
    ├─ quest_fullscreen.py
    ├─ quest_audio_max.py
    ├─ switch_view.sh quest
    └─ atem_take_pi.py
```

---

## Quick Start (Recommended)

```bash
git clone https://github.com/DevManiacscom/pi-cg-machine.git
cd pi-cg-machine

chmod +x install.sh
./install.sh
```

This will:
- install OS packages
- create the Python virtual environment
- install Python dependencies
- install user-level systemd units
- create runtime directories

---

## Manual Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

mkdir -p ~/.config/cg-overlay-box
cp .env.example ~/.config/cg-overlay-box/overlay.env

mkdir -p ~/.local/state/cg-overlay-box
mkdir -p ~/.config/systemd/user
cp systemd-user/*.service ~/.config/systemd/user/

systemctl --user daemon-reload
systemctl --user enable --now overlay-api.service
systemctl --user enable --now overlay-chromium-overlay.service
systemctl --user enable --now overlay-chromium-quest.service
systemctl --user enable --now overlay-watchdog.timer
systemctl --user enable unclutter.service

sudo loginctl enable-linger "$(whoami)"
```

---

## Repository Layout

```text
cg-overlay-box/
├── backend/
│   └── main.py
│
├── scripts/
│   ├── atem_take_pi.py
│   ├── quest_audio_max.py
│   ├── quest_detect_ready.py
│   ├── quest_fullscreen.py
│   ├── quest_prepare_and_take.sh
│   └── switch_view.sh
│
├── systemd-user/
│   ├── overlay-api.service
│   ├── overlay-chromium-overlay.service
│   ├── overlay-chromium-quest.service
│   ├── overlay-watchdog.service
│   └── overlay-watchdog.timer
│
├── web/
│   └── index.html
│
├── requirements.txt
├── .env.example
├── install.sh
└── README.md
```

---

## Configuration

Main config file:

```text
~/.config/cg-overlay-box/overlay.env
```

### Example

```env
OVERLAY_TOKEN=my_token
OVERLAY_PORT=8000

ATEM_IP=192.168.1.150
ATEM_INPUT=2

CHROME_DEBUG_HOST=127.0.0.1
CHROME_DEBUG_PORT=9223

CG_OVERLAY_DATA_DIR=/home/pi/.local/state/cg-overlay-box

KOFI_POLL_URL=https://example.org/kofi/poll
KOFI_RELAY_TOKEN=change_me
KOFI_SINCE_FILE=/home/pi/.local/state/cg-overlay-box/kofi_since.txt
```

---

## StreamDeck Integration

Use this action type:

```text
Website → GET request in background
```

### Main buttons

#### Quest
Runs the full production path:
- detect stream
- fullscreen
- audio max
- reveal Quest
- switch ATEM

```text
http://<PI_IP>:8000/api/view/quest_prepare_and_take?token=<OVERLAY_TOKEN>
```

#### Overlay

```text
http://<PI_IP>:8000/api/view/overlay?token=<OVERLAY_TOKEN>
```

#### Clean

```text
http://<PI_IP>:8000/api/scene/set?name=clean&token=<OVERLAY_TOKEN>
```

#### Clock

```text
http://<PI_IP>:8000/api/scene/set?name=clock&token=<OVERLAY_TOKEN>
```

#### Title

```text
http://<PI_IP>:8000/api/scene/set?name=title&token=<OVERLAY_TOKEN>
```

#### Clock + Title

```text
http://<PI_IP>:8000/api/scene/set?name=clock_title&token=<OVERLAY_TOKEN>
```

#### Clock + Ko-fi

```text
http://<PI_IP>:8000/api/scene/set?name=clock_kofi&token=<OVERLAY_TOKEN>
```

#### Ko-fi Toggle

```text
http://<PI_IP>:8000/api/kofi/enabled/toggle?token=<OVERLAY_TOKEN>
```

### Optional debug buttons

#### Quest Fullscreen

```text
http://<PI_IP>:8000/api/view/quest_fullscreen?token=<OVERLAY_TOKEN>
```

#### Quest Audio Max

```text
http://<PI_IP>:8000/api/view/quest_audio_max?token=<OVERLAY_TOKEN>
```

---

## Systemd Services

All project services are **user-level**.

### Check status

```bash
systemctl --user status overlay-api.service --no-pager
systemctl --user status overlay-chromium-overlay.service --no-pager
systemctl --user status overlay-chromium-quest.service --no-pager
systemctl --user status overlay-watchdog.timer --no-pager
systemctl --user status unclutter.service --no-pager
```

### Logs

```bash
journalctl --user -u overlay-api.service -f
journalctl --user -u overlay-chromium-overlay.service -f
journalctl --user -u overlay-chromium-quest.service -f
```

### Enable lingering

This allows user services to continue running across reboots without an interactive login:

```bash
sudo loginctl enable-linger "$(whoami)"
```

---

## Troubleshooting

### Chromium not starting

- Ensure X11 is active
- Check:
  ```bash
  echo $DISPLAY
  echo $XDG_SESSION_TYPE
  ```
- Test manually:
  ```bash
  chromium --kiosk
  ```

### Quest casting not detected

- Check `CHROME_DEBUG_PORT`
- Ensure the casting tab is open
- Ensure the Meta account is logged in

### Quest audio or fullscreen not applying

- Verify the Quest casting page is the active tab in the Quest Chromium window
- Test scripts manually:
  ```bash
  ./.venv/bin/python scripts/quest_fullscreen.py
  ./.venv/bin/python scripts/quest_audio_max.py
  ```

### ATEM not switching

- Verify `ATEM_IP`
- Verify the selected input number
- Check network connectivity between Pi and ATEM

### API not responding

```bash
curl http://127.0.0.1:8000/health
```

---

## Production Hardening

For a production appliance-style setup, use the following checklist.

### 1. Stay on X11

Do not run this project under Wayland.

### 2. Enable lingering

```bash
sudo loginctl enable-linger "$(whoami)"
```

This ensures user-level services survive reboots and do not depend on an interactive terminal session.

### 3. Disable screen blanking

This project disables X11 screen blanking and DPMS from the Chromium user services themselves via `ExecStartPost`, instead of using a separate blanking service.

Also make sure kernel console blanking is disabled:

```bash
sudo nano /boot/firmware/cmdline.txt
```

Add this to the end of the existing single line:

```bash
consoleblank=0
```

After reboot, verify:

```bash
DISPLAY=:0 XAUTHORITY=$HOME/.Xauthority xset q
```

Expected:

- timeout: 0
- DPMS is Disabled

### 4. Keep `.env` outside the repository

Use:

```text
~/.config/cg-overlay-box/overlay.env
```

Never commit real tokens or real ATEM IPs.

### 5. Restrict API exposure

This API is meant for a trusted local network.

Recommended options:
- keep the Pi on a private LAN
- do not expose port 8000 to the public internet
- restrict inbound firewall rules if needed

Example with UFW:

```bash
sudo ufw allow from 192.168.1.0/24 to any port 8000 proto tcp
sudo ufw enable
```

Adjust the subnet to match your network.

### 6. Use stable IPs

Assign stable addresses or DHCP reservations for:
- Raspberry Pi
- ATEM switcher
- StreamDeck host (if useful for firewall rules)

### 7. Verify after every reboot

Run:

```bash
systemctl --user status overlay-api.service --no-pager
systemctl --user status overlay-chromium-overlay.service --no-pager
systemctl --user status overlay-chromium-quest.service --no-pager
curl http://127.0.0.1:8000/health
```

---

## Development

```bash
source .venv/bin/activate
cd backend
uvicorn main:app --reload
```

---

## License

MIT
