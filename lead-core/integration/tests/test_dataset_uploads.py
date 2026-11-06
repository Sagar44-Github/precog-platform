import io
import shutil
import time
import zipfile
from pathlib import Path

import pytest
from werkzeug.datastructures import FileStorage

from addons.uploads import UploadError, UploadManager
from addons.dataset_packs import validate_pack

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def upload_manager(flask_app, tmp_path):
    extensions = flask_app.extensions
    workspaces = extensions["precog_workspaces"]
    old_root = workspaces.store.root
    packs = tmp_path / "packs"
    packs.mkdir()
    shutil.copytree(ROOT / "packs" / "demo-6", packs / "demo-6")
    workspaces.store.root = packs
    old_uploads = extensions.get("precog_uploads")
    manager = UploadManager(tmp_path / "data", packs, extensions["precog"]["config"].contracts_dir,
                            template_pack=ROOT / "packs" / "synth-enterprise-30", max_bytes=2 * 1024 * 1024)
    extensions["precog_uploads"] = manager
    try:
        yield manager
    finally:
        workspaces.store.root = old_root
        extensions["precog_uploads"] = old_uploads


def _wait(manager, job_id):
    for _ in range(200):
        state = manager.status(job_id)
        if state["state"] not in ("queued", "building"):
            return state
        time.sleep(0.025)
    raise AssertionError("upload job did not finish")


def test_csv_upload_builds_a_valid_local_pack_through_routes(logged_in, flask_app, upload_manager):
    csv_data = "time,src,dst,label,zone\n0,10.0.0.1,10.0.0.2,scan,office\n1000,10.0.0.2,10.0.0.3,exploit,server\n"
    preview = logged_in.post("/api/x/workspaces/upload/preview", data={"file": (io.BytesIO(csv_data.encode()), "flows.csv")}, content_type="multipart/form-data")
    assert preview.status_code == 202, preview.get_json()
    job = preview.get_json()
    assert job["preview"]["format"] == "csv"
    assert job["preview"]["columns"] == ["time", "src", "dst", "label", "zone"]
    built = logged_in.post("/api/x/workspaces/upload/jobs/%s/build" % job["job_id"], json={
        "name": "Local Flow Fixture", "license_ack": True, "pseudonymize": True,
        "compromise_semantics": "access-attempt",
        "mapping": {"time_column": "time", "src_column": "src", "dst_column": "dst", "label_column": "label", "zone_column": "zone"},
    })
    assert built.status_code == 202
    final = _wait(upload_manager, job["job_id"])
    assert final["state"] == "installed", final["message"]
    manifest = validate_pack(upload_manager.packs_root / final["pack_id"], flask_app.extensions["precog"]["config"].contracts_dir)
    assert manifest["id"] == "user-local-flow-fixture"
    assert manifest["counts"]["events"] == 2
    assert manifest["capabilities"]["lateral_movement_routes"] == "none"
    assert "10.0.0.1" not in (upload_manager.packs_root / final["pack_id"] / "topology.json").read_text(encoding="utf-8")
    assert any(item["id"] == final["pack_id"] for item in logged_in.get("/api/x/workspaces").get_json()["workspaces"])
    removed = logged_in.delete("/api/x/workspaces/%s" % final["pack_id"])
    assert removed.status_code == 200
    assert not (upload_manager.packs_root / final["pack_id"]).exists()


def test_valid_pack_zip_is_reidentified_and_installed(logged_in, upload_manager):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        base = ROOT / "packs" / "synth-enterprise-30"
        for path in base.rglob("*"):
            if path.is_file():
                archive.write(path, (Path("workspace") / path.relative_to(base)).as_posix())
    buffer.seek(0)
    preview = logged_in.post("/api/x/workspaces/upload/preview", data={"file": (buffer, "pack.zip")}, content_type="multipart/form-data")
    assert preview.status_code == 202, preview.get_json()
    job_id = preview.get_json()["job_id"]
    accepted = logged_in.post("/api/x/workspaces/upload/jobs/%s/build" % job_id, json={"name": "ZIP Fixture", "license_ack": True})
    assert accepted.status_code == 202
    final = _wait(upload_manager, job_id)
    assert final["state"] == "installed", final["message"]
    assert final["pack_id"].startswith("user-zip-fixture")
    validate_pack(upload_manager.packs_root / final["pack_id"])


def test_upload_rejects_viewer_wrong_content_type_and_missing_csrf(client, upload_manager):
    viewer = client.post("/api/x/login", json={"username": "viewer", "password": "test-viewer-password"})
    assert viewer.status_code == 200
    denied = client.post("/api/x/workspaces/upload/preview", data={"file": (io.BytesIO(b"a,b\n1,2\n"), "a.csv")}, content_type="multipart/form-data")
    assert denied.status_code == 403
    client.post("/api/x/logout", json={})
    client.post("/api/x/login", json={"username": "admin", "password": "test-admin-password"})
    wrong_type = client.post("/api/x/workspaces/upload/preview", data=b"not multipart", content_type="text/plain", headers={"X-Precog-Request": "1"})
    assert wrong_type.status_code == 415
    no_csrf = client.post("/api/x/workspaces/upload/preview", data={"file": (io.BytesIO(b"time,src,dst\n0,a,b\n"), "a.csv")}, content_type="multipart/form-data", headers={"X-Precog-Request": ""})
    assert no_csrf.status_code == 403


def test_upload_rejects_zip_slip_zip_bomb_binary_huge_lines_and_oversize(upload_manager, tmp_path):
    unsafe = io.BytesIO()
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("../escape.txt", "bad")
    unsafe.seek(0)
    with pytest.raises(UploadError, match="unsafe path"):
        upload_manager.preview(FileStorage(stream=unsafe, filename="unsafe.zip"), "unsafe.zip")

    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", b"A" * 100_000)
    bomb.seek(0)
    with pytest.raises(UploadError, match="compression ratio"):
        upload_manager.preview(FileStorage(stream=bomb, filename="bomb.zip"), "bomb.zip")

    for content, filename, error in ((b"\x00\xff\x00", "junk.bin", "UTF-8"),
                                     (b"time,src,dst\n0," + b"x" * 70_000, "long.csv", "oversized line")):
        with pytest.raises(UploadError, match=error):
            upload_manager.preview(FileStorage(stream=io.BytesIO(content), filename=filename), filename)

    tiny = UploadManager(tmp_path / "tiny", upload_manager.packs_root, upload_manager.contracts_dir,
                         template_pack=upload_manager.template_pack, max_bytes=64)
    with pytest.raises(UploadError, match="size limit"):
        tiny.preview(FileStorage(stream=io.BytesIO(b"x" * 100), filename="too.csv"), "too.csv")


def test_zip_rejects_unexpected_executable_files_and_preview_quota(upload_manager):
    archive_data = io.BytesIO()
    with zipfile.ZipFile(archive_data, "w") as archive:
        archive.writestr("manifest.json", "{}")
        archive.writestr("run.py", "raise SystemExit()")
    archive_data.seek(0)
    with pytest.raises(UploadError, match="outside the validated pack format"):
        upload_manager.preview(FileStorage(stream=archive_data, filename="unexpected.zip"), "unexpected.zip")

    jobs = [upload_manager.preview(FileStorage(stream=io.BytesIO(b"time,src,dst\n0,a,b\n"), filename="flow.csv"), "flow.csv")
            for _ in range(5)]
    with pytest.raises(UploadError, match="preview quota"):
        upload_manager.preview(FileStorage(stream=io.BytesIO(b"time,src,dst\n0,a,b\n"), filename="sixth.csv"), "sixth.csv")
    for job in jobs:
        upload_manager.cancel(job["job_id"])


def test_upload_acknowledgement_cancel_and_local_quota(upload_manager, tmp_path):
    preview = upload_manager.preview(FileStorage(stream=io.BytesIO(b"time,src,dst\n0,a,b\n"), filename="flow.csv"), "flow.csv")
    with pytest.raises(UploadError, match="rights"):
        upload_manager.build(preview["job_id"], {"name": "no ack"})
    cancelled = upload_manager.cancel(preview["job_id"])
    assert cancelled["state"] == "cancelled"
    assert not (upload_manager.data_root / preview["job_id"]).exists()

    capped = UploadManager(tmp_path / "capped", tmp_path / "capped-packs", upload_manager.contracts_dir,
                           template_pack=upload_manager.template_pack)
    capped.packs_root.mkdir()
    for index in range(20):
        (capped.packs_root / ("user-%02d" % index)).mkdir()
    with pytest.raises(UploadError, match="quota"):
        capped._check_quota()


def test_default_upload_store_is_runtime_data_not_the_repository_pack_tree(flask_app):
    manager = flask_app.extensions["precog_workspaces"]
    uploads = flask_app.extensions["precog_uploads"]
    expected = (flask_app.extensions["precog"]["config"].data_dir / "user_packs").resolve()
    assert uploads.packs_root == expected
    assert uploads.packs_root != (ROOT / "packs").resolve()
    assert uploads.packs_root in manager.store.roots
