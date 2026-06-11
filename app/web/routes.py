import csv
import os
import threading
from datetime import date, datetime
from pathlib import Path

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

_state_lock = threading.Lock()
_state = {
    "weight": 0.0,
    "unit": "kg",
    "stable": False,
    "error": None,
}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

LOG_DIR = Path("logs")

_qr_logger = None


def set_qr_logger(logger):
    global _qr_logger
    _qr_logger = logger


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/weight")
def api_weight():
    with _state_lock:
        return jsonify(dict(_state))


@app.route("/api/logs/dates")
def api_log_dates():
    dates = []
    if LOG_DIR.exists():
        for f in sorted(LOG_DIR.glob("weight_*.csv"), reverse=True):
            try:
                stem = f.stem
                d = stem.replace("weight_", "")
                date.fromisoformat(d)
                dates.append(d)
            except ValueError:
                pass
    return jsonify(dates)


@app.route("/api/logs")
def api_logs():
    d = request.args.get("date", date.today().isoformat())
    filepath = LOG_DIR / f"weight_{d}.csv"
    if not filepath.exists():
        return jsonify({"date": d, "entries": []})
    entries = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) >= 2:
                try:
                    ts = row[0]
                    wt = float(row[1])
                    st = row[2] == "1" if len(row) >= 3 else True
                    entries.append({"time": ts, "weight": wt, "stable": st})
                except (ValueError, IndexError):
                    continue
    return jsonify({"date": d, "entries": entries})


@app.route("/api/scans")
def api_scans():
    d = request.args.get("date", date.today().isoformat())
    if _qr_logger:
        entries = _qr_logger.get_scans(d)
        return jsonify({"date": d, "entries": entries})
    return jsonify({"date": d, "entries": []})


@app.route("/api/scans/update", methods=["PUT"])
def api_scan_update():
    data = request.get_json()
    if not data or "time" not in data:
        return jsonify({"ok": False, "error": "Missing 'time' field"}), 400
    ts = data["time"]
    lp = data.get("license_plate", "")
    co = data.get("company", "")
    pr = data.get("product", "")
    en = data.get("einwaage")
    au = data.get("auswaage")
    reason = data.get("reason", "")
    status = data.get("status", "")
    if _qr_logger:
        kw = {"license_plate": lp, "company": co, "product": pr}
        if en is not None:
            kw["einwaage"] = en
        if au is not None:
            kw["auswaage"] = au
        if reason:
            kw["reason"] = reason
        if status:
            kw["status"] = status
        ok = _qr_logger.update(ts, **kw)
        if ok:
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "Entry not found"}), 404
    return jsonify({"ok": False, "error": "Logger not available"}), 500


@app.route("/api/scans/approve", methods=["PUT"])
def api_scan_approve():
    data = request.get_json()
    if not data or "time" not in data:
        return jsonify({"ok": False, "error": "Missing 'time' field"}), 400
    if _qr_logger:
        ok = _qr_logger.update(data["time"], status="OK")
        if ok:
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "Entry not found"}), 404
    return jsonify({"ok": False, "error": "Logger not available"}), 500


def push_weight(weight: float, stable: bool, error: str | None = None, unit: str = "kg"):
    with _state_lock:
        _state["weight"] = weight
        _state["unit"] = unit
        _state["stable"] = stable
        _state["error"] = error
    socketio.emit("weight_update", _state)


def push_qr_scan(qr_id: str, weight: float):
    data = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "qr_id": qr_id,
        "weight_scan": str(round(weight, 1)),
        "einwaage": "",
        "auswaage": "",
        "netto": "",
        "hash": "",
        "license_plate": "",
        "company": "",
        "product": "",
        "reason": "",
        "status": "open",
    }
    socketio.emit("qr_scan", data)


def run_web(host: str, port: int):
    socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)
