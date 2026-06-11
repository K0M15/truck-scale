import socket
import sys
import threading
import time
from dataclasses import dataclass


@dataclass
class QRScan:
    qr_id: str
    weight: float


class ScannerClient:

    def __init__(self, host, port=4001, weight_provider=None, simulate=False):
        self.host = host
        self.port = port
        self.weight_provider = weight_provider
        self.simulate = simulate
        self._running = False
        self._thread = None
        self._on_scan = None
        self._sim_count = 0

    def on_scan(self, callback):
        self._on_scan = callback

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        if self.simulate:
            self._run_simulate()
        else:
            self._run_tcp()

    def _run_simulate(self):
        while self._running:
            time.sleep(12)
            if self._running:
                self._sim_count += 1
                weight = self.weight_provider() if self.weight_provider else 0.0
                qr_id = f"SIM-{self._sim_count:04d}"
                if self._on_scan:
                    self._on_scan(QRScan(qr_id, weight))

    def _run_tcp(self):
        while self._running:
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10)
                sock.connect((self.host, self.port))

                buffer = b""
                while self._running:
                    try:
                        data = sock.recv(1024)
                        if not data:
                            break
                        buffer += data
                        lines = buffer.split(b"\n")
                        buffer = lines.pop()
                        for line in lines:
                            line = line.strip(b"\r")
                            if not line:
                                continue
                            qr_id = line.decode("utf-8", errors="replace").strip()
                            if qr_id and self._on_scan:
                                weight = self.weight_provider() if self.weight_provider else 0.0
                                self._on_scan(QRScan(qr_id, weight))
                    except socket.timeout:
                        continue
            except (ConnectionRefusedError, OSError) as e:
                print(f"[Scanner] Connection error: {e}", file=sys.stderr)
            except Exception as e:
                print(f"[Scanner] Unexpected error: {e}", file=sys.stderr)
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
            if self._running:
                time.sleep(10)
