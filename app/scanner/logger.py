import csv
import hashlib
import threading
from datetime import datetime, date, timedelta
from pathlib import Path


CSV_HEADER = [
    "timestamp", "qr_id", "weight_scan",
    "einwaage", "auswaage", "netto", "hash",
    "license_plate", "company", "product",
    "reason", "status",
]

COL_TIMESTAMP = 0
COL_QR_ID = 1
COL_WEIGHT_SCAN = 2
COL_EINWAAGE = 3
COL_AUSWAAGE = 4
COL_NETTO = 5
COL_HASH = 6
COL_LP = 7
COL_COMPANY = 8
COL_PRODUCT = 9
COL_REASON = 10
COL_STATUS = 11


def _compute_hash(ein, aus, netto):
    raw = f"{ein}|{aus}|{netto}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _netto_from(ein, aus):
    if ein > aus:
        return round(ein - aus, 1)
    return round(aus - ein, 1)


class QRScanLogger:

    def __init__(self, log_dir="logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._current_date = None
        self._file = None
        self._writer = None

    def _rotate(self, today):
        if today == self._current_date:
            return
        if self._file:
            self._file.close()
        self._current_date = today
        filename = self._path(today)
        file_exists = filename.exists()
        self._file = open(filename, "a", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        if not file_exists:
            self._writer.writerow(CSV_HEADER)

    def _path(self, d):
        return self.log_dir / f"scans_{d.isoformat()}.csv"

    # ── logging + auto-pairing ──────────────────────────────

    def log(self, qr_id, weight):
        now = datetime.now()
        w = round(weight, 1)

        with self._lock:
            pair = self._try_pair(qr_id, w)
            if pair:
                return pair

            self._rotate(now.date())
            self._writer.writerow([
                now.isoformat(timespec="seconds"),
                qr_id, w,
                w, 0.0, 0.0, "",
                "", "", "",
                "", "open",
            ])
            self._file.flush()
        return None

    def _try_pair(self, qr_id, weight):
        for days_ago in range(365):
            d = date.today() - timedelta(days=days_ago)
            fp = self._path(d)
            if not fp.exists():
                continue
            rows = []
            header = []
            paired = False
            with open(fp, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader)
                for row in reader:
                    if (
                        not paired
                        and len(row) > COL_AUSWAAGE
                        and row[COL_QR_ID] == qr_id
                        and (row[COL_AUSWAAGE] == "" or float(row[COL_AUSWAAGE]) == 0.0)
                    ):
                        while len(row) < len(CSV_HEADER):
                            row.append("")
                        ein = float(row[COL_EINWAAGE])
                        aus = weight
                        netto = _netto_from(ein, aus)
                        row[COL_AUSWAAGE] = str(aus)
                        row[COL_NETTO] = str(netto)
                        row[COL_HASH] = _compute_hash(ein, aus, netto)
                        paired = True
                    rows.append(row)
            if paired:
                with open(fp, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(header)
                    w.writerows(rows)
                return rows[-1] if rows else None
        return None

    # ── read ────────────────────────────────────────────────

    def get_scans(self, date_str):
        fp = self._path(date.fromisoformat(date_str))
        if not fp.exists():
            return []
        entries = []
        with self._lock:
            with open(fp, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    def _g(i, default=""):
                        return row[i] if len(row) > i else default
                    entries.append({
                        "time": _g(COL_TIMESTAMP),
                        "qr_id": _g(COL_QR_ID),
                        "weight_scan": _g(COL_WEIGHT_SCAN),
                        "einwaage": _g(COL_EINWAAGE),
                        "auswaage": _g(COL_AUSWAAGE),
                        "netto": _g(COL_NETTO),
                        "hash": _g(COL_HASH),
                        "license_plate": _g(COL_LP),
                        "company": _g(COL_COMPANY),
                        "product": _g(COL_PRODUCT),
                        "reason": _g(COL_REASON),
                        "status": _g(COL_STATUS, "open"),
                    })
        return entries

    # ── update ──────────────────────────────────────────────

    def update(self, timestamp, **kwargs):
        date_part = timestamp[:10]
        fp = self._path(date.fromisoformat(date_part))
        if not fp.exists():
            return False

        with self._lock:
            rows = []
            header = []
            updated = False

            with open(fp, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader)
                for row in reader:
                    if row[COL_TIMESTAMP] == timestamp:
                        while len(row) < len(CSV_HEADER):
                            row.append("")

                        old_ein = float(row[COL_EINWAAGE]) if row[COL_EINWAAGE] else 0.0
                        old_aus = float(row[COL_AUSWAAGE]) if row[COL_AUSWAAGE] else 0.0

                        if "license_plate" in kwargs:
                            row[COL_LP] = kwargs["license_plate"]
                        if "company" in kwargs:
                            row[COL_COMPANY] = kwargs["company"]
                        if "product" in kwargs:
                            row[COL_PRODUCT] = kwargs["product"]
                        if "status" in kwargs:
                            row[COL_STATUS] = kwargs["status"]

                        if "einwaage" in kwargs:
                            row[COL_EINWAAGE] = str(kwargs["einwaage"])
                        if "auswaage" in kwargs:
                            row[COL_AUSWAAGE] = str(kwargs["auswaage"])

                        new_ein = float(row[COL_EINWAAGE]) if row[COL_EINWAAGE] else 0.0
                        new_aus = float(row[COL_AUSWAAGE]) if row[COL_AUSWAAGE] else 0.0

                        if new_ein != old_ein or new_aus != old_aus:
                            netto = _netto_from(new_ein, new_aus)
                            row[COL_NETTO] = str(netto)
                            reason = kwargs.get("reason", "")
                            if reason:
                                row[COL_REASON] = reason
                            row[COL_HASH] = "CHANGED"
                        else:
                            netto = _netto_from(new_ein, new_aus)
                            row[COL_NETTO] = str(netto)
                            if not row[COL_HASH]:
                                row[COL_HASH] = _compute_hash(new_ein, new_aus, netto)

                        updated = True
                    rows.append(row)

            if not updated:
                return False

            with open(fp, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(header)
                w.writerows(rows)
        return True

    def close(self):
        if self._file:
            self._file.close()
            self._file = None
