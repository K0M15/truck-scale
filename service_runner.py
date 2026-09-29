"""
Service Watchdog / Runner for Landliebe Waage.
Runs 'python -m app.main' as a child process and automatically restarts it if it crashes.
Supports clean termination via SIGINT/SIGTERM and writes restart logs.
"""
import os
import sys
import time
import signal
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
WATCHDOG_LOG = LOG_DIR / "watchdog.log"


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [Watchdog] {msg}"
    print(line, flush=True)
    try:
        with open(WATCHDOG_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run_supervisor():
    os.chdir(PROJECT_ROOT)
    log(f"Starting Landliebe Waage Supervisor (Python: {PYTHON_EXE})...")

    running = True
    current_process = None

    def handle_signal(sig, frame):
        nonlocal running
        log("Received stop signal, shutting down child process...")
        running = False
        if current_process and current_process.poll() is None:
            current_process.terminate()
            try:
                current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                current_process.kill()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    consecutive_rapid_crashes = 0
    RESTART_DELAY = 3  # seconds

    while running:
        start_time = time.time()
        log("Starting server process: python -m app.main")
        try:
            current_process = subprocess.Popen(
                [str(PYTHON_EXE), "-m", "app.main"],
                cwd=str(PROJECT_ROOT),
            )
            current_process.wait()
            exit_code = current_process.returncode
        except Exception as e:
            log(f"Error launching process: {e}")
            exit_code = -1

        run_duration = time.time() - start_time

        if not running:
            log(f"Supervisor stopped cleanly. Child exited with code {exit_code}.")
            break

        if run_duration < 5:
            consecutive_rapid_crashes += 1
            delay = min(RESTART_DELAY * (2 ** (consecutive_rapid_crashes - 1)), 60)
            log(f"Process crashed quickly (ran for {run_duration:.1f}s, exit code {exit_code}). Backing off for {delay}s...")
        else:
            consecutive_rapid_crashes = 0
            delay = RESTART_DELAY
            log(f"Process exited (ran for {run_duration:.1f}s, exit code {exit_code}). Restarting in {delay}s...")

        # Sleep in small slices so we can still handle stop signals
        for _ in range(int(delay * 10)):
            if not running:
                break
            time.sleep(0.1)

    log("Supervisor shutdown complete.")


if __name__ == "__main__":
    run_supervisor()
