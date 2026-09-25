"""Walidator wspólnego kontraktu paczki telefonu (contract/KONTRAKT.md, wersja 2).

Ten sam zestaw przypadków (contract/fixtures/cases.json) testują: ten moduł,
mobile/src/contract.js i mobile/api/lib/contract.php.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

SCHEMA_VERSION = 2
BRANDS = ("atlet", "rigger")
EVIDENCE = ("unknown", "scheduled", "published", "failed")
ROLES = ("video", "slide", "thumbnail", "caption", "hashtags")
TIKTOK_TRANSFER = ("published", "scheduled", "manual_checked")
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def package_id(brand: str, post_id: str) -> str:
    return f"{brand}--{post_id}"


def safe_name(name: Any) -> bool:
    return (isinstance(name, str) and bool(name) and name != "manifest.json" and not name.startswith(".")
            and "/" not in name and "\\" not in name and ".." not in name and len(name) <= 180)


def validate(manifest: Any) -> list[dict[str, str]]:
    """Zwraca listę błędów [{code, message}]; pusta lista = manifest poprawny."""
    errors: list[dict[str, str]] = []

    def err(code: str, message: str) -> None:
        errors.append({"code": code, "message": message})

    if not isinstance(manifest, dict):
        return [{"code": "FIELD", "message": "Brak manifestu"}]
    if manifest.get("schema_version") != SCHEMA_VERSION:
        err("SCHEMA", f"Nieobsługiwana wersja schematu: {manifest.get('schema_version')}")
    brand, post_id = manifest.get("brand"), manifest.get("post_id")
    if brand not in BRANDS:
        err("BRAND", f"Nieznana marka: {brand or 'brak'}")
    if manifest.get("channel") != "instagram":
        err("CHANNEL", f"Niewłaściwy kanał: {manifest.get('channel') or 'brak'}")
    if not isinstance(post_id, str) or not post_id.strip() or not safe_name(post_id):
        err("FIELD", "Brak lub zły post_id")
    elif manifest.get("package_id") != package_id(str(brand), post_id):
        err("FIELD", "package_id nie zgadza się z marką i post_id")
    if not isinstance(manifest.get("content_revision"), str) or not _HEX64.match(manifest["content_revision"]):
        err("FIELD", "content_revision musi być sumą SHA-256")
    exported = manifest.get("exported_at")
    if not isinstance(exported, str) or not _ISO_UTC.match(exported):
        err("FIELD", "exported_at musi być datą ISO UTC")
    else:
        try:
            datetime.fromisoformat(exported.replace("Z", "+00:00"))
        except ValueError:
            err("FIELD", "exported_at nie jest prawidłową datą")
    for key in ("caption", "hashtags", "location", "title"):
        if not isinstance(manifest.get(key, ""), str):
            err("FIELD", f"{key} musi być tekstem")
    kind = manifest.get("type")
    if kind not in ("reel", "carousel"):
        err("TYPE", f"Nieznany typ paczki: {kind or 'brak'}")

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        err("FILES", "Brak listy plików")
        files = []
    names: set[str] = set()
    roles: dict[str, list[dict]] = {r: [] for r in ROLES}
    for item in files:
        if not isinstance(item, dict):
            err("FILE_NAME", "Nieprawidłowy wpis pliku")
            continue
        name = item.get("name")
        if not safe_name(name):
            err("FILE_NAME", f"Niedozwolona nazwa pliku: {name}")
        elif name in names:
            err("FILE_NAME", f"Powtórzony plik: {name}")
        else:
            names.add(name)
        if item.get("role") not in ROLES:
            err("FILE_NAME", f"Nieznana rola pliku {name}: {item.get('role')}")
        else:
            roles[item["role"]].append(item)
        sha = item.get("sha256")
        if not isinstance(sha, str) or not _HEX64.match(sha):
            err("FILE_HASH", f"Zła suma SHA-256: {name}")
        size = item.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            err("FILE_HASH", f"Zły rozmiar pliku: {name}")
    if files:
        for role, label in (("thumbnail", "miniatury"), ("caption", "opisu"), ("hashtags", "hashtagów")):
            if len(roles[role]) != 1:
                err("ROLE_MISSING", f"Paczka musi mieć dokładnie jeden plik {label}")
        if kind == "reel" and not roles["video"]:
            err("ROLE_MISSING", "Rolka nie ma pliku wideo")
        if kind == "carousel":
            if len(roles["slide"]) < 2:
                err("ROLE_MISSING", "Karuzela musi mieć co najmniej 2 slajdy")
            orders = [x.get("order") for x in roles["slide"]]
            if any(not isinstance(o, int) or isinstance(o, bool) for o in orders) or len(set(orders)) != len(orders):
                err("ORDER", "Slajdy muszą mieć unikalną kolejność")

    platforms = manifest.get("platforms")
    if not isinstance(platforms, dict):
        err("PLATFORMS", "Brak stanów platform")
    else:
        for ch in ("tiktok", "instagram", "facebook"):
            p = platforms.get(ch)
            if not isinstance(p, dict) or p.get("evidence") not in EVIDENCE or not isinstance(p.get("manual_checked"), bool):
                err("PLATFORMS", f"Zły stan platformy: {ch}")
    transfer = manifest.get("transfer")
    if (not isinstance(transfer, dict) or transfer.get("from") != "tiktok" or transfer.get("to") != "instagram"
            or transfer.get("tiktok") not in TIKTOK_TRANSFER or transfer.get("instagram") != "pending"):
        err("TRANSFER", "Paczka musi opisywać transfer: TikTok gotowy, Instagram oczekuje")
    return errors


def is_valid(manifest: Any) -> bool:
    return not validate(manifest)
