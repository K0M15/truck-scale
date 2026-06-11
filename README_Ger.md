# Landliebe Waage

Steuerungssoftware für eine industrielle LKW-Waage mit Mettler Toledo IND570 Wägeterminal.

## Übersicht

- **SD Server**-Modul zur Kommunikation mit dem IND570 Terminal (TCP Port 1701)
- **Logger** – sekündliche Aufzeichnung mit Zeitstempel bei Gewicht > 0, tägliche CSV-Dateien
- **Web-Frontend** – Live-Anzeige des aktuellen Gewichts per WebSocket, Status-LEDs, Verlaufstabelle

## Projektstruktur

```
├── app/
│   ├── main.py                    # Einstiegspunkt, startet alle Komponenten
│   ├── ind570/
│   │   └── client.py              # IND570 SD Server TCP-Client
│   ├── logger/
│   │   └── logger.py              # CSV-Logger (tägliche Rotation)
│   └── web/
│       ├── routes.py              # Flask + SocketIO (WebSocket)
│       ├── templates/
│       │   └── index.html         # Dashboard-UI
│       └── static/
│           └── style.css          # Dark-Theme Styling
├── logs/                          # weight_YYYY-MM-DD.csv (automatisch erstellt)
├── config.toml                    # Konfiguration
├── requirements.txt
├── README.md                      # Englische Dokumentation
└── README_Ger.md                  # Deutsche Dokumentation
```

## Abhängigkeiten

- Python 3.11+
- Flask, Flask-SocketIO
- Keine externen Hardware-Treiber – Kommunikation über Standard-TCP-Sockets

## Setup

```bash
# Virtual Environment erstellen
python3 -m venv .venv

# Abhängigkeiten installieren
# Linux:
.venv/bin/pip install -r requirements.txt

# Windows:
.venv\Scripts\pip install -r requirements.txt
```

## Konfiguration

`config.toml`:

```toml
[ind570]
host = "192.168.0.100"      # IP-Adresse des IND570
port = 1701                  # SD Server TCP-Port (Standard: 1701)
username = ""                # SD Server Benutzername (leer wenn nicht benötigt)
password = ""                # SD Server Passwort (leer wenn nicht benötigt)
simulate = true              # true = Simulationsmodus, false = echte Waage

[logger]
log_dir = "logs"             # Verzeichnis für CSV-Logdateien

[web]
host = "0.0.0.0"             # Webserver Listener (0.0.0.0 = alle Interfaces)
port = 8080                  # Webserver Port

[polling]
interval = 1.0               # Abfrageintervall in Sekunden
```

## Start

```bash
# Linux:
.venv/bin/python -m app.main

# Windows:
.venv\Scripts\python -m app.main
```

Web-Oberfläche: **http://localhost:8080**

## Betriebsmodi

### Simulationsmodus (`simulate = true`)
Pendelt automatisch zwischen 0 und ~30.000 kg – zum Testen der UI und des Loggers ohne echte Waage.

### Live-Modus (`simulate = false`)
Verbindet sich per TCP mit dem IND570 Shared Data (SD) Server auf Port 1701. Fragt das Bruttogewicht jede Sekunde mit dem Befehl `read wt0101 wt0103` ab.

## Logging

- Eine CSV-Datei pro Tag: `logs/weight_YYYY-MM-DD.csv`
- Header: `timestamp, weight_kg, stable`
- Eintrag nur bei Gewicht > 0
- Pro Sekunde ein Eintrag (entsprechend `polling.interval`)
- Dateien werden nicht automatisch gelöscht
- `stable`: 1 = Gewicht stabil (laut IND570 Status-Flag), 0 = in Bewegung

## Web-Oberfläche

- Große digitale Gewichtsanzeige (Live-Update via WebSocket)
- Status-LEDs: Grün = stabil, Gelb = in Bewegung, Rot = Fehler
- Verbindungsindikator (grün = verbunden, rot = getrennt)
- Tabelle mit den letzten 50 Wägungen

## IND570 Schnittstelle – Shared Data (SD) Server

Das IND570 startet standardmäßig einen SD Server auf **TCP Port 1701**. Die Kommunikation erfolgt über ein einfaches textbasiertes Protokoll:

1. TCP-Socket-Verbindung zu Port 1701 aufbauen
2. Authentifizierung (optional): `user anonymous`
3. Gewicht abfragen: `read wt0101 wt0103` liefert `00R453~14780~kg~S`

### Verwendete SD-Befehle

| Befehl               | Beschreibung                       | Antwort-Beispiel              |
|----------------------|------------------------------------|-------------------------------|
| `read wt0101 wt0103` | Bruttogewicht + Einheit lesen      | `00R453~14780~kg~S`           |

Antwortformat: `<status><op><id>~<gewicht>~<einheit>~<status_flag>`

- `status`: `00` = Erfolg, `99` = Fehler
- `status_flag`: `S` = stabil, `D` = in Bewegung, leer = Stillstand

### Alternative: Callback-Modus (Echtzeit-Push)

Statt Polling kann das IND570 Gewichtsänderungen automatisch senden:

```
callback wt0101
ctimer 100
```

Das Terminal sendet dann bei jeder Gewichtsänderung `wt0101 <Gewicht>` (maximal alle 100 ms). Für Callback-Modus muss `app/ind570/client.py` angepasst werden.

### Sicherheit

Falls der IND570 SD Server eine Authentifizierung verlangt, wird `user anonymous` beim Verbinden gesendet. Die Benutzerverwaltung des Terminals wird unter **Setup > Anwendung > Benutzer** konfiguriert.

## Plattform

- Entwickelt für **Windows** und **Linux**
- Python 3.11+ (für `tomllib`)

## Betrieb unter Linux

### Setup

```bash
# Repository klonen oder Dateien entpacken
cd Landliebe-Waage

# Virtual Environment erstellen
python3 -m venv .venv

# Abhängigkeiten installieren
.venv/bin/pip install -r requirements.txt
```

### Manuell starten

```bash
.venv/bin/python -m app.main
```

Beenden mit `Ctrl+C`.

### Als systemd-Service einrichten (empfohlen)

Service-Datei erstellen:

```bash
sudo nano /etc/systemd/system/landliebe-waage.service
```

```ini
[Unit]
Description=Landliebe Waage Steuerung
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

Service aktivieren und starten:

```bash
sudo systemctl daemon-reload
sudo systemctl enable landliebe-waage
sudo systemctl start landliebe-waage
sudo systemctl status landliebe-waage
```

Logs des Services anzeigen:

```bash
sudo journalctl -u landliebe-waage -f
```

## Als Dienst einrichten (Windows)

### NSSM (Non-Sucking Service Manager)

```powershell
# NSSM installieren (https://nssm.cc)
nssm install LandliebeWaage .venv\Scripts\python.exe "-m app.main"
nssm set LandliebeWaage AppDirectory C:\Pfad\zu\Landliebe-Waage
nssm set LandliebeWaage AppStdout C:\Pfad\zu\Landliebe-Waage\logs\service_stdout.log
nssm set LandliebeWaage AppStderr C:\Pfad\zu\Landliebe-Waage\logs\service_stderr.log
nssm set LandliebeWaage Start SERVICE_AUTO_START
nssm start LandliebeWaage
```

Deinstallieren:

```powershell
nssm stop LandliebeWaage
nssm remove LandliebeWaage confirm
```
