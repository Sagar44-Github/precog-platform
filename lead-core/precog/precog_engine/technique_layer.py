"""The technique-level hint: "which ATT&CK technique is likely next?" (TRD DD-9).

Two tables, both plain JSON files read at start-up (nothing from the forecasting repository is imported by the backend):
  technique_markov.json  exported ONCE from the repository mayank02raj/MITRE-ATTACK-based-Attack-Chain-Prediction (tools/export_technique_markov.py)
  technique_lookup.json  a hand-written rule table, the fallback
The forecast records which one produced its hint ("repo" or "lookup").
"""
import json
from pathlib import Path


def _parent(technique_id):
    return technique_id.split(".")[0]


class TechniqueLayer:
    def __init__(self, markov=None, lookup=None, prefer="repo"):
        """markov: parsed technique_markov.json or None. lookup: parsed technique_lookup.json or None. prefer: "repo" or "lookup"."""
        self.markov, self.lookup, self.prefer = markov, lookup, prefer

    @classmethod
    def load(cls, markov_path, lookup_path, prefer="repo"):
        def read(path):
            path = Path(path)
            return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

        return cls(read(markov_path), read(lookup_path), prefer)

    @property
    def default_source(self):
        return "repo" if (self.prefer == "repo" and self.markov) else "lookup"

    def _from_markov(self, technique_id):
        table = self.markov["next_prob"]
        for key in (technique_id, _parent(technique_id)):
            row = table.get(key)
            if row:
                best = max(row.items(), key=lambda kv: (kv[1], kv[0]))
                return {"technique_id": best[0], "technique_name": self.markov["names"].get(best[0], best[0]), "probability": round(best[1], 4)}
        return None

    def _from_lookup(self, technique_id):
        table = self.lookup["next"]
        for key in (technique_id, _parent(technique_id)):
            row = table.get(key)
            if row:
                best = row[0]
                return {"technique_id": best["id"], "technique_name": self.lookup["names"].get(best["id"], best["id"]), "probability": round(best["probability"], 4)}
        return None

    def hint(self, technique_id):
        """(hint or None, source). The sub-technique is tried first, then its parent. If the preferred table has nothing, the other is tried."""
        if not technique_id:
            return None, self.default_source
        order = [("repo", self.markov, self._from_markov), ("lookup", self.lookup, self._from_lookup)]
        if self.prefer == "lookup":
            order.reverse()
        for source, table, finder in order:
            if table:
                found = finder(technique_id)
                if found:
                    return found, source
        return None, self.default_source
