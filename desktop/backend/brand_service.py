"""Marki, styl, słowa kluczowe, lokalizacje i szkice opisów.

Jedynym źródłem zasad są kompendia stylu (desktop/style/*.md). Profil marki (defaults/brands.json)
przenosi je na banki tekstów, kolejność sekcji i reguły kontroli. Szkice powstają lokalnie, bez AI.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from learning.store import LearningStore
from learning.style_lessons import active_rules

from .content_service import normalize_hashtags

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "defaults" / "brands.json"
STYLE_DIR = ROOT / "style"
BANKS = ("hooks", "scenes", "merytoryka", "closings", "facts", "side", "questions", "ctas", "closers")
LIST_FIELDS = BANKS + ("hook_emojis", "allowed_hook_emojis", "keywords", "fixed_hashtags", "rotating_hashtags", "banned_words",
                       "avoid_phrases", "style_rules", "required_words", "locations", "posting_slots", "structure", "sections")
TAG_MODES = ("keywords", "hashtags")
IG_HASHTAG_LIMIT = 30
IG_CAPTION_LIMIT = 2200
VOWELS = "aeiouyąęó"


class BrandService:
    def __init__(self, data_dir: Path, learning: LearningStore, style_source: Path | None = None):
        self.file = data_dir / "brands.json"
        self.learning = learning
        self.style_source = style_source

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
        clean = self._validated(brand, patch)
        stored = json.loads(self.file.read_text(encoding="utf-8")) if self.file.is_file() else {}
        stored[brand] = {**stored.get(brand, {}), **clean}
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.file)
        return self.get(brand)

    def preview(self, brand: str, patch: dict, topic: str, sample: str = "") -> dict:
        """Szkice i kontrola z niezapisanych ustawień panelu stylu. Nic nie zapisuje."""
        profile = {**self.get(brand), **self._validated(brand, patch)}
        return {"drafts": self.draft(brand, "podglad-stylu", topic, profile=profile),
                "sample_lint": self.lint(brand, sample, "", profile=profile) if sample.strip() else []}

    def _validated(self, brand: str, patch: dict) -> dict:
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
            elif key in ("name", "handle", "tone", "forbidden_address"):
                clean[key] = str(value).strip()
            elif key in ("caption_min", "caption_max", "rotating_count"):
                clean[key] = max(0, int(value))
            elif key in ("max_dashes", "max_exclaims"):
                clean[key] = None if value in (None, "") else max(0, int(value))
            elif key == "hook_no_question":
                clean[key] = bool(value)
            elif key == "posting_days":
                clean[key] = sorted({int(x) for x in value if 0 <= int(x) <= 6})
            elif key == "tag_mode":
                if value not in TAG_MODES:
                    raise ValueError("tag_mode: keywords albo hashtags")
                clean[key] = value
        merged = {**current, **clean}
        if merged["caption_min"] > merged["caption_max"] or merged["caption_max"] > IG_CAPTION_LIMIT:
            raise ValueError("Zakres długości opisu jest nieprawidłowy (maks. 2200 znaków)")
        return clean

    # ---------- kompendium stylu ----------
    def compendium(self, brand: str) -> dict:
        name = self.get(brand).get("compendium", "")
        local = STYLE_DIR / name
        if not name or not local.is_file():
            return {"file": name, "markdown": "", "version": "", "source_newer": False}
        text = local.read_text(encoding="utf-8")
        version = next((line.strip() for line in text.splitlines() if line.startswith("Wersja")), "")
        source = self.style_source / name if self.style_source else None
        newer = bool(source and source.is_file() and source.read_bytes() != local.read_bytes())
        return {"file": name, "markdown": text, "version": version, "source": str(source or ""), "source_newer": newer}

    def reimport_compendium(self, brand: str) -> dict:
        name = self.get(brand).get("compendium", "")
        source = self.style_source / name if self.style_source and name else None
        if not source or not source.is_file():
            raise ValueError("Nie znaleziono pliku kompendium w folderze źródłowym (config.json: style_source_dir).")
        STYLE_DIR.mkdir(exist_ok=True)
        shutil.copyfile(source, STYLE_DIR / name)
        return self.compendium(brand)

    # ---------- hashtagi / słowa kluczowe ----------
    def hashtags_for(self, brand: str, post_id: str, variant: int = 0, profile: dict | None = None) -> str:
        profile = profile or self.get(brand)
        if profile.get("tag_mode") == "keywords":
            return ""
        rotating = list(profile.get("rotating_hashtags", []))
        count = min(int(profile.get("rotating_count", 2)), len(rotating))
        picked: list[str] = []
        if rotating and count:
            start = (int(hashlib.sha256(post_id.encode()).hexdigest(), 16) + variant * count) % len(rotating)
            picked = [rotating[(start + i) % len(rotating)] for i in range(count)]
        return normalize_hashtags(" ".join(profile.get("fixed_hashtags", []) + picked))

    # ---------- szkice opisu ----------
    def draft(self, brand: str, post_id: str, topic: str, count: int = 3, profile: dict | None = None) -> list[dict]:
        """Sekcje w kolejności z profilu (kompendium). „a|b” = na zmianę między wariantami, „x?” = sekcja opcjonalna,
        „scene” = scena z opisu posta albo z banku. Za krótki szkic dostaje kolejny akapit z pad_key."""
        profile = profile or self.get(brand)
        seed = int(hashlib.sha256(post_id.encode()).hexdigest(), 16)
        scene = " ".join(topic.split()).rstrip(".")
        minimum = int(profile.get("caption_min", 0))
        pad_key = profile.get("pad_key", "")
        drafts = []
        for i in range(count):
            pick = lambda key, k, extra=0: (lambda bank: bank[((seed >> (8 * k)) + i + extra) % len(bank)] if bank else "")(profile.get(key) or [])
            parts: list[tuple[str, str]] = []
            for k, sec in enumerate(profile.get("sections") or ["hooks", "scene", "merytoryka", "questions", "closers"]):
                optional = sec.endswith("?")
                key = sec.rstrip("?")
                if optional and i % 2:
                    continue
                if "|" in key:
                    options = key.split("|")
                    key = options[i % len(options)]
                if key == "scene":
                    text = f"{scene}." if scene else pick("scenes", k)
                elif key == "hooks":
                    text = self._hook(profile, pick("hooks", k), (seed >> 8) + i)
                else:
                    text = pick(key, k)
                if text:
                    parts.append((key, text))
            bank = profile.get(pad_key) or []
            used = {t for key, t in parts if key == pad_key}
            spare = [t for t in bank if t not in used]
            while spare and len("\n\n".join(t for _, t in parts)) < minimum:
                where = max((n for n, (key, _) in enumerate(parts) if key == pad_key), default=len(parts) - 2)
                parts.insert(where + 1, (pad_key, spare.pop((seed + i) % len(spare))))
            text = self._fit("\n\n".join(t for _, t in parts), profile)
            tags = self.hashtags_for(brand, post_id, i, profile=profile)
            drafts.append({"variant": i + 1, "description": text, "hashtags": tags,
                           "lint": self.lint(brand, text, tags, profile=profile)})
        return drafts

    @staticmethod
    def _hook(profile: dict, hook: str, n: int) -> str:
        if not hook:
            return hook
        allowed = (profile.get("allowed_hook_emojis") or []) + (profile.get("hook_emojis") or [])
        lead = next((e for e in allowed if hook.startswith(e)), "")
        if lead:
            return hook if hook.rstrip().endswith(lead) else f"{hook.rstrip()} {lead}"
        emojis = profile.get("hook_emojis") or []
        if not emojis:
            return hook
        e = emojis[n % len(emojis)]
        return f"{e} {hook} {e}"

    @staticmethod
    def _banned_pattern(word: str) -> re.Pattern:
        # Rdzeń + do 3 liter końcówki łapie odmiany (grawitacji, systemu), a nie łapie innych słów
        # (tego ≠ ego, systematycznie ≠ system, materac ≠ matrix). Krótkie słowa tylko w całości.
        w = word.lower()
        if len(w) <= 3:
            return re.compile(r"(?<!\w)" + re.escape(w) + r"(?!\w)")
        stem = w[:-1] if len(w) >= 5 and w[-1] in VOWELS else w
        return re.compile(r"(?<!\w)" + re.escape(stem) + r"\w{0,3}(?!\w)")

    @staticmethod
    def _fit(text: str, profile: dict) -> str:
        limit = int(profile.get("caption_max", IG_CAPTION_LIMIT))
        if len(text) <= limit:
            return text
        cut = text[: limit - 1]
        return cut[: cut.rfind(" ")].rstrip(" ,.;") + "…" if " " in cut else cut + "…"

    # ---------- kontrola (lista „kontrola przed oddaniem” z kompendium) ----------
    def lint(self, brand: str, description: str, hashtags: str, profile: dict | None = None) -> list[dict]:
        profile = profile or self.get(brand)
        notes: list[dict] = []
        add = lambda level, text: notes.append({"level": level, "text": text})
        text = description.strip()
        lowered = text.lower()
        length = len(text)
        if length < int(profile.get("caption_min", 0)):
            add("warn", f"Opis ma {length} znaków. Marka zakłada {profile['caption_min']}–{profile['caption_max']}.")
        if length > int(profile.get("caption_max", IG_CAPTION_LIMIT)):
            add("error", f"Opis ma {length} znaków. Limit marki to {profile['caption_max']}.")

        hook = text.split("\n", 1)[0].strip() if text else ""
        allowed = profile.get("allowed_hook_emojis") or []
        if hook and allowed:
            forms = lambda e: {e, e.replace("️", "")}
            if not any(hook.startswith(f) and hook.endswith(f) for e in allowed for f in forms(e)):
                add("warn", f"Hak: to samo emoji z zestawu ({' '.join(allowed)}) na początku i na końcu linii.")
        if hook and profile.get("hook_no_question") and "?" in hook:
            add("warn", "Hak ma być stwierdzeniem z kadru, nie pytaniem.")

        for word in profile.get("banned_words", []):
            if self._banned_pattern(word).search(lowered):
                add("error", f"Zakazane słowo marki: „{word}”.")
        for phrase in profile.get("avoid_phrases", []):
            if phrase.lower() in lowered:
                add("warn", f"Ogólnik albo metafora spoza stylu: „{phrase}”. Napisz to konkretniej.")
        for short, full, *exceptions in profile.get("full_name_checks", []):
            checked = lowered
            for exc in exceptions:
                checked = checked.replace(exc.lower(), "")
            if checked.count(short.lower()) > checked.count(full.lower()):
                add("warn", f"Pisz pełną nazwą: „…{full}”, a nie samo „{short}”.")
        if "—" in text:
            add("error", "Długi myślnik „—” jest zakazany. Kropka, przecinek albo zwykły „-”.")
        dashes = len(re.findall(r"(?<=\s)-(?=\s)", text))
        if profile.get("max_dashes") is not None and dashes > profile["max_dashes"]:
            add("warn", f"{dashes} myślniki „-”. Marka pozwala na {profile['max_dashes']}.")
        if profile.get("max_exclaims") is not None and text.count("!") > profile["max_exclaims"]:
            add("warn", f"{text.count('!')} wykrzykniki. Marka pozwala na {profile['max_exclaims']}.")
        address = profile.get("forbidden_address") or ""
        if address and re.search(r"(?<!\w)" + re.escape(address) + r"(?!\w)", text):
            add("warn", f"W opisach tej marki bez zwrotu „{address}” (wolno tylko w rolkach mówionych).")
        for word in profile.get("required_words", []):
            if word.lower() not in lowered:
                add("warn", f"Brakuje „{word}”. Pytanie-wyzwanie zawsze z tym zwrotem.")
        if "**" in text:
            add("warn", "Pogrubień „**…**” Instagram nie pokazuje. Usuń gwiazdki.")
        for para in text.split("\n\n"):
            sentences = len(re.findall(r"[.!?…](?=\s|$)", para))
            if sentences > 3:
                add("info", f"Akapit ma {sentences} zdania. Nowy akapit co 2–3 zdania.")
                break
        if any(re.search(r"[^\s.!?…:👇]\n\S", para) for para in text.split("\n\n")[1:]):
            add("info", "Linia łamana w środku zdania. Pisz pełnymi zdaniami, akapit to jeden blok tekstu.")

        tags = hashtags.split()
        if profile.get("tag_mode") == "keywords":
            if tags or re.search(r"(?<!\w)#\w", text):
                add("warn", "Ta marka używa słów kluczowych zamiast hashtagów. Usuń „#”.")
            missing_kw = [k for k in profile.get("keywords", []) if k.lower() not in lowered]
            if missing_kw:
                add("info", "Brak słów kluczowych w opisie: " + ", ".join(missing_kw))
            return notes
        if len(tags) > IG_HASHTAG_LIMIT:
            add("error", f"{len(tags)} hashtagów. Instagram przyjmie maks. {IG_HASHTAG_LIMIT}.")
        missing = [t for t in profile.get("fixed_hashtags", []) if t.lower() not in {x.lower() for x in tags}]
        if tags and missing:
            add("info", "Brak stałych hashtagów marki: " + " ".join(missing))
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
