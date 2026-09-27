from __future__ import annotations

import re
from datetime import datetime
from typing import Any

CHANNELS = ("tiktok", "instagram", "facebook")
DONE = {"opublikowany", "published"}
RUNNING = {"running", "w_toku", "przygotowuje", "wysylanie"}
WAITING = {"awaiting_user", "gotowe_do_klikniecia", "czeka_na_muzyke"}


_EDGE_START = re.compile(r"^[^\w„\"'(]+")
_EDGE_END = re.compile(r"[^\w?!.…)\"'”]+$")
_SENTENCE = re.compile(r"(?<=[.!?…])\s+")


def headline(description: str, fallback: str = "", limit: int = 72) -> str:
    """Tytuł karty zamiast nazwy pliku: pierwszy akapit opisu (opisy są łamane co ~25 znaków),
    bez ozdobników na brzegach, przycięty do pierwszego pełnego zdania, gdy jest za długi."""
    paragraph: list[str] = []
    for line in str(description or "").splitlines():
        line = line.strip()
        if line.startswith("#"): continue
        if not line or not _EDGE_START.sub("", line):
            if paragraph and not line: break
            continue
        paragraph.append(line)
    text = _EDGE_END.sub("", _EDGE_START.sub("", " ".join(paragraph))).strip()
    if len(text) < 3: return fallback
    text = text[0].upper() + text[1:]
    if len(text) <= limit: return text
    head = ""
    for part in _SENTENCE.split(text):
        head = f"{head} {part}".strip()
        if len(head) >= 16 and not head.lower().endswith((" vs.", " np.", " tj.", " itp.")): break
    if 16 <= len(head) <= limit: return _EDGE_END.sub("", head) if head[-1] not in "?!.…" else head
    return text[:limit - 1].rsplit(" ", 1)[0].rstrip(",;:-–—") + "…"


def channel_view(raw: dict[str, Any] | None, *, manual_checked: bool = False) -> dict[str, Any]:
    state = dict(raw or {})
    legacy = str(state.get("stan") or "czeka").lower()
    evidence = str(state.get("platform_evidence") or state.get("dowod") or "unknown").lower()
    if evidence == "unknown" and legacy == "potwierdzony":
        evidence = "scheduled"  # LIVE nie rozstrzyga publikacji bez czasu/rodzaju wpisu.
    delivery = str(state.get("delivery") or "idle").lower()
    if delivery == "idle" and legacy in RUNNING:
        delivery = "running"
    if delivery == "idle" and legacy in WAITING:
        delivery = "awaiting_user"
    return {
        "delivery": delivery,
        "platform_evidence": evidence if evidence in {"unknown", "scheduled", "published", "failed"} else "unknown",
        "manual_checked": bool(manual_checked),
        "local_target_at": state.get("local_target_at") or "",
        "platform_target_at": state.get("platform_target_at") or state.get("termin") or "",
        "evidence_source": state.get("evidence_source") or ("legacy_live" if legacy == "potwierdzony" else ""),
        "observed_at": state.get("observed_at") or state.get("kiedy") or "",
        "url": state.get("url") or "",
        "info": state.get("info") or "",
        "attempts": state.get("proby") or [],
        "legacy_state": legacy,
    }


def next_action(card: dict[str, Any], selected_channel: str = "instagram") -> dict[str, str]:
    ch = card.get("channels", {}).get(selected_channel, {})
    if ch.get("delivery") in {"running", "awaiting_user"}:
        return {"code": "show_progress", "channel": selected_channel, "label": "Pokaż postęp", "reason": "Aktywne zadanie wymaga dokończenia."}
    if card.get("archived"):
        return {"code": "show_history", "channel": selected_channel, "label": "Pokaż historię", "reason": "Paczka jest w archiwum."}
    if ch.get("delivery") in {"submitted", "unknown"} and ch.get("legacy_state") == "wyslany":
        return {"code": "verify", "channel": selected_channel, "label": "Sprawdź na platformie", "reason": "Wysłano, ale brak wiarygodnego wyniku."}
    if ch.get("platform_evidence") == "published" and ch.get("manual_checked"):
        return {"code": "done", "channel": selected_channel, "label": "Zakończone", "reason": "Dowód i ręczne potwierdzenie są zgodne."}
    if ch.get("platform_evidence") in {"scheduled", "published"} and not ch.get("manual_checked"):
        return {"code": "manual_check", "channel": selected_channel, "label": "Sprawdź i potwierdź", "reason": "Platforma ma wpis, ale brakuje haczyka użytkownika."}
    if ch.get("delivery") == "failed" or ch.get("platform_evidence") == "failed":
        return {"code": "diagnose", "channel": selected_channel, "label": "Pokaż błąd", "reason": ch.get("info") or "Publikacja wymaga diagnozy."}
    missing = card.get("assets", {}).get("missing", [])
    if missing or not card.get("content", {}).get("description", "").strip():
        return {"code": "finish", "channel": selected_channel, "label": "Uzupełnij paczkę", "reason": ", ".join(missing) or "Brakuje opisu."}
    if not card.get("content", {}).get("approved", False):
        return {"code": "review_content", "channel": selected_channel, "label": "Sprawdź opis", "reason": "Ta wersja treści nie została zaakceptowana."}
    if not ch.get("local_target_at") and not card.get("local_target_at"):
        return {"code": "schedule", "channel": selected_channel, "label": "Wybierz termin", "reason": "Brak lokalnego terminu."}
    if selected_channel == "instagram":
        return {"code": "phone_package", "channel": selected_channel, "label": "Przygotuj na telefon", "reason": "Instagram jest domyślnie kończony na telefonie."}
    return {"code": "publish", "channel": selected_channel, "label": f"Przygotuj {selected_channel.title()}", "reason": "Paczka jest gotowa do istniejącego procesu."}


def counts(cards: list[dict[str, Any]]) -> dict[str, int]:
    active = [x for x in cards if not x.get("archived")]
    return {
        "all": len(active),
        "action": sum(1 for x in active if x.get("next_action", {}).get("code") not in {"done", "show_history"}),
        "phone": sum(1 for x in active if x.get("phone_ready")),
        "running": sum(1 for x in active if any(c.get("delivery") in {"running", "awaiting_user"} for c in x.get("channels", {}).values())),
        "review": sum(1 for x in active if any(c.get("platform_evidence") != "unknown" and not c.get("manual_checked") for c in x.get("channels", {}).values())),
        "completed": sum(1 for x in active if all(c.get("manual_checked") for c in x.get("channels", {}).values() if c)),
    }

