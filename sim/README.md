# Hardware-Simulatoren für Landliebe Waage

Dieses Verzeichnis enthält zwei eigenständige Python-Simulatoren zur hardwareunabhängigen Entwicklung und zum Testen der Waagen- und Scanner-Kommunikation.

---

## 1. Waagen-Simulator: `sim/scale_sim.py`

Simuliert das **Mettler Toledo IND570 Wägeterminal** auf TCP-Ebene (Shared Data Protokoll).

### Eigenschaften
- **Shared Data (SD) Protokoll**: Beantwortet `user <login>` und `read wt0101 wt0103` mit `00R453~<gewicht>~<einheit>~<status_flag>`.
- **Maximal 5 Verbindungen gleichzeitig**: Weist weitere Verbindungsversuche ab, sobald 5 Clients verbunden sind.
- **Inaktivitäts-Timeout von 300 Sekunden**: Trennt inaktive Verbindungen automatisch nach 300s.
- **Verbindungsabbruch simulierbar**: Trennt aktive Clients sofort per Terminal-Befehl (`drop`).
- **Gewicht flexibel steuerbar**: Beliebige Gewichte einstellbar oder direkt auf Null setzbar (`zero`).
- **Status umschaltbar**: Stabil (`S`), In Bewegung (`D`), oder Fehlermodus (`99`).

### Starten & Pflicht-Argumente

`--host` und `--port` sind **zwingend erforderlich**:

```bash
# Standard-Start auf Port 1701:
python sim/scale_sim.py --host 0.0.0.0 --port 1701

# Mit Anfangsgewicht von 15.000 kg:
python sim/scale_sim.py -H 127.0.0.1 -p 1701 --weight 15000

# Hilfe und alle Optionen anzeigen:
python sim/scale_sim.py --help
```

### Interaktive Bedienung während der Laufzeit

Sobald der Simulator gestartet ist, fordert die Konsole zur Eingabe des neuen Gewichts auf:
```text
Gewicht eingeben in kg [Aktuell: 0.0 kg]: 18500
>> [OK] Gewicht erfolgreich auf 18500.0 kg geändert.
```

- **Nur Zahlen erlaubt**: Eingaben werden strikt validiert. Ungültige Eingaben (z. B. Buchstaben) werden mit einer Fehlermeldung abgewiesen. Sowohl Punkt (`1250.5`) als auch deutsches Komma (`1250,5`) werden akzeptiert.
- **Nullpunkt**: Eingabe von `0` setzt das Gewicht direkt auf `0.0 kg`.
- **Verbindungsabbruch**: Eingabe von `drop` trennt sofort alle aktiven Client-Verbindungen.
- **Statusanzeige**: Eingabe von `status` zeigt alle Details und verbundene Clients an.
- **Beenden**: Eingabe von `quit` oder `exit`.

---

## 2. QR-Code Scanner Simulator: `sim/scanner_sim.py`

Simuliert den **Newland FM3080 Barcode- und QR-Code Scanner** als TCP-Server.

### Eigenschaften
- Sendet gescannte Codes / Nummern im Format `<code_text>\r\n` an alle verbundenen Clients.
- **Ausschliesslich bei Eingabe**: Ein Scan wird **nur dann übertragen**, wenn aktiv im Terminal eine Eingabe getätigt und mit Enter bestätigt wird. Keine unkontrollierten Hintergrundscans.
- **Verbindungsabbruch simulierbar**: Trennt aktive Scanner-Clients per Befehl (`drop`).

### Starten & Pflicht-Argumente

`--host` und `--port` sind **zwingend erforderlich**:

```bash
# Standard-Start auf Port 4001:
python sim/scanner_sim.py --host 0.0.0.0 --port 4001

# Mit optionalem Präfix 'QR-':
python sim/scanner_sim.py -H 127.0.0.1 -p 4001 --prefix QR-

# Hilfe und alle Optionen anzeigen:
python sim/scanner_sim.py --help
```

### Interaktive Bedienung während der Laufzeit

Sobald der Simulator läuft, zeigt er die Anzahl verbundener Clients an und wartet auf eine Eingabe:
```text
QR-Code / Nummer scannen [Verbundene Clients: 1]: 12345
>> [OK] Scan '12345' erfolgreich an 1 Client(s) gesendet.

QR-Code / Nummer scannen [Verbundene Clients: 1]: LKW-AB-9876
>> [OK] Scan 'LKW-AB-9876' erfolgreich an 1 Client(s) gesendet.
```

- **Scan senden**: Beliebige Nummer oder Zeichenkette eingeben und `Enter` drücken.
- **Verbindungsabbruch**: `drop` trennt sofort alle aktiven Scanner-Verbindungen.
- **Status & Clients**: `status` oder `clients` zeigt Details an.
- **Beenden**: `quit` oder `exit`.

---

## Verbindung mit der Hauptanwendung

In `config.toml` können die Simulatoren eingetragen werden:

```toml
[ind570]
host = "127.0.0.1"
port = 1701
simulate = false     # false, da der Simulator als echter TCP-Server agiert!

[scanner]
host = "127.0.0.1"
port = 4001
simulate = false     # false, da der Scanner-Simulator als echter TCP-Server agiert!
```
