from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    source_root: Path
    production_queue: Path
    sandbox_queue: Path
    data_dir: Path
    host: str
    port: int
    mode: str
    allow_publication: bool
    allow_production_writes: bool
    timezone: str
    core: str = "auto"
    drive_sync_dir: Path | None = None
    drive_folder_ids: dict = field(default_factory=dict)
    mobile_server_url: str = ""
    mobile_upload_token: str = ""

    @property
    def queue(self) -> Path:
        return self.production_queue if self.mode == "production" else self.sandbox_queue

    @property
    def writes_allowed(self) -> bool:
        return self.mode != "production" or self.allow_production_writes


def _read_env(path: Path) -> dict[str, str]:
    """Lokalny plik .env (poza repozytorium) — sekrety nigdy nie trafiają do config.json."""
    values: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_settings(config_path: Path | None = None) -> Settings:
    config_path = config_path or Path(os.environ.get("BYKU_DESKTOP_CONFIG") or ROOT / "config.json")
    base = config_path.parent
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    env = {**_read_env(ROOT / ".env"), **os.environ}

    def path(value: str) -> Path:
        if os.sep == "/":
            value = value.replace("\\", "/")
        p = Path(value)
        return p if p.is_absolute() else (base / p).resolve()

    drive = raw.get("google_drive", {}) or {}
    mobile = raw.get("mobile_server", {}) or {}
    cfg = Settings(
        source_root=path(raw["source_root"]), production_queue=path(raw["production_queue"]),
        sandbox_queue=path(raw["sandbox_queue"]), data_dir=path(raw["data_dir"]),
        host=str(raw.get("host", "127.0.0.1")), port=int(raw.get("port", 8902)),
        mode=str(raw.get("mode", "sandbox")),
        allow_publication=bool(raw.get("allow_publication", False)),
        allow_production_writes=bool(raw.get("allow_production_writes", False)),
        timezone=str(raw.get("timezone", "Europe/Warsaw")),
        core=str(raw.get("core", "auto")),
        drive_sync_dir=path(drive["local_sync_dir"]) if drive.get("local_sync_dir") else None,
        drive_folder_ids={"root": drive.get("root_folder_id", ""), **(drive.get("brand_folder_ids") or {})},
        mobile_server_url=str(mobile.get("url", "")).rstrip("/"),
        mobile_upload_token=str(env.get("BYKU_MOBILE_UPLOAD_TOKEN", "")),
    )
    if cfg.mode not in {"sandbox", "production"}:
        raise ValueError("mode musi być sandbox albo production")
    if cfg.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Desktop nasłuchuje wyłącznie lokalnie (127.0.0.1)")
    cfg.sandbox_queue.mkdir(parents=True, exist_ok=True)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    return cfg
