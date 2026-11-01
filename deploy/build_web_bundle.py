"""Build the web app and copy it into the backend's hosted static bundle.

Run from the repository root with ``python deploy/build_web_bundle.py``.
"""

import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE = REPO_ROOT / "lead-core" / "backend" / "web_dist"


def copy_dist(source, target):
    """Replace the hosted bundle with a built app and return its file count."""
    source = Path(source)
    target = Path(target)
    if not (source / "index.html").is_file():
        raise SystemExit(
            "%s has no index.html: the web app was not built. "
            "Run 'npm run build' in the web folder first." % source
        )
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return sum(1 for path in target.rglob("*") if path.is_file())


def main():
    web_dir = REPO_ROOT / "web"
    npm = "npm.cmd" if sys.platform == "win32" else "npm"

    print("Installing web dependencies ...")
    result = subprocess.run([npm, "ci"], cwd=str(web_dir))
    if result.returncode != 0:
        raise SystemExit("'npm ci' failed (exit code %d). Fix the web project first." % result.returncode)

    print("Building the web app ...")
    result = subprocess.run([npm, "run", "build"], cwd=str(web_dir))
    if result.returncode != 0:
        raise SystemExit("'npm run build' failed (exit code %d). Fix the build errors first." % result.returncode)

    count = copy_dist(web_dir / "dist", BUNDLE)
    print("Copied %d files to %s" % (count, BUNDLE))
    print("Commit lead-core/backend/web_dist and push to deploy.")


if __name__ == "__main__":
    main()
