"""Settings for the add-ons. Everything comes from environment variables (see .env.example)."""
import os
from dataclasses import dataclass
from pathlib import Path


def _flag(name, default):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Config:
    repo_root: Path
    contracts_dir: Path
    web_dist: Path
    data_mode: str            # "sample" or "live"
    validate_contracts: bool
    cookie_secure: bool

    @staticmethod
    def from_env(repo_root):
        repo_root = Path(repo_root).resolve()
        data_mode = os.environ.get("DATA_MODE", "sample").strip().lower()
        if data_mode not in ("sample", "live"):
            raise ValueError("DATA_MODE must be 'sample' or 'live', not %r" % data_mode)
        web_dist = os.environ.get("WEB_DIST")
        return Config(
            repo_root=repo_root,
            contracts_dir=repo_root / "contracts",
            web_dist=Path(web_dist).resolve() if web_dist else repo_root / "web" / "dist",
            data_mode=data_mode,
            validate_contracts=_flag("VALIDATE_CONTRACTS", True),
            cookie_secure=_flag("COOKIE_SECURE", False),
        )
