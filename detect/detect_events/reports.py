"""Loads DETECT's offline evaluation result (detection_report.json) so the product can show it."""
import json
from pathlib import Path


def load_detection_report(path, contracts=None):
    """Return the report dict, or None if the file does not exist yet. A report that breaks its contract raises."""
    path = Path(path)
    if not path.is_file():
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    if contracts is not None:
        contracts.validate("detection_report", report)
    return report
