from __future__ import annotations

import json
from dataclasses import dataclass
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

    @property
    def queue(self) -> Path:
        return self.production_queue if self.mode == "production" else self.sandbox_queue


def load_settings() -> Settings:
    raw = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    def path(key: str) -> Path:
        value = Path(raw[key])
        return value if value.is_absolute() else (ROOT / value).resolve()
    cfg = Settings(
        source_root=path("source_root"), production_queue=path("production_queue"),
        sandbox_queue=path("sandbox_queue"), data_dir=path("data_dir"),
        host=str(raw.get("host", "127.0.0.1")), port=int(raw.get("port", 8899)),
        mode=str(raw.get("mode", "sandbox")),
        allow_publication=bool(raw.get("allow_publication", False)),
        allow_production_writes=bool(raw.get("allow_production_writes", False)),
        timezone=str(raw.get("timezone", "Europe/Warsaw")),
    )
    cfg.sandbox_queue.mkdir(parents=True, exist_ok=True)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    if cfg.mode not in {"sandbox", "production"}:
        raise ValueError("mode musi być sandbox albo production")
    return cfg

