from __future__ import annotations

import ftplib
import hashlib
import json
import os
import posixpath
from pathlib import Path

from .config import Settings

PASSWORD_ENV = "BYKU_HOSTINGER_FTP_PASSWORD"


class HostingerSync:
    """Wysyła paczki telefonu (index.json + foldery do-instagrama) na Hostinger przez FTPS.

    Hasło nigdy nie trafia do config.json ani repozytorium — tylko zmienna środowiskowa.
    Wysyłane są wyłącznie pliki zmienione od ostatniej udanej wysyłki; index.json idzie
    zawsze na końcu, żeby telefon nigdy nie zobaczył manifestu bez jego plików.
    """

    def __init__(self, settings: Settings, root: Path, ftp_factory=None):
        self.cfg = settings.hostinger
        self.root = root
        self.state_file = settings.data_dir / "hostinger-sync.json"
        self.ftp_factory = ftp_factory

    def status(self) -> dict:
        missing = [k for k in ("host", "user", "remote_dir") if not str(self.cfg.get(k, "")).strip()]
        if not os.environ.get(PASSWORD_ENV) and not self.ftp_factory: missing.append(PASSWORD_ENV)
        return {"enabled": bool(self.cfg.get("enabled")), "configured": not missing, "missing": missing,
                "public_url": self.cfg.get("public_url", ""), "remote_dir": self.cfg.get("remote_dir", "")}

    def local_files(self) -> list[Path]:
        files = [p for p in self.root.glob("*/do-instagrama/**/*") if p.is_file()]
        return sorted(files, key=lambda p: (p.name == "manifest.json", p.as_posix()))

    @staticmethod
    def digest(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
        return h.hexdigest()

    def _connect(self):
        if self.ftp_factory: return self.ftp_factory()
        ftp = ftplib.FTP_TLS(timeout=60) if self.cfg.get("tls", True) else ftplib.FTP(timeout=60)
        ftp.connect(self.cfg["host"], int(self.cfg.get("port", 21)))
        ftp.login(self.cfg["user"], os.environ[PASSWORD_ENV])
        if isinstance(ftp, ftplib.FTP_TLS): ftp.prot_p()
        return ftp

    @staticmethod
    def _ensure_dir(ftp, path: str, known: set[str]):
        parts, current = [x for x in path.split("/") if x], ""
        for part in parts:
            current = f"{current}/{part}" if current else part
            if current in known: continue
            try: ftp.mkd(current)
            except ftplib.error_perm: pass  # katalog już istnieje
            known.add(current)

    def publish(self) -> dict:
        st = self.status()
        if not st["enabled"]: raise PermissionError("Wysyłka na Hostinger jest wyłączona w config.json (hostinger.enabled)")
        if not st["configured"]: raise PermissionError("Brakuje konfiguracji Hostingera: " + ", ".join(st["missing"]))
        index = self.root / "index.json"
        if not index.is_file(): raise FileNotFoundError("Brak index.json — najpierw przygotuj paczkę na telefon")
        try: state = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError): state = {}
        remote_root = str(self.cfg["remote_dir"]).strip("/")
        uploaded, skipped, known = [], 0, set()
        ftp = self._connect()
        try:
            for file in self.local_files() + [index]:
                rel = file.relative_to(self.root).as_posix()
                sha = self.digest(file)
                if rel != "index.json" and state.get(rel) == sha:
                    skipped += 1; continue
                remote = posixpath.join(remote_root, rel)
                self._ensure_dir(ftp, posixpath.dirname(remote), known)
                with file.open("rb") as stream: ftp.storbinary(f"STOR {remote}", stream)
                state[rel] = sha; uploaded.append(rel)
                self.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        finally:
            try: ftp.quit()
            except Exception: pass
        return {"uploaded": len(uploaded), "skipped": skipped, "files": uploaded, "public_url": self.cfg.get("public_url", "")}
