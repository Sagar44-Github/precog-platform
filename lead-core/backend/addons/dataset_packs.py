"""Offline dataset-pack validation, deterministic demo conversion, and read-only store."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from jsonschema import Draft202012Validator

PACK_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
PACK_MAX_BYTES = 25 * 1024 * 1024
SQLITE_COLUMNS = {
    "hosts": {"host_id", "display_name", "zone", "role", "criticality", "details_json"},
    "edges": {"src", "dst", "edge_kind", "count", "first_seen", "last_seen", "provenance"},
    "events": {"event_id", "t", "src", "dst", "kind", "severity", "label", "attack_class", "protocol", "port", "bytes", "extra_json"},
    "routes": {"route_id", "label", "hops_json", "provenance"},
    "labels": {"label_id", "event_id", "label", "provenance"},
    "windows": {"window_id", "title", "start_t", "end_t", "scenario_file"},
}


class PackError(ValueError):
    """Pack content is invalid or violates a safety bound."""


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackError("Cannot read valid UTF-8 JSON from %s: %s" % (path.name, exc)) from exc


def _canonical_json(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _payload_hash(pack_dir: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    for path in sorted(p for p in pack_dir.rglob("*") if p.is_file() and p.name != "manifest.json"):
        rel = path.relative_to(pack_dir).as_posix()
        size = path.stat().st_size
        total += size
        digest.update(rel.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest(), total


def _validate_topology(topology: dict, host_ids: set[str]):
    if set(topology) != {"network_id", "hosts", "feasible_edges", "observed_edges", "assets", "clusters"}:
        raise PackError("topology.json must contain exactly network_id, hosts, feasible_edges, observed_edges, assets, and clusters")
    seen = set()
    for host in topology["hosts"]:
        if not isinstance(host, dict) or not isinstance(host.get("host_id"), str):
            raise PackError("topology host must have a string host_id")
        host_id = host["host_id"]
        if not PACK_ID.fullmatch(host_id) or host_id in seen:
            raise PackError("topology contains an invalid or duplicate host id: %r" % host_id)
        seen.add(host_id)
    if seen != host_ids:
        raise PackError("manifest, topology, and SQLite host ids differ")
    for edge_type in ("feasible_edges", "observed_edges"):
        edges = topology[edge_type]
        if not isinstance(edges, list):
            raise PackError("%s must be a list" % edge_type)
        for edge in edges:
            if not isinstance(edge, dict) or edge.get("src") not in host_ids or edge.get("dst") not in host_ids or edge["src"] == edge["dst"]:
                raise PackError("%s has an invalid endpoint" % edge_type)
    if not isinstance(topology["assets"], dict) or set(topology["assets"]) - host_ids:
        raise PackError("topology assets contain an unknown host")
    if not isinstance(topology["clusters"], list):
        raise PackError("topology clusters must be a list")


def validate_pack(pack_dir, contracts_dir=None, require_matching_dir=True) -> dict:
    """Validate a complete pack, including its schema, content hash, references, and SQLite indexes."""
    pack_dir = Path(pack_dir).resolve()
    if not pack_dir.is_dir():
        raise PackError("Pack directory does not exist")
    files = list(pack_dir.rglob("*"))
    if any(path.is_symlink() for path in files):
        raise PackError("Pack directories cannot contain symbolic links")
    if sum(path.stat().st_size for path in files if path.is_file()) > PACK_MAX_BYTES:
        raise PackError("Pack exceeds the 25 MiB pack size limit")
    manifest = _read_json(pack_dir / "manifest.json")
    if contracts_dir is None:
        contracts_dir = Path(__file__).resolve().parents[3] / "contracts"
    schema = _read_json(Path(contracts_dir) / "schemas" / "pack_manifest.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda e: list(e.path))
    if errors:
        path = "/".join(map(str, errors[0].absolute_path)) or "(root)"
        raise PackError("manifest.json violates pack_manifest at %s: %s" % (path, errors[0].message))
    if not PACK_ID.fullmatch(manifest["id"]) or (require_matching_dir and manifest["id"] != pack_dir.name):
        raise PackError("pack id must be a safe identifier matching its directory name")
    expected_files = {"topology.json", "pack.sqlite", "routes.jsonl", "model.json", "evaluation.json", "card.md"}
    missing = sorted(name for name in expected_files if not (pack_dir / name).is_file())
    if missing:
        raise PackError("Pack is missing required files: " + ", ".join(missing))
    topology = _read_json(pack_dir / "topology.json")
    host_ids = {h["host_id"] for h in topology.get("hosts", []) if isinstance(h, dict) and isinstance(h.get("host_id"), str)}
    _validate_topology(topology, host_ids)
    if len(host_ids) != manifest["counts"]["hosts"]:
        raise PackError("manifest host count does not match topology")
    scenarios_dir = pack_dir / "scenarios"
    if not scenarios_dir.is_dir():
        raise PackError("Pack is missing its scenarios directory")
    scenario_schema = _read_json(Path(__file__).resolve().parents[3] / "graph" / "graph_replay" / "schemas" / "scenario.schema.json")
    scenario_ids = set()
    scenario_files = {}
    for scenario_path in scenarios_dir.glob("*.json"):
        scenario = _read_json(scenario_path)
        errors = list(Draft202012Validator(scenario_schema).iter_errors(scenario))
        if errors:
            raise PackError("Invalid scenario %s: %s" % (scenario_path.name, errors[0].message))
        if scenario["scenario_id"] in scenario_ids:
            raise PackError("Pack scenario ids must be unique")
        scenario_ids.add(scenario["scenario_id"])
        scenario_files[scenario["scenario_id"]] = scenario_path.name
        for event in scenario["events"]:
            referenced = ([event["host"]] if event["kind"] == "technique" else
                          [event["from_host"], event["to_host"]] if event["kind"] == "attempt" else
                          [host for packet in event.get("packets", []) for host in (packet["src_host"], packet["dst_host"])])
            if set(referenced) - host_ids:
                raise PackError("Scenario %s references an unknown host" % scenario_path.name)
    model = _read_json(pack_dir / "model.json")
    if not isinstance(model.get("alpha"), (int, float)) or not math.isfinite(model["alpha"]) or model["alpha"] <= 0 or not isinstance(model.get("counts"), dict):
        raise PackError("model.json requires numeric alpha and transition counts")
    for source, targets in model["counts"].items():
        if source not in host_ids or not isinstance(targets, dict) or set(targets) - host_ids or any(type(n) is not int or n < 0 for n in targets.values()):
            raise PackError("model.json contains invalid transition counts")
    evaluation = _read_json(pack_dir / "evaluation.json")
    if not isinstance(evaluation, dict) or not isinstance(evaluation.get("limitations"), list):
        raise PackError("evaluation.json must include a limitations list")
    if "evaluation_result" in evaluation:
        result_schema_path = Path(contracts_dir) / "schemas" / "evaluation_result.schema.json"
        result_schema = _read_json(result_schema_path)
        result_errors = sorted(Draft202012Validator(result_schema).iter_errors(evaluation["evaluation_result"]), key=lambda err: list(err.path))
        if result_errors:
            path = "/".join(map(str, result_errors[0].absolute_path)) or "(root)"
            raise PackError("evaluation_result violates its contract at %s: %s" % (path, result_errors[0].message))
    routes = []
    try:
        with (pack_dir / "routes.jsonl").open(encoding="utf-8") as fh:
            for line_num, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                route = json.loads(line)
                if not isinstance(route.get("path"), list) or any(host not in host_ids for host in route["path"]):
                    raise PackError("routes.jsonl line %d references an unknown host" % line_num)
                routes.append(route)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackError("routes.jsonl is invalid: %s" % exc) from exc
    if len(routes) != manifest["counts"]["routes"]:
        raise PackError("manifest route count does not match routes.jsonl")
    db = pack_dir / "pack.sqlite"
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % db.as_posix(), uri=True)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise PackError("pack.sqlite failed integrity_check")
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if set(SQLITE_COLUMNS) - tables:
                raise PackError("pack.sqlite is missing required tables")
            for table, required in SQLITE_COLUMNS.items():
                cols = {row[1] for row in conn.execute("PRAGMA table_info(%s)" % table)}
                if not required <= cols:
                    raise PackError("pack.sqlite table %s is missing columns" % table)
            for index_name, table, column in (("idx_events_t", "events", "t"), ("idx_events_src", "events", "src"), ("idx_events_dst", "events", "dst")):
                row = conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (index_name,)).fetchone()
                if not row or table not in row[0] or column not in row[0]:
                    raise PackError("pack.sqlite is missing index %s" % index_name)
            db_hosts = {row[0] for row in conn.execute("SELECT host_id FROM hosts")}
            if db_hosts != host_ids:
                raise PackError("SQLite and topology host ids differ")
            event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            route_count = conn.execute("SELECT COUNT(*) FROM routes").fetchone()[0]
            label_count = conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
            window_rows = conn.execute("SELECT window_id, scenario_file FROM windows").fetchall()
            if event_count != manifest["counts"]["events"] or edge_count != manifest["counts"]["edges"] or route_count != manifest["counts"]["routes"] or label_count != manifest["counts"]["labelled_events"]:
                raise PackError("manifest event or edge count does not match SQLite")
            if {row[0] for row in window_rows} != scenario_ids or any(Path(row[1]).name != scenario_files.get(row[0]) or Path(row[1]).is_absolute() or ".." in Path(row[1]).parts for row in window_rows):
                raise PackError("SQLite windows do not match safe scenario files")
            for table, columns in (("edges", ("src", "dst")), ("events", ("src", "dst"))):
                for column in columns:
                    unknown = conn.execute("SELECT 1 FROM %s WHERE %s IS NOT NULL AND %s NOT IN (SELECT host_id FROM hosts) LIMIT 1" % (table, column, column)).fetchone()
                    if unknown:
                        raise PackError("SQLite %s.%s references an unknown host" % (table, column))
            for (hops_raw,) in conn.execute("SELECT hops_json FROM routes"):
                try:
                    hops = json.loads(hops_raw)
                except json.JSONDecodeError as exc:
                    raise PackError("SQLite route has invalid hops JSON") from exc
                if not isinstance(hops, list) or any(not isinstance(hop, dict) or hop.get("host_id") not in host_ids for hop in hops):
                    raise PackError("SQLite route references an unknown host")
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise PackError("Cannot validate pack.sqlite: %s" % exc) from exc
    digest, payload_bytes = _payload_hash(pack_dir)
    if digest != manifest["content_hash"]:
        raise PackError("Pack content hash does not match its files")
    if manifest["size_bytes"] != payload_bytes:
        raise PackError("manifest size_bytes does not match non-manifest payload size")
    return manifest


@dataclass(frozen=True)
class DatasetPack:
    path: Path
    manifest: dict

    def iter_events(self, start_t: int | None = None, end_t: int | None = None, batch_size: int = 1000) -> Iterator[list[dict]]:
        """Yield ordered, bounded event batches using indexed range queries."""
        if not isinstance(batch_size, int) or batch_size < 1 or batch_size > 10_000:
            raise ValueError("batch_size must be between 1 and 10000")
        conn = sqlite3.connect("file:%s?mode=ro" % (self.path / "pack.sqlite").as_posix(), uri=True)
        conn.row_factory = sqlite3.Row
        try:
            clauses, args = [], []
            if start_t is not None:
                clauses.append("t >= ?"); args.append(start_t)
            if end_t is not None:
                clauses.append("t <= ?"); args.append(end_t)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            cursor = conn.execute("SELECT * FROM events" + where + " ORDER BY t, event_id", args)
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                batch = []
                for row in rows:
                    item = dict(row)
                    item["extra"] = json.loads(item.pop("extra_json"))
                    batch.append(item)
                yield batch
        finally:
            conn.close()


class PackStore:
    """Read-only pack registry bounded to trusted shipped and runtime roots."""
    def __init__(self, root, contracts_dir=None, additional_roots=()):
        self.root = Path(root).resolve()
        self.additional_roots = tuple(Path(item).resolve() for item in additional_roots)
        self.contracts_dir = Path(contracts_dir).resolve() if contracts_dir else None

    @property
    def roots(self):
        return tuple(dict.fromkeys((Path(self.root).resolve(), *self.additional_roots)))

    def open(self, pack_id: str) -> DatasetPack:
        if not isinstance(pack_id, str) or not PACK_ID.fullmatch(pack_id):
            raise PackError("Invalid pack id")
        for root in self.roots:
            path = (root / pack_id).resolve()
            if path.parent != root:
                raise PackError("Pack path escapes the configured pack root")
            if path.is_dir():
                manifest = validate_pack(path, self.contracts_dir)
                if manifest["id"] != pack_id:
                    raise PackError("Pack id does not match the requested store id")
                return DatasetPack(path, manifest)
        raise PackError("Pack is not installed")

    def list_packs(self) -> list[dict]:
        """Return validated manifest summaries for packs directly under the store root."""
        summaries = []
        seen = set()
        for root in self.roots:
            if not root.is_dir():
                continue
            for path in sorted(root.iterdir()):
                if path.is_dir() and PACK_ID.fullmatch(path.name):
                    if path.is_symlink() or path.resolve().parent != root:
                        raise PackError("Pack store entries cannot be symlinks or escape the pack root")
                    if path.name in seen:
                        raise PackError("Duplicate pack id across configured pack roots")
                    seen.add(path.name)
                    manifest = validate_pack(path, self.contracts_dir)
                    summaries.append({"id": manifest["id"], "name": manifest["name"], "version": manifest["version"], "counts": manifest["counts"], "capabilities": manifest["capabilities"]})
        return summaries


def _sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scenario_events(scenario):
    for event in scenario["events"]:
        base = {"t": int(event["offset_ms"]), "kind": event["kind"], "severity": event.get("severity", "LOW"), "label": None, "attack_class": None, "protocol": None, "port": None, "bytes": None}
        if event["kind"] == "technique":
            base.update(dst=event["host"], label=event["technique_id"], attack_class="simulated-technique")
        elif event["kind"] == "attempt":
            base.update(src=event["from_host"], dst=event["to_host"], label=event.get("technique_id"), attack_class="simulated-lateral-movement")
        else:
            packets = event.get("packets", [])
            if packets:
                packet = packets[0]
                base.update(src=packet.get("src_host"), dst=packet.get("dst_host"), protocol=packet.get("protocol"), port=packet.get("dst_port"), bytes=packet.get("packet_size"), label=packet.get("anomaly"))
                base["attack_class"] = "simulated-traffic"
        yield base


def build_demo6_pack(repo_root, output_dir, contracts_dir=None) -> dict:
    """Convert the checked-in demo fixtures into a validated offline pack, atomically."""
    repo_root, output_dir = Path(repo_root).resolve(), Path(output_dir).resolve()
    pack_id = "demo-6"
    if output_dir.name != pack_id:
        raise PackError("demo-6 output directory must be named demo-6")
    sources = {
        "hosts": repo_root / "contracts/data/hosts.json",
        "topology": repo_root / "graph/graph_net/data/topology.json",
        "routes": repo_root / "graph/graph_replay/training/sequences.json",
        "model": repo_root / "lead-core/precog/precog_engine/data/node_model.json",
        "evaluation": repo_root / "lead-core/precog/results/precog_evaluation.json",
    }
    scenarios = sorted((repo_root / "graph/graph_replay/scenarios").glob("*.json"))
    for path in sources.values():
        if not path.is_file():
            raise PackError("Required demo source is missing: %s" % path)
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".demo-6-build-", dir=str(parent)))
    backup = parent / ".demo-6-backup"
    try:
        hosts_doc, legacy_topology = _read_json(sources["hosts"]), _read_json(sources["topology"])
        route_doc, model, evaluation_doc = (_read_json(sources[name]) for name in ("routes", "model", "evaluation"))
        hosts = hosts_doc["hosts"]
        ids = {host["host_id"] for host in hosts}
        topology = {
            "network_id": hosts_doc["network"], "hosts": hosts,
            "feasible_edges": [{"src": src, "dst": dst, "probability": None} for src, targets in legacy_topology["feasible_connections"].items() for dst in targets],
            "observed_edges": [], "assets": legacy_topology["assets"],
            "clusters": [{"id": "zone-" + zone, "name": zone, "host_ids": [h["host_id"] for h in hosts if h["zone"] == zone]} for zone in sorted({h["zone"] for h in hosts})],
        }
        _validate_topology(topology, ids)
        (staging / "topology.json").write_bytes(_canonical_json(topology))
        scenario_dir = staging / "scenarios"
        scenario_dir.mkdir()
        scenario_records = []
        all_events = []
        for scenario_path in scenarios:
            scenario = _read_json(scenario_path)
            # Validate each shipped scenario against GRAPH's existing schema.
            scenario_schema = _read_json(repo_root / "graph/graph_replay/schemas/scenario.schema.json")
            errors = list(Draft202012Validator(scenario_schema).iter_errors(scenario))
            if errors:
                raise PackError("Shipped scenario %s is invalid: %s" % (scenario_path.name, errors[0].message))
            if any((e.get("host") not in ids if e["kind"] == "technique" else (e.get("from_host") not in ids or e.get("to_host") not in ids if e["kind"] == "attempt" else any(p.get("src_host") not in ids or p.get("dst_host") not in ids for p in e.get("packets", [])))) for e in scenario["events"]):
                raise PackError("Scenario references a host outside demo-6")
            rel = "scenarios/" + scenario_path.name
            (staging / rel).write_bytes(_canonical_json(scenario))
            scenario_records.append((scenario, rel))
            all_events.extend((scenario["scenario_id"], i, event) for i, event in enumerate(_scenario_events(scenario), 1))
        conn = sqlite3.connect(staging / "pack.sqlite")
        try:
            conn.executescript("""
                PRAGMA journal_mode=DELETE;
                PRAGMA synchronous=FULL;
                CREATE TABLE hosts(host_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, zone TEXT NOT NULL, role TEXT NOT NULL, criticality REAL NOT NULL, details_json TEXT NOT NULL);
                CREATE TABLE edges(src TEXT NOT NULL, dst TEXT NOT NULL, edge_kind TEXT NOT NULL, count INTEGER NOT NULL, first_seen INTEGER, last_seen INTEGER, provenance TEXT NOT NULL, PRIMARY KEY(src,dst,edge_kind));
                CREATE TABLE events(event_id INTEGER PRIMARY KEY, t INTEGER NOT NULL, src TEXT, dst TEXT, kind TEXT NOT NULL, severity TEXT, label TEXT, attack_class TEXT, protocol TEXT, port INTEGER, bytes INTEGER, extra_json TEXT NOT NULL);
                CREATE TABLE routes(route_id TEXT PRIMARY KEY, label TEXT NOT NULL, hops_json TEXT NOT NULL, provenance TEXT NOT NULL);
                CREATE TABLE labels(label_id INTEGER PRIMARY KEY, event_id INTEGER, label TEXT NOT NULL, provenance TEXT NOT NULL);
                CREATE TABLE windows(window_id TEXT PRIMARY KEY, title TEXT NOT NULL, start_t INTEGER NOT NULL, end_t INTEGER NOT NULL, scenario_file TEXT NOT NULL);
                CREATE INDEX idx_events_t ON events(t);
                CREATE INDEX idx_events_src ON events(src);
                CREATE INDEX idx_events_dst ON events(dst);
            """)
            for host in hosts:
                details = {k: v for k, v in host.items() if k not in ("host_id", "name", "zone", "role")}
                asset = legacy_topology["assets"].get(host["host_id"], {})
                conn.execute("INSERT INTO hosts VALUES(?,?,?,?,?,?)", (host["host_id"], host["name"], host["zone"], host["role"], float(asset.get("criticality", 0.5)), json.dumps(details, sort_keys=True)))
            for src, targets in legacy_topology["feasible_connections"].items():
                for dst in targets:
                    conn.execute("INSERT INTO edges VALUES(?,?,?,?,?,?,?)", (src, dst, "feasible", 0, None, None, "native-demo-topology"))
            for seq, (scenario_id, index, event) in enumerate(all_events, 1):
                extra = {"scenario_id": scenario_id, "scenario_event": index, **event.pop("extra", {})}
                conn.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (seq, event["t"], event.get("src"), event.get("dst"), event["kind"], event["severity"], str(event.get("label")) if event.get("label") is not None else None, event.get("attack_class"), event.get("protocol"), event.get("port"), event.get("bytes"), json.dumps(extra, sort_keys=True)))
                if event.get("label") is not None:
                    conn.execute("INSERT INTO labels(event_id,label,provenance) VALUES(?,?,?)", (seq, str(event["label"]), "native-demo-script"))
            for scenario, rel in scenario_records:
                end_t = max(e["offset_ms"] for e in scenario["events"])
                conn.execute("INSERT INTO windows VALUES(?,?,?,?,?)", (scenario["scenario_id"], scenario["description"], 0, end_t, rel))
            route_lines = []
            for i, sequence in enumerate(route_doc["sequences"], 1):
                if any(host not in ids for host in sequence["path"]):
                    raise PackError("Training route references a host outside demo-6")
                route = {"route_id": "route-%06d" % i, "profile": sequence["profile"], "path": sequence["path"], "provenance": "native-scripted-simulation"}
                route_lines.append(json.dumps(route, sort_keys=True, separators=(",", ":")))
                hops = [{"host_id": host, "position": pos} for pos, host in enumerate(sequence["path"])]
                conn.execute("INSERT INTO routes VALUES(?,?,?,?)", (route["route_id"], route["profile"], json.dumps(hops, sort_keys=True), route["provenance"]))
            conn.commit()
            conn.execute("VACUUM")
        finally:
            conn.close()
        (staging / "routes.jsonl").write_text("\n".join(route_lines) + "\n", encoding="utf-8", newline="\n")
        (staging / "model.json").write_bytes(_canonical_json(model))
        evaluation = {**evaluation_doc, "source": "lead-core/precog/results/precog_evaluation.json", "detector": evaluation_doc.get("detector"), "limitations": ["Six-host scripted simulation; not real attacker data.", "Forecast and detection metrics describe held-out generated sequences only.", "Precision@3 is trivial for this topology because candidate sets contain at most three hosts."]}
        (staging / "evaluation.json").write_bytes(_canonical_json(evaluation))
        (staging / "card.md").write_text("# Precog demo-6\n\nThe unchanged deterministic six-host scripted simulation used by the existing application. Scenarios and training routes are project-generated. Detection uses the existing NIDS live path. Containment is an in-memory simulated action. This pack is for demonstrating the pipeline, not measuring real-world security performance.\n", encoding="utf-8", newline="\n")
        digest, payload_size = _payload_hash(staging)
        source_hashes = [{"path": path.relative_to(repo_root).as_posix(), "sha256": _sha(path)} for path in list(sources.values()) + scenarios]
        manifest = {
            "id": pack_id, "name": "Precog six-host demo", "version": "1.0.0", "builder_version": "precog-pack-builder/1.0.0", "seed": int(route_doc.get("seed", 0)), "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "source": {"id": "project-demo-6", "name": "Project-owned deterministic demo fixtures", "citation": "Precog SOC project fixtures; not external data.", "licence": "Project-owned simulation", "terms_summary": "Generated and scripted demo content; no external dataset redistribution."},
            "redistribution": "project-owned", "size_bytes": payload_size,
            "counts": {"hosts": len(hosts), "edges": len(topology["feasible_edges"]), "events": len(all_events), "labelled_events": sum(1 for _, _, e in all_events if e.get("label") is not None), "routes": len(route_lines), "time_span_ms": max((w[0]["events"][-1]["offset_ms"] for w in scenario_records), default=0)},
            "capabilities": {"detection_labels": "native", "host_compromise": "native", "lateral_movement_routes": "native", "topology": "native"},
            "attack_classes": [{"id": "simulated-technique", "compromise_semantics": "access-attempt"}, {"id": "simulated-lateral-movement", "compromise_semantics": "lateral-movement"}, {"id": "simulated-traffic", "compromise_semantics": "impact-only"}],
            "technique_mapping": [{"attack_class": "simulated-lateral-movement", "technique_ids": ["T1021.004"], "assumption": "The shipped golden-path replay declares this technique; this is a scenario mapping, not inferred from external truth."}],
            "detector_options": ["nids-live"], "default_decision_policy": {"mode": "scenario-pauses", "threshold": 0.0, "minimum_candidates": 1}, "display_hints": {"zones": sorted({h["zone"] for h in hosts}), "clusters": "zone", "layout": "demo-6-default"},
            "source_file_checksums": source_hashes, "content_hash": digest,
        }
        (staging / "manifest.json").write_bytes(_canonical_json(manifest))
        # Validate against final structure before publishing.
        validate_pack(staging, contracts_dir, require_matching_dir=False)
        if output_dir.exists():
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(output_dir, backup)
        try:
            os.replace(staging, output_dir)
        except Exception:
            if backup.exists() and not output_dir.exists():
                os.replace(backup, output_dir)
            raise
        if backup.exists():
            shutil.rmtree(backup)
        return validate_pack(output_dir, contracts_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def validate_existing_demo_equivalence(pack_dir, repo_root):
    """Assert pack views match the original six-host runtime fixtures and return a summary."""
    pack_dir, repo_root = Path(pack_dir), Path(repo_root)
    manifest = validate_pack(pack_dir)
    source_hosts = _read_json(repo_root / "contracts/data/hosts.json")["hosts"]
    source_topology = _read_json(repo_root / "graph/graph_net/data/topology.json")
    packed_topology = _read_json(pack_dir / "topology.json")
    if source_hosts != packed_topology["hosts"]:
        raise PackError("demo-6 pack host inventory differs from the legacy host inventory")
    legacy_edges = {(src, dst) for src, targets in source_topology["feasible_connections"].items() for dst in targets}
    pack_edges = {(edge["src"], edge["dst"]) for edge in packed_topology["feasible_edges"]}
    if legacy_edges != pack_edges:
        raise PackError("demo-6 pack feasible edges differ from the legacy topology")
    legacy_sequences = _read_json(repo_root / "graph/graph_replay/training/sequences.json")["sequences"]
    packed_routes = [json.loads(line) for line in (pack_dir / "routes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if [r["path"] for r in packed_routes] != [r["path"] for r in legacy_sequences]:
        raise PackError("demo-6 pack training routes differ from legacy sequences")
    legacy_model = _read_json(repo_root / "lead-core/precog/precog_engine/data/node_model.json")
    if _read_json(pack_dir / "model.json") != legacy_model:
        raise PackError("demo-6 pack Precog model differs from the shipped model")
    source_scenarios = {item["scenario_id"]: item for item in (_read_json(path) for path in (repo_root / "graph/graph_replay/scenarios").glob("*.json"))}
    pack_scenarios = {item["scenario_id"]: item for item in (_read_json(path) for path in (pack_dir / "scenarios").glob("*.json"))}
    if source_scenarios != pack_scenarios:
        raise PackError("demo-6 pack scenarios differ from the original replay fixtures")
    expected_events = []
    for scenario_id, scenario in sorted(source_scenarios.items()):
        for event in _scenario_events(scenario):
            expected_events.append((event["t"], event.get("src"), event.get("dst"), event["kind"], event["severity"], str(event.get("label")) if event.get("label") is not None else None, event.get("attack_class"), event.get("protocol"), event.get("port"), event.get("bytes"), scenario_id))
    conn = sqlite3.connect("file:%s?mode=ro" % (pack_dir / "pack.sqlite").as_posix(), uri=True)
    try:
        packed_events = []
        for row in conn.execute("SELECT t,src,dst,kind,severity,label,attack_class,protocol,port,bytes,extra_json FROM events ORDER BY event_id"):
            extra = json.loads(row[10])
            packed_events.append((*row[:10], extra.get("scenario_id")))
    finally:
        conn.close()
    if Counter(expected_events) != Counter(packed_events):
        raise PackError("demo-6 pack event stream differs from the original scripted event inputs")
    evaluation_source = _read_json(repo_root / "lead-core/precog/results/precog_evaluation.json")
    if _read_json(pack_dir / "evaluation.json")["node_model"] != evaluation_source["node_model"]:
        raise PackError("demo-6 pack evaluation differs from the shipped evaluation")
    return {"pack_id": manifest["id"], "hosts": len(source_hosts), "edges": len(legacy_edges), "routes": len(legacy_sequences), "model_equal": True, "scenarios_equal": True, "event_inputs_equal": True, "evaluation_equal": True, "golden_path_unchanged": True}
