"""Offline, bounded builders for the Phase D5 public dataset sources.

Raw records are read only by this command-line pipeline. Host identifiers are
pseudonymized before a pack is written; raw source files never enter the app.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import ipaddress
import json
import os
import random
import re
import shutil
import sqlite3
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .dataset_packs import PackError, _canonical_json, _payload_hash, validate_pack


BUILDER_VERSION = "precog-real-dataset-builder/1.0.0"
MAX_HOSTS = 500
MAX_EVENTS = 100_000
MAX_ROWS_SCANNED = 2_000_000
MAX_PACK_BYTES = 25 * 1024 * 1024
ATTACK_TECHNIQUES = {
    "access-attempt": "T1110", "impact-only": "T1498",
    "reconnaissance": "T1046", "command-and-control": "T1071",
    "lateral-movement": "T1021.001",
}


@dataclass(frozen=True)
class DatasetSpec:
    id: str
    name: str
    url: str
    citation: str
    licence: str
    terms: str
    redistribution: str
    host_semantics: str = "derived"
    route_semantics: str = "derived"
    topology_semantics: str = "derived"
    parser: str = "flows"


SPECS = {
    "lanl-cyber1": DatasetSpec(
        "lanl-cyber1", "LANL Cyber1 authentication events",
        "https://csr.lanl.gov/data/cyber1/",
        'A. D. Kent, "Cybersecurity Data Sources for Dynamic Network Research," 2015.',
        "LANL public release; rights waived to the extent possible",
        "LANL approves the data for public release and requests a short intended-use description for access. Cite the dataset in publications; source files are not bundled by this project.",
        "builder-only-pending-release-review", "derived", "derived", "derived", "lanl",
    ),
    "cse-cic-ids2018": DatasetSpec(
        "cse-cic-ids2018", "CSE-CIC-IDS2018 labeled flows",
        "https://www.unb.ca/cic/datasets/ids-2018.html",
        'I. Sharafaldin, A. H. Lashkari, and A. A. Ghorbani, "Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization," ICISSP, 2018.',
        "UNB CIC dataset terms; redistribution requires citation and AWS dataset link",
        "UNB permits redistribution with the dataset citation and link to the AWS registry. Preserve attribution and record checksums for selected files.",
        "attribution-required", parser="flows",
    ),
    "cic-ids2017": DatasetSpec(
        "cic-ids2017", "CIC-IDS2017 labeled flows",
        "https://www.unb.ca/cic/datasets/ids-2017.html",
        'I. Sharafaldin, A. H. Lashkari, and A. A. Ghorbani, "Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization," ICISSP, 2018.',
        "UNB CIC dataset terms; redistribution requires dataset and paper citations",
        "UNB's FAQ permits mirroring with citation. Raw flows do not prove successful compromise; keep derived host and route labels explicit.",
        "attribution-required", parser="flows",
    ),
    "ctu-13": DatasetSpec(
        "ctu-13", "CTU-13 labeled botnet flows",
        "https://www.stratosphereips.org/datasets-ctu13/",
        'S. García et al., "An empirical comparison of botnet detection methods," Computers & Security, 2014.',
        "Creative Commons Attribution (CC BY); verify version-specific notice",
        "Use the bidirectional NetFlow text files, not the superseded unidirectional flows. Attribute Stratosphere Lab and cite its paper.",
        "attribution-required", "derived", "derived", "derived", "ctu",
    ),
    "cic-iot-2023": DatasetSpec(
        "cic-iot-2023", "CIC IoT dataset 2023",
        "https://www.unb.ca/cic/datasets/iotdataset-2023.html",
        'E. C. P. Neto et al., "CICIoT2023: A real-time dataset and benchmark for large-scale attacks in IoT environment," Sensors, 2023.',
        "UNB CIC terms not explicit on the reviewed source page",
        "The official page describes the data and citation but does not establish redistribution permission. Builder only until the rights holder confirms terms.",
        "builder-only-pending-terms", parser="flows",
    ),
    "ton-iot": DatasetSpec(
        "ton-iot", "ToN_IoT network telemetry",
        "https://research.unsw.edu.au/projects/toniot-datasets",
        'N. Moustafa, "TON_IoT Datasets: A New Generation Dataset of IoT and IIoT for Data-Driven Intrusion Detection Systems," 2021.',
        "UNSW academic research use; commercial use requires author approval",
        "The project page grants academic use and requires citations. It does not establish a general derived-data redistribution grant; builder only pending clarification.",
        "builder-only-pending-terms", parser="flows",
    ),
    "unsw-nb15": DatasetSpec(
        "unsw-nb15", "UNSW-NB15 labeled flows",
        "https://research.unsw.edu.au/projects/unsw-nb15-dataset",
        'N. Moustafa and J. Slay, "UNSW-NB15: a comprehensive data set for network intrusion detection systems," MilCIS, 2015.',
        "UNSW academic research use; commercial use requires agreement",
        "The dataset page describes academic use; redistribution of converted records is not established. Builder only pending written clarification.",
        "builder-only-pending-terms", "derived", "none", "derived", "flows",
    ),
    "cidds-001": DatasetSpec(
        "cidds-001", "CIDDS-001 labeled flow benchmark",
        "https://www.hs-coburg.de/forschen/transferstellen-und-institute/kompetenzzentrum-fuer-it-sicherheit/cidds-coburg-intrusion-detection-data-sets/",
        'M. Ring et al., "Flow-based benchmark data sets for intrusion detection," 2017.',
        "Citation required; broad redistribution grant not established",
        "The university page requests citation but does not grant broad redistribution. Builder only pending clarification and file-level checks.",
        "builder-only-pending-terms", parser="flows",
    ),
}


ALIASES = {
    "time": ("timestamp", "time", "stime", "starttime", "start_time", "start time", "date first seen", "ts", "stime_ms"),
    "src": ("src ip", "src ip addr", "source ip", "src_ip", "srcip", "source address", "srcaddr", "src addr", "ipv4_src_addr", "src_host", "source computer", "source_computer"),
    "dst": ("dst ip", "dst ip addr", "destination ip", "dst_ip", "dstip", "destination address", "dstaddr", "dst addr", "ipv4_dst_addr", "dst_host", "destination computer", "destination_computer"),
    "label": ("label", "attack_cat", "attack_type", "attack type", "attack category", "category", "class", "type"),
    "proto": ("protocol", "proto", "protocol type", "l4_proto"),
    "sport": ("src port", "source port", "src_port", "sport", "src pt", "source_port"),
    "dport": ("dst port", "destination port", "dst_port", "dport", "dst pt", "destination_port"),
    "bytes": ("totbytes", "total bytes", "bytes", "tot size", "tot_size", "srcbytes", "flow bytes"),
    "packets": ("totpkts", "total packets", "packets", "tot_pkts", "packet count"),
    "duration": ("dur", "duration", "flow duration", "flow_duration"),
}


def _key(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()


def _columns(row):
    return {_key(key): value for key, value in row.items() if key is not None}


def _get(row, field, default=""):
    row = _columns(row)
    for alias in ALIASES[field]:
        if _key(alias) in row and row[_key(alias)] is not None:
            return str(row[_key(alias)]).strip()
    return default


def _time_ms(value, fallback):
    text = str(value or "").strip()
    if text:
        try:
            number = float(text)
            if number >= 1e12:
                return int(number)
            return int(number * 1000)
        except ValueError:
            pass
        for fmt in ("%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d-%H.%M.%S.%f"):
            try:
                return int(datetime.strptime(text, fmt).replace(tzinfo=timezone.utc).timestamp() * 1000)
            except ValueError:
                continue
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return int(parsed.timestamp() * 1000)
        except ValueError:
            pass
    return int(fallback) * 1000


def _integer(value, default=0):
    try:
        return max(0, min(65535, int(float(str(value).strip().replace(",", "")))))
    except (TypeError, ValueError):
        return default


def _is_benign(label):
    normalized = _key(label).replace(" ", "")
    return normalized in {"", "0", "benign", "normal", "background", "normaltraffic", "backgroundtraffic", "noattack"}


def _semantics(label, dataset_id):
    value = _key(label)
    if _is_benign(value):
        return "benign"
    if any(term in value for term in ("ddos", "dos", "flood", "impact")):
        return "impact-only"
    if any(term in value for term in ("scan", "recon", "probing", "portscan")):
        return "reconnaissance"
    if any(term in value for term in ("botnet", "c2", "mirai", "command and control")):
        return "command-and-control"
    if any(term in value for term in ("infiltration", "lateral", "pivot", "worm")):
        return "lateral-movement"
    if any(term in value for term in ("brute", "exploit", "web attack", "backdoor", "shellcode", "fuzzer", "generic")):
        return "access-attempt"
    return "access-attempt"


def _open_text(path):
    return gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="") if str(path).lower().endswith(".gz") else open(path, "r", encoding="utf-8-sig", errors="replace", newline="")


def _flow_records(paths, dataset_id, max_rows, max_events):
    output, scanned = [], 0
    for path in paths:
        if len(output) >= max_events:
            break
        with _open_text(path) as stream:
            reader = csv.DictReader(stream, skipinitialspace=True)
            if not reader.fieldnames:
                raise PackError("No CSV header found in %s" % Path(path).name)
            normalized = {_key(name) for name in reader.fieldnames}
            if not any(any(_key(alias) in normalized for alias in ALIASES[field]) for field in ("src",)) or not any(any(_key(alias) in normalized for alias in ALIASES[field]) for field in ("dst",)):
                raise PackError("%s needs source and destination address columns" % Path(path).name)
            for line, row in enumerate(reader, 2):
                scanned += 1
                if scanned > max_rows:
                    raise PackError("Raw input exceeds the %d-row scan limit" % max_rows)
                src, dst = _get(row, "src"), _get(row, "dst")
                if not src or not dst or src == "?" or dst == "?":
                    continue
                label = _get(row, "label")[:120]
                if dataset_id == "cidds-001":
                    # CIDDS Class describes the endpoint perspective (attacker,
                    # victim, normal); AttackType contains the actual class.
                    label = (_columns(row).get("attacktype") or _columns(row).get("attack type") or label)[:120]
                protocol = _get(row, "proto", "TCP").upper()
                if protocol not in ("TCP", "UDP", "ICMP"):
                    protocol = "TCP"
                output.append({"raw_t": _time_ms(_get(row, "time"), scanned), "raw_src": src, "raw_dst": dst,
                    "label": label or None, "semantic": _semantics(label, dataset_id), "protocol": protocol,
                    "sport": _integer(_get(row, "sport")), "dport": _integer(_get(row, "dport")),
                    "bytes": min(65535, _integer(_get(row, "bytes"))), "packets": min(1000000, _integer(_get(row, "packets"))),
                    "source_file": Path(path).name, "source_row": line})
                if len(output) >= max_rows:
                    raise PackError("Normalized records exceed the configured event limit")
                if len(output) >= max_events:
                    return output
    return output


def _lanl_records(paths, max_rows, max_events):
    by_name = {Path(path).name.lower(): path for path in paths}
    auth = next((path for name, path in by_name.items() if name.startswith("auth.txt")), None)
    redteam = next((path for name, path in by_name.items() if name.startswith("redteam.txt")), None)
    if not auth or not redteam:
        raise PackError("LANL builder requires auth.txt[.gz] and redteam.txt[.gz]")
    red_rows, red_keys = [], set()
    with _open_text(redteam) as stream:
        for index, row in enumerate(csv.reader(stream), 1):
            if index > min(100_000, max_rows):
                raise PackError("LANL red-team file exceeds the 100,000-row limit")
            if len(row) < 4:
                continue
            t, user, src, dst = (part.strip() for part in row[:4])
            key = (t, user, src, dst)
            red_keys.add(key)
            red_rows.append({"raw_t": _time_ms(t, index), "raw_src": src, "raw_dst": dst,
                "label": "redteam", "semantic": "lateral-movement", "protocol": "TCP", "sport": 0, "dport": 0,
                "bytes": 0, "packets": 1, "source_file": Path(redteam).name, "source_row": index, "user": user,
                "is_redteam": True, "red_key": key})
    output, scanned, matched_redteam = [], 0, set()
    with _open_text(auth) as stream:
        for index, row in enumerate(csv.reader(stream), 1):
            scanned += 1
            if scanned > max_rows:
                raise PackError("LANL auth input exceeds the %d-row scan limit" % max_rows)
            if len(row) < 9:
                continue
            t, src_user, dst_user, src, dst = (part.strip() for part in row[:5])
            key = (t, src_user, src, dst)
            match = key in red_keys
            if match:
                matched_redteam.add(key)
            output.append({"raw_t": _time_ms(t, index), "raw_src": src, "raw_dst": dst,
                "label": "redteam" if match else None, "semantic": "lateral-movement" if match else "benign",
                "protocol": "TCP", "sport": 0, "dport": 0, "bytes": 0, "packets": 1,
                "source_file": Path(auth).name, "source_row": index, "user": src_user, "is_redteam": match})
            if len(output) >= max_events - min(len(red_rows), max_events):
                break
    # Prefer the compact ground-truth file over duplicating the corresponding
    # authentication rows, while retaining matched rows as route evidence.
    unmatched = [row for row in red_rows if row["red_key"] not in matched_redteam]
    output.extend(unmatched[:max(0, max_events - len(output))])
    return output[:max_events]


def parse_dataset(dataset_id, paths, max_rows=MAX_ROWS_SCANNED, max_events=MAX_EVENTS):
    """Normalize a tiny fixture or downloaded source file without retaining raw IPs."""
    if dataset_id not in SPECS:
        raise PackError("Unknown real dataset id %r" % dataset_id)
    paths = [Path(path) for path in paths]
    if not paths or any(path.is_symlink() or not path.is_file() for path in paths):
        raise PackError("Raw inputs must be existing regular files")
    paths = [path.resolve() for path in paths]
    if SPECS[dataset_id].parser == "lanl":
        return _lanl_records(paths, max_rows, max_events)
    return _flow_records(paths, dataset_id, max_rows, max_events)


def _host_id(raw_id, seed):
    digest = hashlib.sha256((str(seed) + "\0" + raw_id).encode("utf-8")).hexdigest()[:16]
    return "host-" + digest


def _safe_label(raw):
    value = re.sub(r"[^a-z0-9-]+", "-", _key(raw)).strip("-")[:80]
    return value or "unknown"


def _route_rows(records, spec, host_map):
    """Derive only ordered paths supported by source evidence and declared semantics."""
    if spec.route_semantics == "none":
        return []
    by_user = defaultdict(list)
    if spec.parser == "lanl":
        for row in records:
            if row.get("is_redteam"):
                if row["raw_src"] in host_map and row["raw_dst"] in host_map:
                    by_user[row.get("user", "unknown")].extend((host_map[row["raw_src"]], host_map[row["raw_dst"]]))
    else:
        root_by_host = {}
        trails = defaultdict(list)
        records_sorted = sorted(records, key=lambda row: (row["raw_t"], row["source_file"], row["source_row"]))
        for row in records_sorted:
            src, dst = row["raw_src"], row["raw_dst"]
            if src not in host_map or dst not in host_map or not row.get("label") or row["semantic"] == "benign":
                continue
            try:
                source_ip = ipaddress.ip_address(src)
                source_external = not source_ip.is_private
            except ValueError:
                source_external = False
            if row["semantic"] in ("access-attempt", "lateral-movement") and source_external:
                root_by_host[dst] = src
                trails[src].append(host_map[dst])
            elif row["semantic"] == "lateral-movement" and src in root_by_host:
                root_by_host[dst] = root_by_host[src]
                trails[root_by_host[src]].append(host_map[dst])
        by_user.update(trails)
    routes = []
    for number, (_source_profile, hops) in enumerate(sorted(by_user.items()), 1):
        ordered = []
        for host in hops:
            if not ordered or ordered[-1] != host:
                ordered.append(host)
        if len(ordered) >= 2:
            # Never serialize a source account name or external source address as route metadata.
            routes.append({"route_id": "route-%06d" % number, "profile": "campaign-%03d" % number,
                "path": ordered[:100], "provenance": "native-redteam" if spec.parser == "lanl" else "derived-from-labelled-flows"})
    return routes


def _write_database(path, hosts, edges, events, routes, start_t, end_t, scenario_id):
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
            PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL;
            CREATE TABLE hosts(host_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, zone TEXT NOT NULL, role TEXT NOT NULL, criticality REAL NOT NULL, details_json TEXT NOT NULL);
            CREATE TABLE edges(src TEXT NOT NULL, dst TEXT NOT NULL, edge_kind TEXT NOT NULL, count INTEGER NOT NULL, first_seen INTEGER, last_seen INTEGER, provenance TEXT NOT NULL, PRIMARY KEY(src,dst,edge_kind));
            CREATE TABLE events(event_id INTEGER PRIMARY KEY, t INTEGER NOT NULL, src TEXT, dst TEXT, kind TEXT NOT NULL, severity TEXT, label TEXT, attack_class TEXT, protocol TEXT, port INTEGER, bytes INTEGER, extra_json TEXT NOT NULL);
            CREATE TABLE routes(route_id TEXT PRIMARY KEY, label TEXT NOT NULL, hops_json TEXT NOT NULL, provenance TEXT NOT NULL);
            CREATE TABLE labels(label_id INTEGER PRIMARY KEY, event_id INTEGER, label TEXT NOT NULL, provenance TEXT NOT NULL);
            CREATE TABLE windows(window_id TEXT PRIMARY KEY, title TEXT NOT NULL, start_t INTEGER NOT NULL, end_t INTEGER NOT NULL, scenario_file TEXT NOT NULL);
            CREATE INDEX idx_events_t ON events(t); CREATE INDEX idx_events_src ON events(src); CREATE INDEX idx_events_dst ON events(dst);
        """)
        for host in hosts:
            conn.execute("INSERT INTO hosts VALUES(?,?,?,?,?,?)", (host["host_id"], host["name"], host["zone"], host["role"], 0.5,
                json.dumps({"identity_pseudonymized": True, "services": host["services"]}, sort_keys=True, separators=(",", ":"))))
        for edge in edges:
            conn.execute("INSERT INTO edges VALUES(?,?,?,?,?,?,?)", (edge["src"], edge["dst"], "observed", edge["count"], edge["first_seen"], edge["last_seen"], "derived-from-recorded-flows"))
        for item in events:
            conn.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (item["event_id"], item["t"], item["src"], item["dst"], item["kind"],
                item["severity"], item["label"], item["attack_class"], item["protocol"], item["port"], item["bytes"],
                json.dumps(item["extra"], sort_keys=True, separators=(",", ":"))))
            if item["label"] is not None:
                conn.execute("INSERT INTO labels(event_id,label,provenance) VALUES(?,?,?)", (item["event_id"], item["label"], "native-dataset-label"))
        for route in routes:
            hops = [{"host_id": host_id, "position": index} for index, host_id in enumerate(route["path"])]
            conn.execute("INSERT INTO routes VALUES(?,?,?,?)", (route["route_id"], route["profile"], json.dumps(hops, separators=(",", ":")), route["provenance"]))
        conn.execute("INSERT INTO windows VALUES(?,?,?,?,?)", (scenario_id, "Bounded preview from converted source rows", start_t, end_t, "scenarios/%s.json" % scenario_id))
        conn.commit(); conn.execute("VACUUM")
    finally:
        conn.close()


def _evaluation(records, routes):
    benign = [row for row in records if row["semantic"] == "benign"]
    malicious = [row for row in records if row["semantic"] != "benign"]
    n = len(records)
    split = max(1, int(n * 0.8)) if n else 0
    test = records[split:]
    positives = sum(row["semantic"] != "benign" for row in test)
    negatives = sum(row["semantic"] == "benign" for row in test)
    # This is intentionally the ground-truth label playback baseline. It does not
    # train a detector and is therefore not presented as detection performance.
    return {
        "detector_evaluation": {
            "status": "computed-trivial-label-playback",
            "method": "time-ordered 80/20 split; label column replayed as prediction",
            "training_events": split, "test_events": len(test), "test_positive_events": positives,
            "precision": 1.0 if positives else None, "recall": 1.0 if positives else None,
            "f1": 1.0 if positives else None, "false_positive_rate": 0.0 if negatives else None,
            "limitations": ["Trivial label replay uses the held-out ground-truth label itself; it is not a predictive detector evaluation."]
        },
        "precog_evaluation": {"status": "requires-at-least-five-routes" if len(routes) < 5 else "not-run-by-builder",
            "routes_available": len(routes), "reason": "No held-out real route metric is reported until the per-source route review and evaluation are completed."},
        "counts": {"events_used": n, "benign": len(benign), "labelled": len(malicious)},
        "limitations": [
            "This record is a builder output from the selected source files and selected event cap; it does not represent the full public dataset.",
            "Host compromise and routes are labelled only where the card describes the explicit source-derived rule; they are not inferred facts about successful intrusion.",
            "The label-playback baseline is tautological and must not be described as predictive detection performance.",
            "Containment and forecasts in the application are simulated counterfactuals over recorded data.",
        ]
    }


def _scenario(dataset_id, events):
    items = []
    for event in events:
        if event["src"] is None or event["dst"] is None:
            continue
        if event["label"] is None:
            continue
        offset = min(7_200_000, max(0, event["t"]))
        items.append({"seq": len(items) + 1, "offset_ms": offset, "kind": "traffic", "severity": event["severity"],
            "packets": [{"src_host": event["src"], "dst_host": event["dst"], "protocol": event["protocol"],
                "src_port": 0, "dst_port": event["port"], "size": max(1, event["bytes"] or 1)}]})
        if len(items) >= 200:
            break
    if not items and events:
        first = events[0]
        target = first["dst"] or first["src"]
        items = [{"seq": 1, "offset_ms": 0, "kind": "technique", "host": target, "technique_id": "T1046", "compromise": False, "severity": "LOW", "note": "Recorded-source preview; no attack truth inferred."}]
    return {"scenario_id": dataset_id, "description": "Dataset replay preview; recorded events are a simulation input, not live traffic.", "events": items}


def build_real_dataset_pack(dataset_id, raw_paths, output_dir, *, seed=0, max_hosts=400, max_events=50_000, contracts_dir=None):
    """Build a validated, source-attributed pack from explicitly supplied raw files.

    The resulting pack contains no raw addresses or user IDs. It is not published
    into the workspace registry automatically; redistribution status still gates use.
    """
    if dataset_id not in SPECS:
        raise PackError("Unknown real dataset id %r" % dataset_id)
    if not (0 <= int(seed) <= 2**31 - 1) or not (1 <= int(max_hosts) <= MAX_HOSTS) or not (1 <= int(max_events) <= MAX_EVENTS):
        raise PackError("seed, max_hosts, or max_events is outside the documented bounds")
    spec = SPECS[dataset_id]
    paths = sorted(Path(path).resolve() for path in raw_paths)
    records = parse_dataset(dataset_id, paths, MAX_ROWS_SCANNED, max_events)
    records.sort(key=lambda row: (row["raw_t"], row["source_file"], row["source_row"]))
    if len(records) > max_events:
        records = records[:max_events]
    frequencies = Counter()
    for row in records:
        frequencies[row["raw_src"]] += 1
        frequencies[row["raw_dst"]] += 1
    redteam_frequency = Counter()
    if spec.parser == "lanl":
        for row in records:
            if row.get("is_redteam"):
                redteam_frequency[row["raw_src"]] += 1
                redteam_frequency[row["raw_dst"]] += 1
    selected = {raw for raw, _ in sorted(redteam_frequency.items(), key=lambda item: (-item[1], item[0]))[:max_hosts]}
    for raw, _ in sorted(frequencies.items(), key=lambda item: (-item[1], item[0])):
        if len(selected) >= max_hosts:
            break
        selected.add(raw)
    if len(selected) < 2:
        raise PackError("Selected source window has fewer than two endpoints")
    host_map = {raw: _host_id(raw, seed) for raw in sorted(selected)}
    records = [row for row in records if row["raw_src"] in host_map and row["raw_dst"] in host_map]
    if not records:
        raise PackError("No events remain after deterministic host sampling")
    t0 = records[0]["raw_t"]
    events, edge_map, service_map = [], {}, defaultdict(set)
    class_semantics = {}
    for index, row in enumerate(records, 1):
        src, dst = host_map[row["raw_src"]], host_map[row["raw_dst"]]
        relative_t = max(0, row["raw_t"] - t0)
        semantic = row["semantic"]
        label = row["label"]
        attack_class = _safe_label(label) if semantic != "benign" else "benign"
        if semantic != "benign":
            class_semantics[attack_class] = semantic
        severity = "HIGH" if semantic in ("access-attempt", "command-and-control", "lateral-movement") else "MEDIUM" if semantic == "impact-only" else "LOW"
        events.append({"event_id": index, "t": relative_t, "src": src, "dst": dst,
            "kind": "attempt" if semantic in ("access-attempt", "lateral-movement", "command-and-control") else "traffic",
            "severity": severity, "label": label if semantic != "benign" else None, "attack_class": attack_class,
            "protocol": row["protocol"], "port": row["dport"], "bytes": row["bytes"],
            "extra": {"provenance": "native-label" if label else "unlabeled", "source_file": row["source_file"], "source_row": row["source_row"],
                      "compromise_semantics": semantic, "pseudonymized_endpoints": True}})
        edge = edge_map.setdefault((src, dst), {"src": src, "dst": dst, "count": 0, "first_seen": relative_t, "last_seen": relative_t})
        edge["count"] += 1; edge["last_seen"] = relative_t
        if row["dport"]:
            service_map[dst].add("%s/%d" % (row["protocol"].lower(), row["dport"]))
    routes = _route_rows(records, spec, host_map)
    source_checksums = []
    for path in paths:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        source_checksums.append({"path": path.name, "sha256": digest.hexdigest()})
    hosts = [{"host_id": host_id, "name": "Asset " + host_id[-6:].upper(), "zone": "observed", "role": "network endpoint",
              "services": sorted(service_map[host_id])[:20]} for host_id in sorted(host_map.values())]
    observed_edges = sorted(edge_map.values(), key=lambda edge: (edge["src"], edge["dst"]))
    topology = {"network_id": dataset_id, "hosts": hosts, "feasible_edges": [{"src": edge["src"], "dst": edge["dst"]} for edge in observed_edges],
        "observed_edges": [{"src": edge["src"], "dst": edge["dst"], "count": edge["count"], "provenance": "derived-from-recorded-flows"} for edge in observed_edges],
        "assets": {host["host_id"]: {"services": host["services"], "criticality": 0.5, "source": "observed-records"} for host in hosts},
        "clusters": [{"id": "observed", "name": "Observed endpoints", "host_ids": [host["host_id"] for host in hosts]}]}
    scenario = _scenario(dataset_id, events)
    out = Path(output_dir)
    if out.is_symlink():
        raise PackError("Output directory cannot be a symbolic link")
    out = out.resolve()
    if out.name != dataset_id:
        raise PackError("Output directory must be named %s" % dataset_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".%s-build-" % dataset_id, dir=str(out.parent)))
    backup = out.parent / (".%s-backup" % dataset_id)
    try:
        (staging / "scenarios").mkdir()
        (staging / "topology.json").write_bytes(_canonical_json(topology))
        (staging / "scenarios" / (dataset_id + ".json")).write_bytes(_canonical_json(scenario))
        route_lines = [json.dumps(route, sort_keys=True, separators=(",", ":")) for route in routes]
        (staging / "routes.jsonl").write_text("\n".join(route_lines) + ("\n" if route_lines else ""), encoding="utf-8", newline="\n")
        _write_database(staging / "pack.sqlite", hosts, observed_edges, events, routes, 0, max(event["t"] for event in events), dataset_id)
        model_counts = {}
        for route in routes:
            for left, right in zip(route["path"], route["path"][1:]):
                model_counts.setdefault(left, {})[right] = model_counts.setdefault(left, {}).get(right, 0) + 1
        model = {"alpha": 0.1, "counts": model_counts, "meta": {"workspace_id": dataset_id, "model_type": "derived route Markov model" if routes else "no route model",
            "route_provenance": "native-redteam" if spec.parser == "lanl" else "derived" if routes else "none"}}
        (staging / "model.json").write_bytes(_canonical_json(model))
        evaluation = _evaluation(records, routes)
        (staging / "evaluation.json").write_bytes(_canonical_json(evaluation))
        (staging / "card.md").write_text("# %s\n\nSource: %s\n\n%s\n\n- Selected rows: %d (maximum %d); selected hosts: %d (maximum %d).\n- Raw endpoint identifiers are pseudonymized as stable IDs derived from the seed; raw addresses and user identifiers are not stored.\n- Detection labels: native source labels; label playback is a trivial baseline.\n- Host compromise: %s. Lateral routes: %s. Topology: %s.\n- Redistribution: **%s**. Do not ship this pack until its dataset card's rights and attribution gate is satisfied.\n- Evaluation: `evaluation.json` reports a tautological label-playback baseline; Precog route metrics are not reported unless a separate held-out route evaluation is performed.\n\n%s\n" % (
            spec.name, spec.url, spec.terms, len(events), max_events, len(hosts), max_hosts, spec.host_semantics, spec.route_semantics, spec.topology_semantics, spec.redistribution,
            "All forecasts, containment actions, and what-if results are estimates or counterfactuals over recorded data; they do not establish real attacker behavior or protection."), encoding="utf-8", newline="\n")
        has_labels = any(item["label"] is not None for item in events)
        compromise_basis = any(row["semantic"] in ("access-attempt", "lateral-movement", "command-and-control") for row in records)
        capabilities = {"detection_labels": "native" if has_labels else "none",
            "host_compromise": spec.host_semantics if compromise_basis else "none",
            "lateral_movement_routes": spec.route_semantics if routes else "none", "topology": "derived"}
        attacks = [{"id": class_id, "compromise_semantics": semantics if semantics != "benign" else "impact-only"} for class_id, semantics in sorted(class_semantics.items())]
        technique_mapping = [{"attack_class": item["id"], "technique_ids": [ATTACK_TECHNIQUES.get(item["compromise_semantics"], "T1046")],
            "assumption": "Mapping chosen for replay navigation from the dataset label; it is not an observed ATT&CK attribution."} for item in attacks]
        manifest = {"id": dataset_id, "name": spec.name, "version": "1.0.0", "builder_version": BUILDER_VERSION, "seed": int(seed),
            "created_at": "1970-01-01T00:00:00Z", "source": {"id": dataset_id, "name": spec.name,
                "citation": spec.citation + " Source: " + spec.url, "licence": spec.licence, "terms_summary": spec.terms},
            "redistribution": spec.redistribution, "size_bytes": 0,
            "counts": {"hosts": len(hosts), "edges": len(observed_edges), "events": len(events), "labelled_events": sum(item["label"] is not None for item in events),
                "routes": len(routes), "time_span_ms": max(item["t"] for item in events)},
            "capabilities": capabilities, "attack_classes": attacks, "technique_mapping": technique_mapping,
            "detector_options": ["labels", "graph-novelty"], "default_decision_policy": {"mode": "never", "threshold": 1.0, "minimum_candidates": 0},
            "display_hints": {"zones": ["observed"], "clusters": "observed-endpoint-group", "layout": "observed-network"},
            "source_file_checksums": source_checksums, "content_hash": "0" * 64}
        (staging / "manifest.json").write_bytes(_canonical_json(manifest))
        digest, size_bytes = _payload_hash(staging)
        if size_bytes > MAX_PACK_BYTES:
            raise PackError("Converted pack exceeds the 25 MiB payload budget; lower --max-events")
        manifest["content_hash"], manifest["size_bytes"] = digest, size_bytes
        (staging / "manifest.json").write_bytes(_canonical_json(manifest))
        validate_pack(staging, contracts_dir, require_matching_dir=False)
        if out.exists():
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(out, backup)
        try:
            os.replace(staging, out)
        except Exception:
            if backup.exists() and not out.exists():
                os.replace(backup, out)
            raise
        if backup.exists():
            shutil.rmtree(backup)
        return validate_pack(out, contracts_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
