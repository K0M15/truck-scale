import sys
import time
import signal
import threading
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from app.ind570.client import IND570Client
from app.logger.logger import WeightLogger
from app.web.routes import (
    app, socketio, push_weight, push_qr_scan, run_web, set_qr_logger,
)
from app.scanner.client import ScannerClient
from app.scanner.logger import QRScanLogger


def load_config(path="config.toml"):
    with open(path, "rb") as f:
        return tomllib.load(f)


def main():
    config = load_config()

    scale_cfg = config["ind570"]
    log_cfg = config["logger"]
    web_cfg = config["web"]
    poll_cfg = config["polling"]
    scanner_cfg = config.get("scanner", {})

    simulate = scale_cfg.get("simulate", False)
    ind570_port = scale_cfg.get("port", 1701)

    client = IND570Client(
        host=scale_cfg["host"],
        port=ind570_port,
        simulate=simulate,
    )

    logger = WeightLogger(log_dir=log_cfg.get("log_dir", "logs"))
    qr_logger = QRScanLogger(log_dir=log_cfg.get("log_dir", "logs"))
    set_qr_logger(qr_logger)

    web_thread = threading.Thread(
        target=run_web,
        args=(web_cfg.get("host", "0.0.0.0"), web_cfg.get("port", 8080)),
        daemon=True,
    )
    web_thread.start()

    latest_weight = 0.0

    scanner_sim = scanner_cfg.get("simulate", True)
    scanner = ScannerClient(
        host=scanner_cfg.get("host", "192.168.1.100"),
        port=scanner_cfg.get("port", 4001),
        weight_provider=lambda: latest_weight,
        simulate=scanner_sim,
    )

    def on_qr_scan(scan):
        nonlocal latest_weight
        w = latest_weight
        qr_logger.log(scan.qr_id, w)
        push_qr_scan(scan.qr_id, w)

    scanner.on_scan(on_qr_scan)
    scanner.start()
    if scanner_sim:
        print("[Scanner] SIMULATION mode (1 scan every 12s)")
    else:
        print(f"[Scanner] Connecting to {scanner_cfg.get('host')}:{scanner_cfg.get('port')}")

    poll_interval = poll_cfg.get("interval", 1.0)

    connected = False
    while not connected:
        try:
            client.connect()
            connected = client.connected
            if connected:
                mode = "SIMULATION" if simulate else "LIVE"
                print(f"[IND570] Connected ({mode}) to {scale_cfg['host']}:{ind570_port}")
        except Exception as e:
            print(f"[IND570] Connection failed: {e}", file=sys.stderr)
            push_weight(0.0, False, f"Connection failed: {e}")
            time.sleep(5)

    print(f"[Web] http://{web_cfg.get('host', '0.0.0.0')}:{web_cfg.get('port', 8080)}")
    print("[Main] Polling started (Ctrl+C to stop)")

    stop_event = threading.Event()

    def handle_signal(sig, frame):
        print("\n[Main] Shutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    while not stop_event.is_set():
        try:
            reading = client.read_weight()

            if reading.weight > 0:
                latest_weight = reading.weight

            if reading.error:
                push_weight(0.0, False, reading.error)
            else:
                push_weight(reading.weight, reading.stable, unit=reading.unit)

            if reading.weight > 0:
                logger.log(reading.weight, reading.stable)

            if not client.connected and not simulate:
                print(f"[IND570] Disconnected, reconnecting...", file=sys.stderr)
                try:
                    client.connect()
                except Exception as e:
                    print(f"[IND570] Reconnect failed: {e}", file=sys.stderr)

        except Exception as e:
            print(f"[Main] Error in poll loop: {e}", file=sys.stderr)
            push_weight(0.0, False, str(e))

        stop_event.wait(timeout=poll_interval)

    client.disconnect()
    scanner.stop()
    logger.close()
    qr_logger.close()
    print("[Main] Stopped.")


if __name__ == "__main__":
    main()
