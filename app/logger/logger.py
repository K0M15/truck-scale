import csv
from datetime import datetime, date
from pathlib import Path


class WeightLogger:
    def __init__(self, log_dir="logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_date = None
        self._file = None
        self._writer = None

    def _rotate(self, today: date):
        if today == self._current_date:
            return

        if self._file:
            self._file.close()

        self._current_date = today
        filename = self.log_dir / f"weight_{today.isoformat()}.csv"
        file_exists = filename.exists()
        self._file = open(filename, "a", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)

        if not file_exists:
            self._writer.writerow(["timestamp", "weight_kg", "stable"])

    def log(self, weight: float, stable: bool = True):
        if weight <= 0:
            return

        now = datetime.now()
        self._rotate(now.date())
        self._writer.writerow([
            now.isoformat(timespec="milliseconds"),
            round(weight, 1),
            1 if stable else 0,
        ])
        self._file.flush()

    def close(self):
        if self._file:
            self._file.close()
            self._file = None
