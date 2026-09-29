"""
Automatisierter Integrationstest fuer die beiden Simulatoren:
- scale_sim.py (Mettler Toledo IND570 SD Server)
- scanner_sim.py (FM3080 QR-Code Scanner)
"""
import time
import socket
import threading
from sim.scale_sim import ScaleSimulator, ScaleState
from sim.scanner_sim import ScannerSimulator


def test_scale_simulator():
    print("\n--- TEST: scale_sim (Waagen-Simulator) ---")
    state = ScaleState(initial_weight=14500.0, unit="kg", stable=True)
    sim = ScaleSimulator(host="127.0.0.1", port=11701, state=state, max_connections=5, timeout=2)
    sim.start()
    time.sleep(0.5)

    # 1. Verbindung und Login
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 11701))
    s.sendall(b"user anonymous\r\n")
    resp = s.recv(1024).decode().strip()
    assert resp == "00A", f"Login Antwort falsch: {resp}"
    print("[PASS] Login erfolgreich: 00A")

    # 2. Gewicht abfragen
    s.sendall(b"read wt0101 wt0103\r\n")
    resp = s.recv(1024).decode().strip()
    assert "00R453~14500.0~kg~S" in resp, f"Gewichtsabfrage falsch: {resp}"
    print(f"[PASS] Gewichtsabfrage: {resp}")

    # 3. Gewicht aendern
    state.set_weight(28950.5)
    s.sendall(b"read wt0101 wt0103\r\n")
    resp = s.recv(1024).decode().strip()
    assert "00R453~28950.5~kg~S" in resp, f"Geaendertes Gewicht falsch: {resp}"
    print(f"[PASS] Gewichtsaenderung auf 28950.5 kg: {resp}")

    # 4. Gewicht auf Null setzen
    state.set_zero()
    s.sendall(b"read wt0101 wt0103\r\n")
    resp = s.recv(1024).decode().strip()
    assert "00R453~0.0~kg~S" in resp, f"Nullgewicht falsch: {resp}"
    print(f"[PASS] Gewicht auf Null: {resp}")

    # 5. Maximale Verbindungen (max 5)
    extra_socks = []
    for i in range(4): # Bereits 1 verbunden, also noch 4 dazu = 5
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", 11701))
        extra_socks.append(sock)
    time.sleep(0.2)
    with sim.clients_lock:
        assert len(sim.clients) == 5, f"Clients sollten 5 sein, sind {len(sim.clients)}"
    print(f"[PASS] 5 gleichzeitige Verbindungen aktiv.")

    # 6. Verbindung sollte abgewiesen werden
    rejected_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rejected_sock.connect(("127.0.0.1", 11701))
    resp = rejected_sock.recv(1024).decode().strip()
    assert "99E" in resp or not resp, f"6. Client sollte 99E erhalten, bekam: {resp}"
    print(f"[PASS] 6. Verbindung abgewiesen: {resp}")
    rejected_sock.close()

    # 6. Verbindungsabbruch testen (drop / disconnect)
    sim.disconnect_all("Test disconnect")
    time.sleep(0.2)
    # Check that socket was closed
    chunk = s.recv(1024)
    assert not chunk, "Socket sollte nach Verbindungsabbruch geschlossen sein"
    print("[PASS] Verbindung abgebrochen erfolgreich simuliert.")

    s.close()
    for es in extra_socks:
        es.close()
    sim.stop()
    print("[PASS] scale_sim alle Tests bestanden!\n")


def test_scanner_simulator():
    print("\n--- TEST: scanner_sim (Scanner-Simulator) ---")
    sim = ScannerSimulator(host="127.0.0.1", port=14001)
    sim.start()
    time.sleep(0.5)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 14001))
    time.sleep(0.2)

    # 1. Scan senden
    sim.send_scan("LKW-TEST-12345")
    data = s.recv(1024).decode().strip()
    assert data == "LKW-TEST-12345", f"Unerwarteter Scan: {data}"
    print(f"[PASS] Scan empfangen: {data}")

    # 2. Weiteren Scan mit Zahl senden
    sim.send_scan("9876543210")
    data = s.recv(1024).decode().strip()
    assert data == "9876543210", f"Unerwarteter Scan: {data}"
    print(f"[PASS] Scan mit Nummer empfangen: {data}")

    # 3. Verbindungsabbruch testen
    sim.disconnect_all("Test disconnect")
    time.sleep(0.2)
    chunk = s.recv(1024)
    assert not chunk, "Socket sollte nach drop geschlossen sein"
    print("[PASS] Scanner Verbindungsabbruch erfolgreich simuliert.")

    s.close()
    sim.stop()
    print("[PASS] scanner_sim alle Tests bestanden!\n")


if __name__ == "__main__":
    test_scale_simulator()
    test_scanner_simulator()
    print("========================================")
    print("  ALLE SIMULATOR-TESTS ERFOLGREICH!")
    print("========================================")
