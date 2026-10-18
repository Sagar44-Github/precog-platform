"""The experiment log: one row per model per run, kept in results/experiments.csv (PRD FR-DET-6)."""
import csv
from datetime import datetime, timezone
from pathlib import Path

COLUMNS = [
    "timestamp_utc", "split", "model", "n_features", "smote", "seed", "train_rows", "test_rows",
    "precision", "recall", "f1", "false_positive_rate", "macro_f1", "unseen_detection_rate", "seconds", "notes",
]


class ExperimentLog:
    def __init__(self, path):
        self.path = Path(path)

    def add(self, **fields):
        unknown = set(fields) - set(COLUMNS)
        if unknown:
            raise ValueError("Unknown experiment log columns: %s" % sorted(unknown))
        row = {c: "" for c in COLUMNS}
        row["timestamp_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for key, value in fields.items():
            if isinstance(value, float):
                value = round(value, 4)
            row[key] = "" if value is None else value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not self.path.is_file() or self.path.stat().st_size == 0
        with self.path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
            if new_file:
                writer.writeheader()
            writer.writerow(row)
        return row

    def rows(self):
        if not self.path.is_file():
            return []
        with self.path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
