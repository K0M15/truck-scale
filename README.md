# Landliebe Scale

Control software for an industrial truck scale with Mettler Toledo IND570 weighing terminal.

## Overview

- **SD Server** module for communication with the IND570 terminal (TCP port 1701)
- **Logger** – logs weight every second with timestamp when weight > 0, daily CSV files
- **Web frontend** – live weight display via WebSocket, status LEDs, history table

## Project Structure

```
├── app/
│   ├── main.py                    # Entry point, starts all components
│   ├── ind570/
│   │   └── client.py              # IND570 SD Server TCP client
│   ├── logger/
│   │   └── logger.py              # CSV logger (daily rotation)
│   └── web/
│       ├── routes.py              # Flask + SocketIO (WebSocket)
│       ├── templates/
│       │   └── index.html         # Dashboard UI
│       └── static/
│           └── style.css          # Dark theme styling
├── logs/                          # weight_YYYY-MM-DD.csv (auto-created)
├── config.toml                    # Configuration
├── requirements.txt
├── README.md
└── README_Ger.md                  # German documentation
```

## Dependencies

- Python 3.11+
- Flask, Flask-SocketIO
- No external hardware drivers required – communicates via standard TCP sockets

## Setup

```bash
# Create virtual environment
python3 -m venv .venv

# Install dependencies
# Linux:
.venv/bin/pip install -r requirements.txt

# Windows:
.venv\Scripts\pip install -r requirements.txt
```

## Configuration

`config.toml`:

```toml
[ind570]
host = "192.168.0.100"      # IND570 IP address
port = 1701                  # SD Server TCP port (default: 1701)
username = ""                # SD Server username (leave empty if not required)
password = ""                # SD Server password (leave empty if not required)
simulate = true              # true = simulation mode, false = real scale

[logger]
log_dir = "logs"             # CSV log file directory

[web]
host = "0.0.0.0"             # Web server listener (0.0.0.0 = all interfaces)
port = 8080                  # Web server port

[polling]
interval = 1.0               # Polling interval in seconds
```

## Start

```bash
# Linux:
.venv/bin/python -m app.main

# Windows:
.venv\Scripts\python -m app.main
```

Web interface: **http://localhost:8080**

## Operating Modes

### Simulation Mode (`simulate = true`)
Automatically cycles between 0 and ~30,000 kg – for testing the UI and logger without a real scale.

### Live Mode (`simulate = false`)
Connects via TCP to the IND570 Shared Data (SD) Server on port 1701. Polls gross weight every second using the `r wt0101` command.

## Logging

- One CSV file per day: `logs/weight_YYYY-MM-DD.csv`
- Header: `timestamp, weight_kg, stable`
- Entry only when weight > 0
- One entry per second (according to `polling.interval`)
- Files are not automatically deleted
- `stable`: 1 = weight stable (per IND570 status flag), 0 = in motion

## Web Interface

- Large digital weight display (live update via WebSocket)
- Status LEDs: Green = stable, Yellow = in motion, Red = error
- Connection indicator (green = connected, red = disconnected)
- Table showing the last 50 weighings

## IND570 Interface – Shared Data (SD) Server

The IND570 starts an SD Server on **TCP port 1701** by default. Communication uses a simple text-based protocol:

1. Establish a TCP socket connection to port 1701
2. Authenticate (optional): `user anonymous`
3. Poll weight: `read wt0101 wt0103` returns `00R453~14780~kg~S` (tilde-separated)

### SD Server Commands Used

| Command               | Description                | Response Example              |
|-----------------------|----------------------------|-------------------------------|
| `read wt0101 wt0103`  | Read gross weight + unit   | `00R453~14780~kg~S`           |

Response format: `<status><op><id>~<weight>~<unit>~<status_flag>`

- `status`: `00` = success, `99` = error
- `status_flag`: `S` = stable, `D` = dynamic/in motion, empty = standstill

### Alternative: Callback Mode (Real-Time Push)

Instead of polling, the IND570 can push weight updates automatically:

```
callback wt0101
ctimer 100
```

The terminal then sends `wt0101 <weight>` whenever the weight changes (throttled to max every 100 ms). To use callback mode, modify `app/ind570/client.py`.

### Security

If the IND570 SD Server requires authentication, the code sends `user anonymous` on connect. The terminal's user management is configured under **Setup > Application > Users**.

## Platform

- Developed for **Windows** and **Linux**
- Python 3.11+ (for `tomllib`)

## Linux – Running as a Service (systemd)

Create the service file:

```bash
sudo nano /etc/systemd/system/landliebe-waage.service
```

```ini
[Unit]
Description=Landliebe Scale Control
After=network.target

[Service]
Type=simple
User=landliebe
WorkingDirectory=/opt/Landliebe-Waage
ExecStart=/opt/Landliebe-Waage/.venv/bin/python -m app.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable landliebe-waage
sudo systemctl start landliebe-waage
sudo systemctl status landliebe-waage
```

View service logs:

```bash
sudo journalctl -u landliebe-waage -f
```

## Windows – Running as a Service (WinSW + Watchdog)

The project includes service wrapper support using **WinSW** (Windows Service Wrapper) and an integrated watchdog (`service_runner.py`) with automatic restart on crash or unexpected exit.

### Option 1: Native Windows Service (System Boot)

1. Right-click `install_service.bat` -> **Run as Administrator**.
2. The service `LandliebeWaage` is installed with `Automatic` startup and started immediately.

Management scripts:
- `start_service.bat` – Start service
- `stop_service.bat` – Stop service
- `restart_service.bat` – Restart service
- `status_service.bat` – Check service status
- `uninstall_service.bat` – Uninstall service (requires Administrator)

Service configuration (`LandliebeWaage.xml`):
- Restarts automatically within 5 seconds on crash (`<onfailure action="restart" delay="5 sec"/>`)
- Starts on Windows boot (`<startmode>Automatic</startmode>`)

---

### Option 2: Background Runner with User Autostart (No Admin required)

Enable autostart on user logon:
```powershell
powershell -ExecutionPolicy Bypass -File autostart_setup.ps1 -Action enable
```

Manual background controls:
- Start silently (no console window): Double-click `start_background.vbs`
- Stop: Double-click `stop_background.bat`
- Supervisor logs: `logs/watchdog.log`

