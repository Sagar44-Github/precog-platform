"""Rebuilds detect_events/data/attack_techniques.json from MITRE's official ATT&CK data.

Only needed if you want to add techniques or move to a newer ATT&CK version.

  1. Download enterprise-attack.json from
     https://github.com/mitre-attack/attack-stix-data  (folder enterprise-attack)
  2. python detect/tools/build_attack_table.py PATH_TO/enterprise-attack.json

Edit TECHNIQUE_IDS and PORT_HINTS below to change the table.
"""
import json
import sys
from pathlib import Path

OUT_FILE = Path(__file__).resolve().parents[1] / "detect_events" / "data" / "attack_techniques.json"

TECHNIQUE_IDS = [
    "T1046", "T1110", "T1110.001", "T1110.003", "T1078", "T1021", "T1021.001", "T1021.002", "T1021.003",
    "T1021.004", "T1571", "T1048", "T1041", "T1059", "T1087", "T1018", "T1083", "T1005", "T1560", "T1003",
    "T1570", "T1105", "T1190", "T1135", "T1133", "T1068",
]
# Service-based hints for the ports NIDS treats as suspicious. None = no defensible mapping.
PORT_HINTS = {
    "22": "T1021.004", "23": "T1021", "3389": "T1021.001", "445": "T1021.002", "135": "T1021.003",
    "137": None, "138": None, "139": "T1021.002", "4444": "T1571", "6666": "T1571", "31337": "T1571",
}
NOTICE = (
    "(c) The MITRE Corporation. ATT&CK(R) is a registered trademark of The MITRE Corporation. Technique names and "
    "tactics are reproduced from https://attack.mitre.org under the ATT&CK Terms of Use: "
    "https://attack.mitre.org/resources/legal-and-branding/terms-of-use/"
)


def build_table(bundle, technique_ids=TECHNIQUE_IDS, port_hints=PORT_HINTS):
    objects = bundle["objects"]
    collection = [o for o in objects if o.get("type") == "x-mitre-collection"]
    version = collection[0].get("x_mitre_version", "unknown") if collection else "unknown"
    by_id = {}
    for obj in objects:
        if obj.get("type") != "attack-pattern":
            continue
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack":
                by_id[ref["external_id"]] = obj
    techniques = []
    for technique_id in technique_ids:
        obj = by_id.get(technique_id)
        if obj is None:
            raise SystemExit("Technique %s was not found in the ATT&CK data." % technique_id)
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            raise SystemExit("Technique %s is revoked or deprecated in this ATT&CK version." % technique_id)
        techniques.append({
            "id": technique_id,
            "name": obj["name"],
            "tactics": [phase["phase_name"] for phase in obj.get("kill_chain_phases", [])],
            "url": "https://attack.mitre.org/techniques/%s/" % technique_id.replace(".", "/"),
        })
    return {
        "meta": {
            "source": "MITRE ATT&CK Enterprise, version %s" % version,
            "source_data": "https://github.com/mitre-attack/attack-stix-data (enterprise-attack/enterprise-attack.json)",
            "notice": NOTICE,
            "curated": "A small hand-picked subset (%d techniques) used by this project. Rebuild with detect/tools/build_attack_table.py." % len(techniques),
            "port_hints_note": "Service-based hints only. A port number alone does not prove a technique. null means no defensible mapping, so no technique is shown.",
        },
        "port_hints": port_hints,
        "techniques": techniques,
    }


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 1
    bundle = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    table = build_table(bundle)
    OUT_FILE.write_text(json.dumps(table, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Wrote %d techniques to %s" % (len(table["techniques"]), OUT_FILE))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
