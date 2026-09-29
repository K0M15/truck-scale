#!/usr/bin/env python3
"""
Mettler Toledo IND570 Wägeterminal - TCP SD Server Simulator

Simuliert das Mettler Toledo IND570 Wägeterminal auf TCP-Ebene (Shared Data Protokoll).
Ermöglicht das Testen von Verbindungsaufbau, Gewichtsabfragen, Verbindungsabbrüchen
sowie Grenzwerten (max. 5 Verbindungen, 300s Inaktivitäts-Timeout).

Verwendung:
    python sim/scale_sim.py --host 0.0.0.0 --port 1701
    python sim/scale_sim.py -H 127.0.0.1 -p 1701 --weight 15000
    python sim/scale_sim.py --help
"""

import sys
import time
import socket
import select
import threading
import argparse
from datetime import datetime


class ScaleState:
    """Verwaltet den aktuellen Status der simulierten Waage."""

    def __init__(self, initial_weight: float = 0.0, unit: str = "kg", stable: bool = True):
        self.lock = threading.Lock()
        self.weight = float(initial_weight)
        self.unit = unit
        self.stable = stable
        self.error_mode = False

    def set_weight(self, weight: float):
        with self.lock:
            self.weight = max(0.0, float(weight))

    def set_zero(self):
        with self.lock:
            self.weight = 0.0

    def set_stable(self, stable: bool):
        with self.lock:
            self.stable = stable

    def toggle_error(self):
        with self.lock:
            self.error_mode = not self.error_mode
            return self.error_mode

    def get_reading(self):
        with self.lock:
            return self.weight, self.unit, self.stable, self.error_mode


class ScaleSimulator:
    """TCP SD Server für Mettler Toledo IND570 Simulation."""

    def __init__(self, host: str, port: int, state: ScaleState, max_connections: int = 5, timeout: int = 300):
        self.host = host
        self.port = port
        self.state = state
        self.max_connections = max_connections
        self.timeout = timeout

        self.server_sock = None
        self.running = False
        self.clients = {}  # sock -> {"addr": ..., "connected_at": ..., "last_active": ...}
        self.clients_lock = threading.Lock()

    def log(self, msg: str):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] [Waage-Sim] {msg}", flush=True)

    def start(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_sock.bind((self.host, self.port))
        except OSError as e:
            self.log(f"FEHLER: Port {self.port} konnte nicht gebunden werden ({e})")
            sys.exit(1)

        self.server_sock.listen(10)
        self.running = True
        self.log(f"IND570 SD Server gestartet auf {self.host}:{self.port}")
        self.log(f"Max. gleichzeitige Verbindungen: {self.max_connections} | Inaktivitäts-Timeout: {self.timeout}s")

        # Hintergrund-Threads
        threading.Thread(target=self._accept_loop, daemon=True).start()
        threading.Thread(target=self._timeout_watchdog, daemon=True).start()

    def stop(self):
        self.running = False
        self.disconnect_all("Simulator wird beendet")
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
        self.log("Server gestoppt.")

    def disconnect_all(self, reason: str = "Manuell getrennt"):
        with self.clients_lock:
            socks = list(self.clients.keys())
            for sock in socks:
                addr = self.clients[sock]["addr"]
                self.log(f"Verbindung zu {addr[0]}:{addr[1]} abgebrochen ({reason})")
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    sock.close()
                except Exception:
                    pass
            self.clients.clear()

    def disconnect_client(self, client_index: int):
        with self.clients_lock:
            items = list(self.clients.items())
            if 0 <= client_index < len(items):
                sock, info = items[client_index]
                addr = info["addr"]
                self.log(f"Verbindung zu Client #{client_index + 1} ({addr[0]}:{addr[1]}) abgebrochen")
                try:
                    sock.close()
                except Exception:
                    pass
                del self.clients[sock]
                return True
            return False

    def _accept_loop(self):
        while self.running:
            try:
                sock, addr = self.server_sock.accept()
            except OSError:
                break

            with self.clients_lock:
                current_count = len(self.clients)
                if current_count >= self.max_connections:
                    self.log(f"Verbindung von {addr[0]}:{addr[1]} ABGEWIESEN: Maximum von {self.max_connections} Verbindungen erreicht!")
                    try:
                        sock.sendall(b"99E~Max connections reached\r\n")
                        sock.close()
                    except Exception:
                        pass
                    continue

                self.clients[sock] = {
                    "addr": addr,
                    "connected_at": time.time(),
                    "last_active": time.time(),
                }
                count = len(self.clients)
                self.log(f"Neuer Client verbunden: {addr[0]}:{addr[1]} (Aktive Verbindungen: {count}/{self.max_connections})")

            threading.Thread(target=self._client_handler, args=(sock, addr), daemon=True).start()

    def _timeout_watchdog(self):
        while self.running:
            time.sleep(2)
            now = time.time()
            to_remove = []
            with self.clients_lock:
                for sock, info in list(self.clients.items()):
                    idle_sec = now - info["last_active"]
                    if idle_sec >= self.timeout:
                        addr = info["addr"]
                        self.log(f"Timeout bei Client {addr[0]}:{addr[1]}: keine Aktivitaet seit {idle_sec:.0f}s (Limit: {self.timeout}s). Verbindung getrennt.")
                        to_remove.append(sock)

                for sock in to_remove:
                    try:
                        sock.close()
                    except Exception:
                        pass
                    if sock in self.clients:
                        del self.clients[sock]

    def _client_handler(self, sock: socket.socket, addr):
        buffer = b""
        sock.settimeout(1.0)

        while self.running:
            try:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                buffer += chunk

                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line_str = line.decode("utf-8", errors="replace").strip("\r\n ").strip()
                    if not line_str:
                        continue

                    with self.clients_lock:
                        if sock in self.clients:
                            self.clients[sock]["last_active"] = time.time()

                    resp = self._handle_command(line_str)
                    if resp is not None:
                        sock.sendall(resp.encode("utf-8") + b"\r\n")
                    if line_str.lower() == "quit":
                        break

            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError):
                break
            except OSError as e:
                if getattr(e, "winerror", None) in (10038, 10053, 10054) or not self.running:
                    break
                self.log(f"Fehler bei Client {addr[0]}:{addr[1]}: {e}")
                break
            except Exception as e:
                if not self.running:
                    break
                self.log(f"Fehler bei Client {addr[0]}:{addr[1]}: {e}")
                break

        with self.clients_lock:
            if sock in self.clients:
                del self.clients[sock]
                count = len(self.clients)
                self.log(f"Client getrennt: {addr[0]}:{addr[1]} (Verbleibend: {count}/{self.max_connections})")
        try:
            sock.close()
        except Exception:
            pass

    def _handle_command(self, cmd: str) -> str | None:
        cmd_lower = cmd.lower()

        # Login / Auth: "user <username>"
        if cmd_lower.startswith("user"):
            return "00A"

        # Abfrage Bruttogewicht + Einheit: "read wt0101 wt0103"
        if "read wt0101 wt0103" in cmd_lower:
            wt, unit, stable, err = self.state.get_reading()
            if err:
                return "99E453~Scale hardware error~kg~D"
            st_flag = "S" if stable else "D"
            # Format: 00R453~14780~kg~S
            return f"00R453~{wt:.1f}~{unit}~{st_flag}"

        # Abfrage nur Bruttogewicht: "read wt0101"
        if "read wt0101" in cmd_lower:
            wt, unit, stable, err = self.state.get_reading()
            if err:
                return "99E453~Scale hardware error"
            st_flag = "S" if stable else "D"
            return f"00R453~{wt:.1f}~{st_flag}"

        # Abfrage Einheit: "read wt0103"
        if "read wt0103" in cmd_lower:
            wt, unit, stable, err = self.state.get_reading()
            return f"00R453~{unit}"

        # Verbindung beenden: "quit"
        if cmd_lower == "quit":
            return "00"

        # Unbekannter Befehl
        return "99E Unknown command"

    def get_status_summary(self) -> str:
        wt, unit, stable, err = self.state.get_reading()
        st_text = "Stabil (S)" if stable else "In Bewegung (D)"
        err_text = "JA (Fehlercode 99)" if err else "Nein"
        with self.clients_lock:
            client_count = len(self.clients)
            client_list = [f"{c['addr'][0]}:{c['addr'][1]}" for c in self.clients.values()]

        lines = [
            f"  Aktuelles Gewicht : {wt:.1f} {unit}",
            f"  Status            : {st_text}",
            f"  Fehlermodus       : {err_text}",
            f"  Aktive Verbindungen: {client_count}/{self.max_connections}",
        ]
        if client_list:
            lines.append(f"  Clients           : {', '.join(client_list)}")
        return "\n".join(lines)


def print_interactive_help():
    print("""
======================== INTERAKTIVE BEFEHLE ========================
  <zahl>          - Setzt das Gewicht direkt (z. B. 15000 oder 2450.5)
  w / weight <n>  - Setzt das Gewicht auf <n> kg
  0 / zero        - Setzt das Gewicht auf 0.0 kg (Nullpunkt)
  drop / abort    - Bricht alle aktiven Verbindungen sofort ab
  drop <idx>      - Bricht Verbindung von Client #<idx> ab (z. B. drop 1)
  s / stable      - Setzt Gewicht-Status auf STABIL ('S')
  d / dynamic     - Setzt Gewicht-Status auf IN BEWEGUNG ('D')
  err / error     - Schaltet den simulierten Fehlermodus ein/aus
  c / clients     - Zeigt alle verbundenen Clients mit Details
  status          - Zeigt aktuellen Status und Werte
  help / ?        - Zeigt diese Hilfe
  quit / exit     - Beendet den Simulator
=====================================================================
""")


def parse_number(text: str) -> float | None:
    """Parst eine Zahl (unterstützt Punkt und Komma als Dezimaltrenner)."""
    text = text.strip().replace(",", ".")
    try:
        val = float(text)
        if val >= 0:
            return val
    except ValueError:
        pass
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Mettler Toledo IND570 SD Server Simulator für LKW-Waage.",
        epilog="""
Beispiele:
  python sim/scale_sim.py --host 0.0.0.0 --port 1701
  python sim/scale_sim.py -H 127.0.0.1 -p 1701 --weight 12500
  python sim/scale_sim.py -H 0.0.0.0 -p 1701 --max-connections 5 --timeout 300
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Zwingende Argumente
    req_group = parser.add_argument_group("Zwingend erforderliche Konfiguration")
    req_group.add_argument(
        "-H", "--host",
        required=True,
        type=str,
        help="IP-Adresse oder Hostname, an den der Server gebunden wird (z. B. 0.0.0.0 oder 127.0.0.1)",
    )
    req_group.add_argument(
        "-p", "--port",
        required=True,
        type=int,
        help="TCP-Port für den SD Server (z. B. 1701)",
    )

    # Optionale Argumente
    opt_group = parser.add_argument_group("Optionale Parameter")
    opt_group.add_argument(
        "-w", "--weight",
        type=float,
        default=0.0,
        help="Initiales Gewicht in kg (Standard: 0.0)",
    )
    opt_group.add_argument(
        "-u", "--unit",
        type=str,
        default="kg",
        help="Gewichtseinheit (Standard: kg)",
    )
    opt_group.add_argument(
        "-m", "--max-connections",
        type=int,
        default=5,
        help="Maximale Anzahl gleichzeitiger Verbindungen (Standard: 5)",
    )
    opt_group.add_argument(
        "-t", "--timeout",
        type=int,
        default=300,
        help="Inaktivitäts-Timeout pro Verbindung in Sekunden (Standard: 300)",
    )
    opt_group.add_argument(
        "--unstable",
        action="store_true",
        help="Startet mit Status 'in Bewegung' ('D') statt 'stabil' ('S')",
    )

    args = parser.parse_args()

    state = ScaleState(initial_weight=args.weight, unit=args.unit, stable=not args.unstable)
    sim = ScaleSimulator(
        host=args.host,
        port=args.port,
        state=state,
        max_connections=args.max_connections,
        timeout=args.timeout,
    )
    sim.start()

    print("\n" + "=" * 65)
    print("  IND570 Waagen-Simulator bereit.")
    print(sim.get_status_summary())
    print("  Geben Sie jederzeit ein neues Gewicht ein (nur Zahlen).")
    print("  Befehle: 'drop' (Verbindung abbrechen), 'status', 'quit' (Beenden)")
    print("=" * 65 + "\n")

    try:
        while True:
            current_wt, unit, _, _ = state.get_reading()
            try:
                line = input(f"Gewicht eingeben in {unit} [Aktuell: {current_wt:.1f} {unit}]: ").strip()
            except EOFError:
                break

            if not line:
                continue

            cmd_lower = line.lower()

            if cmd_lower in ("exit", "quit", "q"):
                print("Beende Simulator...")
                break

            if cmd_lower in ("drop", "disconnect", "abort"):
                sim.disconnect_all("Manuell ueber Terminal getrennt")
                print(">> [VERBINDUNG ABGEBROCHEN] Alle aktiven Verbindungen wurden getrennt.\n")
                continue

            if cmd_lower == "status":
                print("\n================ STATUS ================")
                print(sim.get_status_summary())
                print("========================================\n")
                continue

            if cmd_lower in ("help", "?"):
                print("""
  Bedienung:
    <Zahl>      - Setzt das Gewicht direkt (z. B. 0, 500, 15000 oder 28500.5)
    drop        - Bricht alle aktiven Verbindungen ab
    status      - Zeigt aktuellen Status und verbundene Clients
    quit        - Beendet den Simulator
""")
                continue

            # Validierung: Nur Zahlen akzeptieren
            num = parse_number(line)
            if num is None:
                print(f">> [FEHLER] Ungueltige Eingabe '{line}'! Es werden nur Zahlen akzeptiert (z. B. 0, 15000 oder 2450.5).\n")
            else:
                state.set_weight(num)
                print(f">> [OK] Gewicht erfolgreich auf {num:.1f} {unit} geaendert.\n")

    except KeyboardInterrupt:
        print("\nAbbruch durch Benutzer...")
    finally:
        sim.stop()


if __name__ == "__main__":
    main()
