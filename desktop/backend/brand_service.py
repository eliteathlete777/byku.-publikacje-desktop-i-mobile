"""Marki, styl komunikacji, hashtagi, lokalizacje i szkice opisów.

Szkice powstają lokalnie z szablonu marki i aktywnych lekcji stylu — bez zewnętrznego AI.
Pełny Generator (stary proces 8765) pozostaje dostępny przez LegacyBridge.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from learning.store import LearningStore
from learning.style_lessons import active_rules

from .content_service import normalize_hashtags

DEFAULTS = Path(__file__).resolve().parents[1] / "defaults" / "brands.json"
LIST_FIELDS = ("hooks", "ctas", "fixed_hashtags", "rotating_hashtags", "banned_words", "locations", "posting_slots", "structure")
IG_HASHTAG_LIMIT = 30
IG_CAPTION_LIMIT = 2200


class BrandService:
    def __init__(self, data_dir: Path, learning: LearningStore):
        self.file = data_dir / "brands.json"
        self.learning = learning

    def all(self) -> dict[str, dict]:
        brands = json.loads(DEFAULTS.read_text(encoding="utf-8"))
        if self.file.is_file():
            for key, value in json.loads(self.file.read_text(encoding="utf-8")).items():
                if key in brands and isinstance(value, dict):
                    brands[key].update(value)
        return brands

    def get(self, brand: str) -> dict:
        brands = self.all()
        if brand not in brands:
            raise ValueError("Nieznana marka")
        return brands[brand]

    def update(self, brand: str, patch: dict) -> dict:
        current = self.get(brand)
        clean: dict[str, Any] = {}
        for key, value in patch.items():
            if key in LIST_FIELDS:
                if not isinstance(value, list):
                    raise ValueError(f"{key} musi być listą")
                items = [str(x).strip() for x in value if str(x).strip()]
                if key.endswith("hashtags"):
                    items = normalize_hashtags(" ".join(items)).split()
                clean[key] = items
            elif key in ("name", "handle", "tone"):
                clean[key] = str(value).strip()
            elif key in ("caption_min", "caption_max", "rotating_count"):
                clean[key] = max(0, int(value))
            elif key == "posting_days":
                clean[key] = sorted({int(x) for x in value if 0 <= int(x) <= 6})
        merged = {**current, **clean}
        if merged["caption_min"] > merged["caption_max"] or merged["caption_max"] > IG_CAPTION_LIMIT:
            raise ValueError("Zakres długości opisu jest nieprawidłowy (maks. 2200 znaków)")
        stored = json.loads(self.file.read_text(encoding="utf-8")) if self.file.is_file() else {}
        stored[brand] = {**stored.get(brand, {}), **clean}
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.file)
        return self.get(brand)

    # ---------- hashtagi ----------
    def hashtags_for(self, brand: str, post_id: str, variant: int = 0) -> str:
        profile = self.get(brand)
        rotating = list(profile.get("rotating_hashtags", []))
        count = min(int(profile.get("rotating_count", 2)), len(rotating))
        picked: list[str] = []
        if rotating and count:
            start = (int(hashlib.sha256(post_id.encode()).hexdigest(), 16) + variant * count) % len(rotating)
            picked = [rotating[(start + i) % len(rotating)] for i in range(count)]
        return normalize_hashtags(" ".join(profile.get("fixed_hashtags", []) + picked))

    # ---------- szkice opisu ----------
    def draft(self, brand: str, post_id: str, topic: str, count: int = 3) -> list[dict]:
        profile = self.get(brand)
        hooks, ctas = profile.get("hooks") or [""], profile.get("ctas") or [""]
        topic = topic.strip() or "Dzisiejsza robota"
        seed = int(hashlib.sha256(post_id.encode()).hexdigest(), 16)
        drafts = []
        for i in range(count):
            hook = hooks[(seed + i) % len(hooks)]
            cta = ctas[(seed + 2 * i) % len(ctas)]
            text = f"{hook}\n\n{topic.rstrip('.')}.\n\n{cta}"
            text = self._fit(text, profile)
            drafts.append({"variant": i + 1, "description": text, "hashtags": self.hashtags_for(brand, post_id, i),
                           "lint": self.lint(brand, text, self.hashtags_for(brand, post_id, i))})
        return drafts

    @staticmethod
    def _fit(text: str, profile: dict) -> str:
        limit = int(profile.get("caption_max", IG_CAPTION_LIMIT))
        if len(text) <= limit:
            return text
        cut = text[: limit - 1]
        return cut[: cut.rfind(" ")].rstrip(" ,.;") + "…" if " " in cut else cut + "…"

    def lint(self, brand: str, description: str, hashtags: str) -> list[dict]:
        profile = self.get(brand)
        notes = []
        length = len(description.strip())
        if length < int(profile.get("caption_min", 0)):
            notes.append({"level": "warn", "text": f"Opis ma {length} znaków — marka zakłada min. {profile['caption_min']}."})
        if length > int(profile.get("caption_max", IG_CAPTION_LIMIT)):
            notes.append({"level": "error", "text": f"Opis ma {length} znaków — limit marki to {profile['caption_max']}."})
        lowered = description.lower()
        for word in profile.get("banned_words", []):
            if word.lower() in lowered:
                notes.append({"level": "error", "text": f"Zakazane słowo marki: „{word}”."})
        tags = hashtags.split()
        if len(tags) > IG_HASHTAG_LIMIT:
            notes.append({"level": "error", "text": f"{len(tags)} hashtagów — Instagram przyjmie maks. {IG_HASHTAG_LIMIT}."})
        missing = [t for t in profile.get("fixed_hashtags", []) if t.lower() not in {x.lower() for x in tags}]
        if tags and missing:
            notes.append({"level": "info", "text": "Brak stałych hashtagów marki: " + " ".join(missing)})
        return notes

    def style_examples(self, brand: str, limit: int = 5) -> list[dict]:
        rules = active_rules(self.learning, brand)[:limit]
        out = []
        for rule in rules:
            evidence = json.loads(rule.get("evidence_json") or "{}")
            out.append({"lesson_id": rule["lesson_id"], "version": rule["version"], "after": rule.get("solution", ""),
                        "post_id": evidence.get("post_id", "") if isinstance(evidence, dict) else ""})
        return out

    def snapshot(self) -> dict:
        return copy.deepcopy(self.all())
