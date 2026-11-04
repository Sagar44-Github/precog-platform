"""Run the hosted-readiness checker against a local single-worker Flask server."""
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"


def available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    if not PYTHON.is_file():
        raise SystemExit("Create the backend environment at .venv before running this check.")

    port = available_port()
    password = secrets.token_urlsafe(24)
    with tempfile.TemporaryDirectory(prefix="precog-hosted-audit-") as temporary:
        temp_path = Path(temporary).resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
        if temp_root not in temp_path.parents:
            raise RuntimeError("The temporary database path is outside the system temp directory.")
        database = (temp_path / "nids.sqlite").as_posix()
        env = os.environ.copy()
        env.update({
            "SECRET_KEY": secrets.token_hex(32),
            "ADMIN_PASSWORD": password,
            "DATABASE_URL": "sqlite:///" + database,
            "DATA_MODE": "live",
            "HOST": "127.0.0.1",
            "PORT": str(port),
            "COOKIE_SECURE": "0",
            "AUTO_TRAIN_MODEL": "0",
            "PUSH_WATCHER": "0",
        })
        env.pop("WEB_DIST", None)
        log_path = temp_path / "backend.log"
        with log_path.open("w", encoding="utf-8") as log:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            server = subprocess.Popen(
                [str(PYTHON), str(REPO_ROOT / "lead-core" / "backend" / "run_app.py")],
                cwd=REPO_ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
            try:
                url = "http://127.0.0.1:%d" % port
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    if server.poll() is not None:
                        break
                    try:
                        with urllib.request.urlopen(url + "/api/x/health", timeout=2) as response:
                            if response.status == 200:
                                break
                    except (urllib.error.URLError, TimeoutError):
                        time.sleep(0.25)
                else:
                    raise RuntimeError("The local backend did not become ready.")

                if server.poll() is not None:
                    raise RuntimeError("The local backend exited before readiness.")
                sys.path.insert(0, str(REPO_ROOT / "lead-core" / "integration"))
                from check_hosted import Checker

                ready = Checker(url).run(password)
                print("READY for the demo" if ready else "NOT ready: fix the lines marked FAIL")
                return 0 if ready else 1
            finally:
                if server.poll() is None:
                    server.terminate()
                    try:
                        server.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
