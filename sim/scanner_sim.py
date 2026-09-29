#!/usr/bin/env python3
"""
FM3080 QR-Code / Barcode Scanner - TCP Server Simulator

Simuliert einen fest installierten QR-Code / Barcode-Scanner (z. B. Newland FM3080),
der als TCP-Server agiert. Der Server akzeptiert eingehende Verbindungen vom
ScannerClient der LKW-Waagen-Software und sendet bei jedem Scan eine Textzeile mit \r\n.

Verwendung:
    python sim/scanner_sim.py --host 0.0.0.0 --port 4001
    python sim/scanner_sim.py -H 127.0.0.1 -p 4001
    python sim/scanner_sim.py --help
"""

import sys
import time
import socket
import random
import threading
import argparse
from datetime import datetime


class ScannerSimulator:
    """TCP Server für QR-Code / Barcode Scanner Simulation."""

    def __init__(self, host: str, port: int, prefix: str = "", auto_interval: float = 0.0):
        self.host = host
        self.port = port
        self.prefix = prefix
        self.auto_interval = float(auto_interval)

        self.server_sock = None
        self.running = False
        self.clients = {}  # sock -> addr
        self.clients_lock = threading.Lock()
        self.scan_counter = 0

        self.auto_thread = None
        self.auto_running = False

    def log(self, msg: str):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] [Scanner-Sim] {msg}", flush=True)

    def start(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_sock.bind((self.host, self.port))
        except OSError as e:
            self.log(f"FEHLER: Port {self.port} konnte nicht gebunden werden ({e})")
            sys.exit(1)

        self.server_sock.listen(5)
        self.running = True
        self.log(f"QR-Code Scanner Simulator gestartet auf {self.host}:{self.port}")

        threading.Thread(target=self._accept_loop, daemon=True).start()

        if self.auto_interval > 0:
            self.start_auto(self.auto_interval)

    def stop(self):
        self.running = False
        self.stop_auto()
        self.disconnect_all("Simulator wird beendet")
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
        self.log("Scanner-Simulator gestoppt.")

    def disconnect_all(self, reason: str = "Manuell getrennt"):
        with self.clients_lock:
            socks = list(self.clients.keys())
            for sock in socks:
                addr = self.clients[sock]
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
                sock, addr = items[client_index]
                self.log(f"Verbindung zu Client #{client_index + 1} ({addr[0]}:{addr[1]}) abgebrochen")
                try:
                    sock.close()
                except Exception:
                    pass
                del self.clients[sock]
                return True
            return False

    def send_scan(self, qr_text: str) -> int:
        """Sendet einen QR-Code / Barcode an alle verbundenen Clients."""
        qr_text = qr_text.strip()
        if not qr_text:
            return 0

        self.scan_counter += 1
        data = f"{qr_text}\r\n".encode("utf-8")
        sent_count = 0

        with self.clients_lock:
            dead_socks = []
            for sock, addr in self.clients.items():
                try:
                    sock.sendall(data)
                    sent_count += 1
                except Exception as e:
                    self.log(f"Senden an {addr[0]}:{addr[1]} fehlgeschlagen: {e}")
                    dead_socks.append(sock)

            for ds in dead_socks:
                try:
                    ds.close()
                except Exception:
                    pass
                if ds in self.clients:
                    del self.clients[ds]

        if sent_count > 0:
            self.log(f"Scan gesendet [#{self.scan_counter}]: '{qr_text}' an {sent_count} Client(s)")
        else:
            self.log(f"Scan erzeugt [#{self.scan_counter}]: '{qr_text}' (keine Clients verbunden!)")
        return sent_count

    def start_auto(self, interval_sec: float):
        self.stop_auto()
        self.auto_interval = float(interval_sec)
        self.auto_running = True
        self.auto_thread = threading.Thread(target=self._auto_loop, daemon=True)
        self.auto_thread.start()
        self.log(f"Auto-Scan aktiviert: alle {self.auto_interval:.1f}s")

    def stop_auto(self):
        if self.auto_running:
            self.auto_running = False
            self.log("Auto-Scan deaktiviert.")

    def _auto_loop(self):
        sample_prefixes = ["LKW-DE", "TRUCK-NL", "SCAN", "CARGO", "DELIVERY"]
        while self.running and self.auto_running:
            time.sleep(self.auto_interval)
            if not self.running or not self.auto_running:
                break
            pfx = self.prefix if self.prefix else random.choice(sample_prefixes)
            num = random.randint(1000, 9999)
            code = f"{pfx}-{num}"
            self.send_scan(code)

    def _accept_loop(self):
        while self.running:
            try:
                sock, addr = self.server_sock.accept()
            except OSError:
                break

            with self.clients_lock:
                self.clients[sock] = addr
                count = len(self.clients)
                self.log(f"Scanner-Client verbunden: {addr[0]}:{addr[1]} (Aktive Clients: {count})")

            # Client Überwachungsthread
            threading.Thread(target=self._client_monitor, args=(sock, addr), daemon=True).start()

    def _client_monitor(self, sock: socket.socket, addr):
        while self.running:
            try:
                sock.settimeout(2.0)
                data = sock.recv(1024)
                if not data:
                    break
            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError):
                break
            except Exception:
                break

        with self.clients_lock:
            if sock in self.clients:
                del self.clients[sock]
                count = len(self.clients)
                self.log(f"Scanner-Client getrennt: {addr[0]}:{addr[1]} (Verbleibend: {count})")
        try:
            sock.close()
        except Exception:
            pass

    def get_status_summary(self) -> str:
        with self.clients_lock:
            client_count = len(self.clients)
            client_list = [f"{addr[0]}:{addr[1]}" for addr in self.clients.values()]

        auto_status = f"Aktiv (alle {self.auto_interval}s)" if self.auto_running else "Inaktiv"
        lines = [
            f"  Server-Adresse     : {self.host}:{self.port}",
            f"  Verbundene Clients : {client_count}",
            f"  Gesendete Scans    : {self.scan_counter}",
            f"  Auto-Scan          : {auto_status}",
        ]
        if client_list:
            lines.append(f"  Clients            : {', '.join(client_list)}")
        return "\n".join(lines)


def print_interactive_help():
    print("""
======================== INTERAKTIVE BEFEHLE ========================
  <text / nummer>  - Sendet diesen QR-Code / Text sofort an alle Clients
                     (z. B. '12345' oder 'LKW-M-9876' oder 'QR-450')
  drop             - Bricht alle aktiven Client-Verbindungen sofort ab
  drop <idx>       - Bricht Verbindung zu Client #<idx> ab (z. B. drop 1)
  c / clients      - Zeigt alle verbundenen Scanner-Clients
  status           - Zeigt aktuellen Status des Simulators
  help / ?         - Zeigt diese Hilfe
  quit / exit      - Beendet den Scanner-Simulator
=====================================================================
""")


def main():
    parser = argparse.ArgumentParser(
        description="FM3080 QR-Code / Barcode Scanner TCP Simulator.",
        epilog="""
Beispiele:
  python sim/scanner_sim.py --host 0.0.0.0 --port 4001
  python sim/scanner_sim.py -H 127.0.0.1 -p 4001
  python sim/scanner_sim.py -H 0.0.0.0 -p 4001 --prefix QR-
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Zwingende Argumente
    req_group = parser.add_argument_group("Zwingend erforderliche Konfiguration")
    req_group.add_argument(
        "-H", "--host",
        required=True,
        type=str,
        help="IP-Adresse oder Hostname, an den der Scanner gebunden wird (z. B. 0.0.0.0 oder 127.0.0.1)",
    )
    req_group.add_argument(
        "-p", "--port",
        required=True,
        type=int,
        help="TCP-Port für den Scanner (z. B. 4001)",
    )

    # Optionale Argumente
    opt_group = parser.add_argument_group("Optionale Parameter")
    opt_group.add_argument(
        "--prefix",
        type=str,
        default="",
        help="Optionales Standard-Präfix für Scans (z. B. 'QR-')",
    )

    args = parser.parse_args()

    sim = ScannerSimulator(
        host=args.host,
        port=args.port,
        prefix=args.prefix,
    )
    sim.start()

    print("\n" + "=" * 65)
    print("  QR-Code Scanner Simulator bereit.")
    print(sim.get_status_summary())
    print("  Geben Sie jederzeit einen QR-Code / eine Nummer ein.")
    print("  Ein Scan wird NUR gesendet, wenn eine Eingabe getaetigt wird.")
    print("  Befehle: 'drop' (Verbindung abbrechen), 'status', 'quit' (Beenden)")
    print("=" * 65 + "\n")

    try:
        while True:
            with sim.clients_lock:
                client_count = len(sim.clients)

            try:
                line = input(f"QR-Code / Nummer scannen [Verbundene Clients: {client_count}]: ").strip()
            except EOFError:
                break

            if not line:
                continue

            parts = line.split()
            cmd = parts[0].lower()

            if cmd in ("exit", "quit", "q"):
                print("Beende Scanner-Simulator...")
                break

            if cmd in ("help", "?"):
                print_interactive_help()
                continue

            if cmd in ("drop", "abort", "disconnect"):
                if len(parts) > 1:
                    try:
                        idx = int(parts[1]) - 1
                        if sim.disconnect_client(idx):
                            print(f">> Verbindung #{parts[1]} getrennt.\n")
                        else:
                            print(f">> Client #{parts[1]} nicht gefunden.\n")
                    except ValueError:
                        print(">> Bitte gueltigen Index angeben (z. B. drop 1)\n")
                else:
                    sim.disconnect_all("Manuell ueber Terminal getrennt")
                    print(">> [VERBINDUNG ABGEBROCHEN] Alle Scanner-Verbindungen wurden getrennt.\n")
                continue

            if cmd in ("c", "clients"):
                with sim.clients_lock:
                    if not sim.clients:
                        print(">> Keine aktiven Verbindungen.\n")
                    else:
                        print(f">> Verbundene Clients ({len(sim.clients)}):")
                        for i, addr in enumerate(sim.clients.values(), 1):
                            print(f"   #{i} {addr[0]}:{addr[1]}")
                        print()
                continue

            if cmd == "status":
                print("\n================ STATUS ================")
                print(sim.get_status_summary())
                print("========================================\n")
                continue

            # Bei jeder sonstigen Eingabe: Scan sofort senden!
            qr_to_send = f"{args.prefix}{line}" if (args.prefix and not line.startswith(args.prefix)) else line
            sent = sim.send_scan(qr_to_send)
            if sent > 0:
                print(f">> [OK] Scan '{qr_to_send}' erfolgreich an {sent} Client(s) gesendet.\n")
            else:
                print(f">> [HINWEIS] Scan '{qr_to_send}' erzeugt, aber aktuell ist kein Client verbunden!\n")

    except KeyboardInterrupt:
        print("\nAbbruch durch Benutzer...")
    finally:
        sim.stop()


if __name__ == "__main__":
    main()
