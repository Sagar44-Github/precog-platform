"""The small table of MITRE ATT&CK techniques this project uses (data/attack_techniques.json)."""
import json
from pathlib import Path


class TechniqueTable:
    def __init__(self, data):
        self.meta = data.get("meta", {})
        self._techniques = {}
        for item in data["techniques"]:
            for key in ("id", "name", "tactics"):
                if key not in item:
                    raise ValueError("Technique entry without '%s': %r" % (key, item))
            if item["id"] in self._techniques:
                raise ValueError("Duplicate technique id: %s" % item["id"])
            self._techniques[item["id"]] = dict(item)
        self._port_hints = {}
        for port, technique_id in data.get("port_hints", {}).items():
            if technique_id is not None and technique_id not in self._techniques:
                raise ValueError("Port %s points to unknown technique %s" % (port, technique_id))
            self._port_hints[int(port)] = technique_id

    @classmethod
    def from_file(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def ids(self):
        return list(self._techniques)

    def get(self, technique_id):
        """The technique dict, or None if the id is not in our table."""
        return self._techniques.get(technique_id)

    def require(self, technique_id):
        found = self._techniques.get(technique_id)
        if found is None:
            raise ValueError("Unknown ATT&CK technique '%s'. Known ids: %s" % (technique_id, ", ".join(self._techniques)))
        return found

    def technique_for_port(self, port):
        """A service-based hint for a destination port, or None. A port alone never proves a technique."""
        technique_id = self._port_hints.get(port)
        return self._techniques[technique_id] if technique_id else None

    def hinted_ports(self):
        return sorted(self._port_hints)
