"""Bounded, administrator-only uploads converted into validated local workspace packs."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .dataset_packs import PACK_ID, PACK_MAX_BYTES, PackError, _payload_hash, validate_pack

MAX_SCAN_ROWS = 2_000_000
MAX_PACK_EVENTS = 100_000
MAX_HOSTS = 500
MAX_ARCHIVE_ITEMS = 5000
MAX_FIELD_BYTES = 65536
MAX_ACTIVE_BUILDS = 1
MAX_OPEN_JOBS = 5
MAX_USER_PACKS = 20
MAX_USER_PACK_BYTES = 200 * 1024 * 1024
PACK_ROOT_FILES = {"manifest.json", "topology.json", "pack.sqlite", "routes.jsonl", "model.json", "evaluation.json", "card.md"}
SEMANTICS = {"none", "access-attempt", "impact-only", "reconnaissance", "command-and-control", "lateral-movement"}
ALLOWED_MAPPING = {"time_column", "src_column", "dst_column", "label_column", "zone_column", "protocol_column", "port_column", "bytes_column"}


class UploadError(ValueError):
    pass


def upload_limit():
    default = 50 * 1024 * 1024 if os.environ.get("RENDER") else 1024 * 1024 * 1024
    raw = os.environ.get("UPLOAD_MAX_BYTES", "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError as exc:
        raise ValueError("UPLOAD_MAX_BYTES must be an integer") from exc
    if value < 1024 or value > 1024 * 1024 * 1024:
        raise ValueError("UPLOAD_MAX_BYTES must be between 1 KiB and 1 GiB")
    if os.environ.get("RENDER") and value > 50 * 1024 * 1024:
        value = 50 * 1024 * 1024
    return value


def _clean_text(value, max_length=200):
    value = "".join(char for char in str(value or "") if ord(char) >= 32 and ord(char) != 127).strip()
    return value[:max_length]


def _slug(value):
    slug = re.sub(r"[^a-z0-9]+", "-", _clean_text(value, 200).casefold()).strip("-")
    return (slug or "dataset")[:48].strip("-") or "dataset"


def _parse_time(value, fallback):
    text = _clean_text(value, 100)
    try:
        number = float(text)
        if not (number == number and abs(number) != float("inf")):
            return fallback
        return int(number * 1000 if abs(number) < 100_000_000_000 else number)
    except (ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return int(parsed.timestamp() * 1000)
        except (ValueError, OverflowError):
            return fallback


def _safe_protocol(value):
    protocol = _clean_text(value, 16).upper()
    return protocol if protocol in ("TCP", "UDP", "ICMP") else "TCP"


def _bounded_int(value, low, high):
    try:
        number = int(float(value))
        return number if low <= number <= high else None
    except (ValueError, TypeError, OverflowError):
        return None


def _archive_layout(source):
    try:
        archive = zipfile.ZipFile(source)
    except (OSError, zipfile.BadZipFile) as exc:
        raise UploadError("The file is not a valid ZIP archive.") from exc
    infos = archive.infolist()
    if not infos or len(infos) > MAX_ARCHIVE_ITEMS:
        archive.close()
        raise UploadError("ZIP archives must contain 1 to 5,000 entries.")
    total = 0
    names = []
    for info in infos:
        name = info.filename
        path = PurePosixPath(name)
        mode = info.external_attr >> 16
        if (not name or "\\" in name or path.is_absolute() or ".." in path.parts or ":" in name or
                name.startswith("/") or stat.S_ISLNK(mode) or info.flag_bits & 1):
            archive.close()
            raise UploadError("ZIP contains an unsafe path, link, or encrypted entry.")
        total += info.file_size
        if info.file_size > PACK_MAX_BYTES or (info.file_size > 0 and info.compress_size == 0):
            archive.close()
            raise UploadError("ZIP entry exceeds the pack size limit or has an invalid compression size.")
        if info.compress_size and info.file_size / info.compress_size > 100:
            archive.close()
            raise UploadError("ZIP compression ratio exceeds the safe limit.")
        names.append(name)
    if total > PACK_MAX_BYTES:
        archive.close()
        raise UploadError("Expanded ZIP contents exceed the 25 MiB pack limit.")
    # Support a direct pack root or one enclosing directory, never arbitrary nesting.
    prefix = ""
    if "manifest.json" not in names:
        heads = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
        if len(heads) != 1 or not any(name == next(iter(heads)) + "/manifest.json" for name in names):
            archive.close()
            raise UploadError("ZIP must contain a pack manifest at its root or under one enclosing folder.")
        prefix = next(iter(heads)) + "/"
        for name in names:
            if not name.startswith(prefix) or len(PurePosixPath(name).parts) < 2:
                archive.close()
                raise UploadError("ZIP contains files outside its pack folder.")
    for name in names:
        relative = name[len(prefix):] if prefix else name
        path = PurePosixPath(relative)
        if not relative:
            continue
        valid_root = not name.endswith("/") and len(path.parts) == 1 and path.name in PACK_ROOT_FILES
        valid_scenario = not name.endswith("/") and len(path.parts) == 2 and path.parts[0] == "scenarios" and path.suffix == ".json"
        valid_directory = name.endswith("/") and path.parts == ("scenarios",)
        if not (valid_root or valid_scenario or valid_directory):
            archive.close()
            raise UploadError("ZIP contains a file outside the validated pack format.")
    return archive, prefix, total


class UploadManager:
    def __init__(self, data_root, packs_root, contracts_dir, template_pack=None, max_bytes=None):
        self.data_root = Path(data_root).resolve() / "uploads"
        self.packs_root = Path(packs_root).resolve()
        self.contracts_dir = Path(contracts_dir).resolve()
        self.template_pack = Path(template_pack or self.packs_root / "synth-enterprise-30").resolve()
        self.max_bytes = int(max_bytes or upload_limit())
        self.data_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._jobs = {}

    def _entry(self, job_id):
        if not isinstance(job_id, str) or not re.fullmatch(r"upload-[0-9a-f]{32}", job_id):
            raise UploadError("Unknown upload job.")
        entry = self._jobs.get(job_id)
        if not entry:
            raise UploadError("Unknown or expired upload job.")
        return entry

    def _summary(self, job_id, entry):
        result = {key: entry[key] for key in ("job_id", "filename", "state", "bytes_received", "size_limit", "message")}
        result["progress"] = entry.get("progress", 0)
        if entry.get("preview") is not None:
            result["preview"] = entry["preview"]
        if entry.get("pack_id"):
            result["pack_id"] = entry["pack_id"]
        return result

    def preview(self, file_storage, filename):
        with self._lock:
            active = sum(item["state"] in ("queued", "building") for item in self._jobs.values())
            if active >= MAX_ACTIVE_BUILDS:
                raise UploadError("Another upload build is active; retry when it finishes.")
            open_jobs = sum(item["state"] in ("preview", "queued", "building") for item in self._jobs.values())
            if open_jobs >= MAX_OPEN_JOBS:
                raise UploadError("Upload preview quota reached (5 open jobs). Cancel or finish a job before uploading another.")
        safe_name = _clean_text(filename, 255).replace("\\", "/").split("/")[-1] or "upload.bin"
        job_id = "upload-" + uuid.uuid4().hex
        folder = self.data_root / job_id
        folder.mkdir(mode=0o700, parents=True)
        source = folder / "source.bin"
        digest = hashlib.sha256()
        total = 0
        try:
            with source.open("xb") as target:
                while True:
                    chunk = file_storage.stream.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self.max_bytes:
                        raise UploadError("Upload exceeds the configured file-size limit.")
                    digest.update(chunk)
                    target.write(chunk)
            if total == 0:
                raise UploadError("Choose a non-empty file.")
            file_hash = digest.hexdigest()
            with source.open("rb") as stream:
                signature = stream.read(4)
            if signature == b"PK\x03\x04":
                archive, prefix, expanded = _archive_layout(source)
                archive.close()
                manifest = self._read_archive_manifest(source, prefix)
                preview = {"format": "pack-zip", "columns": [], "sample_rows": [], "row_estimate": manifest.get("counts", {}).get("events", 0),
                           "warnings": ["The pack is validated and installed locally after explicit build confirmation."],
                           "pack_name": _clean_text(manifest.get("name"), 200), "expanded_bytes": expanded}
            else:
                preview = self._raw_preview(source)
            entry = {"job_id": job_id, "filename": safe_name, "state": "preview", "bytes_received": total,
                     "size_limit": self.max_bytes, "message": "Format inspected. Confirm the licence acknowledgement and mapping before building.",
                     "progress": 0.1, "preview": preview, "source": source, "sha256": file_hash,
                     "folder": folder, "cancel": threading.Event(), "thread": None}
            with self._lock:
                self._jobs[job_id] = entry
            return self._summary(job_id, entry)
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise

    @staticmethod
    def _read_archive_manifest(source, prefix):
        with zipfile.ZipFile(source) as archive:
            try:
                raw = archive.read(prefix + "manifest.json")
                manifest = json.loads(raw.decode("utf-8"))
            except (KeyError, UnicodeError, json.JSONDecodeError, OSError) as exc:
                raise UploadError("ZIP pack manifest is missing or invalid JSON.") from exc
        if not isinstance(manifest, dict) or not isinstance(manifest.get("id"), str):
            raise UploadError("ZIP pack manifest needs an id.")
        return manifest

    @staticmethod
    def _raw_preview(source):
        try:
            with source.open("rb") as stream:
                for _ in range(10):
                    line = stream.readline(MAX_FIELD_BYTES + 2)
                    if not line:
                        break
                    if len(line) > MAX_FIELD_BYTES and not line.endswith((b"\n", b"\r")):
                        raise UploadError("Input contains an oversized line.")
            with source.open("r", encoding="utf-8-sig", newline="") as stream:
                text = stream.read(MAX_FIELD_BYTES + 1)
        except (UnicodeDecodeError, OSError) as exc:
            raise UploadError("Only UTF-8 CSV, TSV, or JSON event files are accepted.") from exc
        if len(text) > MAX_FIELD_BYTES and "\n" not in text and "\r" not in text:
            raise UploadError("Input contains an oversized line.")
        if any(len(line.encode("utf-8")) > MAX_FIELD_BYTES for line in text.splitlines()):
            raise UploadError("Input contains an oversized line.")
        if any(ord(char) == 0 or (ord(char) < 32 and char not in "\t\r\n") for char in text):
            raise UploadError("Binary or control-character input is not accepted.")
        if not text.strip():
            raise UploadError("File contains no data.")
        if text.lstrip().startswith(("{", "[")):
            if source.stat().st_size > 50 * 1024 * 1024:
                raise UploadError("JSON event uploads are limited to 50 MiB for bounded parsing.")
            try:
                payload = json.loads(source.read_text(encoding="utf-8-sig"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise UploadError("JSON events must be a JSON array or an object with an events array.") from exc
            rows = payload.get("events") if isinstance(payload, dict) else payload
            if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows[:100]):
                raise UploadError("JSON events must contain at least one event object.")
            columns = sorted({key for row in rows[:100] for key in row if isinstance(key, str)})
            return {"format": "json-events", "columns": columns[:100], "sample_rows": rows[:5],
                    "row_estimate": len(rows), "warnings": []}
        try:
            delimiter = "\t" if "\t" in text.splitlines()[0] and "," not in text.splitlines()[0] else ","
            reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
            columns = reader.fieldnames or []
            if not columns or len(columns) > 200 or any(not name or len(name) > 200 for name in columns):
                raise UploadError("CSV/TSV needs a header with at most 200 bounded column names.")
            rows = []
            for _, row in zip(range(5), reader):
                rows.append({key: _clean_text(value, 200) for key, value in row.items() if key})
        except csv.Error as exc:
            raise UploadError("CSV/TSV header could not be read safely.") from exc
        if not rows:
            raise UploadError("CSV/TSV must contain at least one row after its header.")
        return {"format": "tsv" if delimiter == "\t" else "csv", "columns": columns,
                "sample_rows": rows, "row_estimate": None, "warnings": ["Row count is computed during the bounded background build."]}

    def status(self, job_id):
        with self._lock:
            entry = self._entry(job_id)
            return self._summary(job_id, entry)

    def build(self, job_id, options):
        if not isinstance(options, dict) or options.get("license_ack") is not True:
            raise UploadError("Acknowledge that you have rights to process this file before building.")
        mapping = options.get("mapping", {})
        if not isinstance(mapping, dict) or set(mapping) - ALLOWED_MAPPING:
            raise UploadError("Column mapping contains unsupported fields.")
        semantics = options.get("compromise_semantics", "none")
        if semantics not in SEMANTICS:
            raise UploadError("Choose a supported compromise-semantics value.")
        name = _clean_text(options.get("name"), 200)
        if not name:
            raise UploadError("Dataset name is required.")
        with self._lock:
            entry = self._entry(job_id)
            if entry["state"] != "preview":
                raise UploadError("Only a previewed upload can be built.")
            active = sum(item["state"] in ("queued", "building") for item in self._jobs.values())
            if active >= MAX_ACTIVE_BUILDS:
                raise UploadError("Another upload build is active; retry when it finishes.")
            fmt = entry["preview"]["format"]
            if fmt != "pack-zip":
                columns = set(entry["preview"]["columns"])
                for key in ("time_column", "src_column", "dst_column"):
                    if not isinstance(mapping.get(key), str) or mapping[key] not in columns:
                        raise UploadError("Map a valid time, source, and destination column before building.")
                if mapping.get("label_column") and mapping["label_column"] not in columns:
                    raise UploadError("Mapped label column is not in the uploaded file.")
                if mapping.get("zone_column") and mapping["zone_column"] not in columns:
                    raise UploadError("Mapped zone column is not in the uploaded file.")
            entry.update(state="queued", message="Build queued.", progress=0.15)
            thread = threading.Thread(target=self._build, args=(entry, name, mapping, semantics,
                                                               bool(options.get("pseudonymize", True))),
                                      name=job_id, daemon=True)
            entry["thread"] = thread
            thread.start()
            return self._summary(job_id, entry)

    def cancel(self, job_id):
        with self._lock:
            entry = self._entry(job_id)
            if entry["state"] in ("installed", "failed", "cancelled"):
                raise UploadError("This upload job can no longer be cancelled.")
            entry["cancel"].set()
            if entry["state"] == "preview":
                entry.update(state="cancelled", message="Upload cancelled; staged source removed.", progress=0)
                shutil.rmtree(entry["folder"], ignore_errors=True)
            return self._summary(job_id, entry)

    def _set(self, entry, **fields):
        with self._lock:
            if entry["cancel"].is_set():
                entry.update(state="cancelled", message="Upload cancelled; temporary files removed.", progress=0)
            else:
                entry.update(fields)
            return entry["state"]

    def _build(self, entry, name, mapping, semantics, pseudonymize):
        staging = entry["folder"] / "pack-staging"
        try:
            if self._set(entry, state="building", message="Building a local validated workspace pack.", progress=0.2) == "cancelled":
                return
            if entry["preview"]["format"] == "pack-zip":
                pack_id = self._install_zip(entry, staging, name)
            else:
                pack_id = self._build_events(entry, staging, name, mapping, semantics, pseudonymize)
            if entry["cancel"].is_set():
                raise UploadError("Upload cancelled.")
            with self._lock:
                entry.update(state="installed", pack_id=pack_id, progress=1.0,
                             message="Validated local workspace installed. It is not active until selected.")
            _ = self
        except Exception as exc:
            state = "cancelled" if entry["cancel"].is_set() else "failed"
            with self._lock:
                entry.update(state=state, progress=0, message=_clean_text(exc, 1000) or "Upload build failed.")
        finally:
            shutil.rmtree(entry["folder"], ignore_errors=True)

    def _new_pack_id(self, name):
        base = "user-" + _slug(name)
        pack_id = base[:62].rstrip("-")
        if not PACK_ID.fullmatch(pack_id):
            pack_id = "user-dataset"
        if (self.packs_root / pack_id).exists():
            pack_id = (base[:52].rstrip("-") + "-" + uuid.uuid4().hex[:8])[:64]
        if not PACK_ID.fullmatch(pack_id) or (self.packs_root / pack_id).exists():
            raise UploadError("A unique local workspace ID could not be created.")
        return pack_id

    def _check_quota(self):
        packs = [path for path in self.packs_root.glob("user-*") if path.is_dir() and not path.is_symlink()]
        if len(packs) >= MAX_USER_PACKS:
            raise UploadError("Local upload quota reached (20 user packs).")
        total = sum(path.stat().st_size for folder in packs for path in folder.rglob("*") if path.is_file())
        if total >= MAX_USER_PACK_BYTES:
            raise UploadError("Local upload storage quota reached (200 MiB).")

    def _install_zip(self, entry, staging, name):
        self._check_quota()
        archive, prefix, _ = _archive_layout(entry["source"])
        staging.mkdir(parents=True, exist_ok=False)
        try:
            for info in archive.infolist():
                if entry["cancel"].is_set():
                    raise UploadError("Upload cancelled.")
                rel = info.filename[len(prefix):] if prefix else info.filename
                if not rel:
                    continue
                target = (staging / Path(*PurePosixPath(rel).parts)).resolve()
                if target != staging.resolve() and staging.resolve() not in target.parents:
                    raise UploadError("ZIP entry escapes its temporary pack folder.")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with archive.open(info) as source, target.open("xb") as destination:
                    while True:
                        block = source.read(256 * 1024)
                        if not block:
                            break
                        written += len(block)
                        if written > PACK_MAX_BYTES or entry["cancel"].is_set():
                            raise UploadError("ZIP extraction exceeded a safety limit or was cancelled.")
                        destination.write(block)
            manifest = json.loads((staging / "manifest.json").read_text(encoding="utf-8"))
            if manifest.get("id") == "demo-6":
                raise UploadError("The protected demo-6 workspace cannot be replaced by an upload.")
            pack_id = self._new_pack_id(name or manifest.get("name"))
            manifest["id"] = pack_id
            manifest["name"] = name or manifest.get("name")
            (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
            validate_pack(staging, self.contracts_dir, require_matching_dir=False)
            self._publish_pack(staging, pack_id)
            return pack_id
        finally:
            archive.close()

    def _publish_pack(self, staging, pack_id):
        target = self.packs_root / pack_id
        self.packs_root.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            raise UploadError("Workspace ID already exists.")
        digest, size = _payload_hash(staging)
        manifest_path = staging / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["content_hash"] = digest
        manifest["size_bytes"] = size
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        validate_pack(staging, self.contracts_dir, require_matching_dir=False)
        os.replace(staging, target)

    def _read_rows(self, source, preview, mapping):
        if preview["format"] == "json-events":
            if source.stat().st_size > 50 * 1024 * 1024:
                raise UploadError("JSON event uploads are limited to 50 MiB for bounded parsing.")
            payload = json.loads(source.read_text(encoding="utf-8-sig"))
            rows = payload.get("events") if isinstance(payload, dict) else payload
            if not isinstance(rows, list) or not rows:
                raise UploadError("JSON event array is empty.")
            for row in rows[:MAX_SCAN_ROWS]:
                if isinstance(row, dict):
                    yield row
            return
        previous_limit = csv.field_size_limit()
        csv.field_size_limit(MAX_FIELD_BYTES)
        try:
            delimiter = "\t" if preview["format"] == "tsv" else ","
            with source.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream, delimiter=delimiter)
                for index, row in enumerate(reader):
                    if index >= MAX_SCAN_ROWS:
                        break
                    yield row
        except (csv.Error, UnicodeError) as exc:
            raise UploadError("CSV/TSV contains an invalid encoding, row, or oversized field.") from exc
        finally:
            csv.field_size_limit(previous_limit)

    def _build_events(self, entry, staging, name, mapping, semantics, pseudonymize):
        self._check_quota()
        shutil.copytree(self.template_pack, staging)
        pack_id = self._new_pack_id(name)
        source_hash = entry["sha256"]
        preview = entry["preview"]
        host_ids = {}
        hosts = []
        zones = set()
        edges = {}
        first_time = None
        last_time = None
        inserted = 0
        labels = 0
        con = sqlite3.connect(staging / "pack.sqlite")
        try:
            con.execute("PRAGMA journal_mode=OFF")
            for table in ("hosts", "edges", "events", "routes", "labels", "windows"):
                con.execute("DELETE FROM " + table)
            for row_index, row in enumerate(self._read_rows(entry["source"], preview, mapping)):
                if entry["cancel"].is_set():
                    raise UploadError("Upload cancelled.")
                if not entry["preview"].get("row_estimate") and row_index and row_index % 10000 == 0:
                    self._set(entry, progress=min(0.85, 0.15 + row_index / MAX_SCAN_ROWS * 0.7), message="Reading and validating event rows.")
                source_raw = _clean_text(row.get(mapping["src_column"]), 512)
                target_raw = _clean_text(row.get(mapping["dst_column"]), 512)
                if not source_raw or not target_raw or source_raw == target_raw:
                    continue
                needed = [source_raw, target_raw]
                new_ids = [value for value in needed if value not in host_ids]
                if len(host_ids) + len(set(new_ids)) > MAX_HOSTS:
                    continue
                for endpoint in new_ids:
                    host_id = "user-host-%04d" % (len(host_ids) + 1)
                    host_ids[endpoint] = host_id
                    raw_zone = _clean_text(row.get(mapping.get("zone_column", "")) if mapping.get("zone_column") else "imported", 100) or "imported"
                    zone = raw_zone if not pseudonymize else _slug(raw_zone)[:80] or "imported"
                    zones.add(zone)
                    hosts.append({"host_id": host_id, "name": ("Endpoint %04d" % len(host_ids)) if pseudonymize else _clean_text(endpoint, 160),
                                  "zone": zone, "role": "endpoint", "criticality": 1.0, "services": [], "weaknesses": []})
                    con.execute("INSERT INTO hosts VALUES(?,?,?,?,?,?)", (host_id, hosts[-1]["name"], zone, "endpoint", 1.0, "{}"))
                source_id, target_id = host_ids[source_raw], host_ids[target_raw]
                raw_time = row.get(mapping["time_column"])
                timestamp = _parse_time(raw_time, row_index)
                first_time = timestamp if first_time is None else min(first_time, timestamp)
                last_time = timestamp if last_time is None else max(last_time, timestamp)
                label = _clean_text(row.get(mapping.get("label_column", "")) if mapping.get("label_column") else "", 160) or None
                malicious = bool(label and label.casefold() not in ("benign", "normal", "0", "false"))
                attack_class = "user-imported-label" if malicious else "user-imported-background"
                severity = "MEDIUM" if malicious else "LOW"
                protocol = _safe_protocol(row.get(mapping.get("protocol_column", "")) if mapping.get("protocol_column") else "TCP")
                port = _bounded_int(row.get(mapping.get("port_column", "")) if mapping.get("port_column") else None, 0, 65535)
                byte_count = _bounded_int(row.get(mapping.get("bytes_column", "")) if mapping.get("bytes_column") else None, 1, 65535)
                if inserted < MAX_PACK_EVENTS:
                    cursor = con.execute("INSERT INTO events(t,src,dst,kind,severity,label,attack_class,protocol,port,bytes,extra_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                         (timestamp, source_id, target_id, "traffic", severity, label, attack_class, protocol, port, byte_count, "{}"))
                    if label:
                        labels += 1
                        con.execute("INSERT INTO labels(event_id,label,provenance) VALUES(?,?,?)", (cursor.lastrowid, label, "user-provided"))
                    pair = (source_id, target_id)
                    aggregate = edges.get(pair)
                    if aggregate is None:
                        edges[pair] = [1, timestamp, timestamp]
                    else:
                        aggregate[0] += 1
                        aggregate[1] = min(aggregate[1], timestamp)
                        aggregate[2] = max(aggregate[2], timestamp)
                    inserted += 1
            if not inserted:
                raise UploadError("No event rows with distinct source and destination hosts could be built.")
            origin = first_time or 0
            con.execute("UPDATE events SET t=t-?", (origin,))
            for (source_id, target_id), (count, first, last) in edges.items():
                con.execute("INSERT INTO edges VALUES(?,?,?,?,?,?,?)", (source_id, target_id, "observed", count, first-origin, last-origin, "derived-from-upload"))
            con.execute("INSERT INTO windows VALUES(?,?,?,?,?)", ("user-import-preview", "Imported event sample", 0, max(0, (last_time or origin)-origin), "user-import-preview.json"))
            con.commit()
        finally:
            con.close()

        topology_path = staging / "topology.json"
        topology = json.loads(topology_path.read_text(encoding="utf-8"))
        feasible = [{"src": src, "dst": dst, "provenance": "derived-from-upload"} for src, dst in sorted(edges)]
        observed = [{"src": src, "dst": dst, "count": values[0], "first_seen": values[1]-first_time, "last_seen": values[2]-first_time,
                     "provenance": "derived-from-upload"} for (src, dst), values in sorted(edges.items())]
        topology.update(network_id=pack_id, hosts=hosts, feasible_edges=feasible, observed_edges=observed,
                        assets={host["host_id"]: {"services": [], "weaknesses": []} for host in hosts}, clusters=[])
        topology_path.write_text(json.dumps(topology, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        scenarios = staging / "scenarios"
        shutil.rmtree(scenarios)
        scenarios.mkdir()
        scenario = {"scenario_id": "user-import-preview", "description": "SIMULATION: preview of uploaded, pseudonymized events; records remain immutable.",
                    "events": [{"seq": 1, "offset_ms": 0, "kind": "traffic", "packets": [{"src_host": hosts[0]["host_id"], "dst_host": hosts[1]["host_id"] if len(hosts) > 1 else hosts[0]["host_id"], "protocol": "TCP", "dst_port": 0, "size": 1}]}]}
        # The preview event references two distinct endpoints, as guaranteed by the import filter.
        scenario["events"][0]["packets"][0]["dst_host"] = next(iter(edges))[1]
        scenario_path = scenarios / "user-import-preview.json"
        scenario_path.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8", newline="\n")
        (staging / "routes.jsonl").write_text("", encoding="utf-8", newline="\n")
        (staging / "model.json").write_text(json.dumps({"alpha": 1.0, "counts": {}, "meta": {"source": "uploaded-events", "routes": 0}}, indent=2) + "\n", encoding="utf-8", newline="\n")
        limitations = ["This pack was built from a user upload and has not been independently evaluated.",
                       "Routes and forecasts are unsupported because ordered compromise routes were not provided.",
                       "Topology is derived from observed flow endpoints and is not a verified network inventory."]
        (staging / "evaluation.json").write_text(json.dumps({"status": "not-evaluated", "limitations": limitations}, indent=2) + "\n", encoding="utf-8", newline="\n")
        (staging / "card.md").write_text("# " + name + "\n\nUser-provided, local-only event pack. Raw upload is discarded after conversion.\n\n" + "\n".join("- " + line for line in limitations) + "\n", encoding="utf-8", newline="\n")
        manifest_path = staging / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        has_labels = bool(mapping.get("label_column"))
        can_compromise = has_labels and semantics in ("access-attempt", "command-and-control", "lateral-movement")
        manifest.update({"id": pack_id, "name": name, "builder_version": "precog-upload-builder/1.0.0",
                         "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                         "source": {"id": "user-upload", "name": name, "citation": "User-provided source; citation supplied by uploader.",
                                    "licence": "User acknowledged local processing rights.", "terms_summary": "Local-only; not redistributed by this project."},
                         "redistribution": "user-provided-local-only", "seed": 0,
                         "counts": {"hosts": len(hosts), "edges": len(edges), "events": inserted, "labelled_events": labels,
                                    "routes": 0, "time_span_ms": max(0, (last_time or first_time or 0) - (first_time or 0))},
                         "capabilities": {"detection_labels": "native" if has_labels else "none", "host_compromise": "derived" if can_compromise else "none",
                                          "lateral_movement_routes": "none", "topology": "derived"},
                         "attack_classes": [{"id": "user-imported-label", "compromise_semantics": semantics if semantics != "none" else "impact-only"},
                                            {"id": "user-imported-background", "compromise_semantics": "impact-only"}],
                         "technique_mapping": [{"attack_class": "user-imported-label", "technique_ids": [], "assumption": "Uploaded labels are retained as labels; no ATT&CK technique is inferred."}],
                         "detector_options": ["labels", "graph-novelty"] if has_labels else ["graph-novelty"],
                         "default_decision_policy": {"mode": "never", "threshold": 1.0, "minimum_candidates": 0},
                         "display_hints": {"zones": sorted(zones), "clusters": "zone", "layout": "uploaded-endpoint-map"},
                         "source_file_checksums": [{"path": "user-upload", "sha256": source_hash}]})
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        self._publish_pack(staging, pack_id)
        return pack_id
