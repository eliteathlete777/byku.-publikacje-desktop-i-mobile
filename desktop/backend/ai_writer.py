"""Układanie opisu z „podstawy opisu” przez Claude, według kompendium stylu marki.

Kompendium idzie w całości jako instrukcja systemowa (stała, cache'owana), podstawa jako wiadomość.
Model zwraca 3 warianty w ustalonym JSON-ie; kontrolę zgodności robi potem BrandService.lint.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SCHEMA = {
    "type": "object",
    "properties": {
        "warianty": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "opis": {"type": "string"},
                    "mechanizm_haka": {"type": "string"},
                    "brakujace_konkrety": {"type": "string"},
                },
                "required": ["opis", "mechanizm_haka", "brakujace_konkrety"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["warianty"],
    "additionalProperties": False,
}

TASK = """Piszesz opisy postów dla marki {name} ({handle}). Poniższe kompendium to jedyne źródło zasad: struktura, ton, długość, emoji haka, słowa kluczowe, zakazane słowa, zwrot do widza, liczba myślników i wykrzykników. Stosuj je dosłownie.

Treść opisu bierzesz wyłącznie z „podstawy opisu” podanej przez Damiana oraz z faktów zapisanych w kompendium. Podstawa to jego surowy, często dyktowany materiał: ułóż go w tym stylu, zachowaj jego sposób mówienia i popraw tylko oczywiste przekłamania z dyktowania. Nie dopisuj miejsc, liczb, nazw, ćwiczeń ani zdarzeń, których nie ma w podstawie ani w kompendium. Jeśli czegoś brakuje, napisz ogólniej i wymień w polu brakujace_konkrety, jaki konkret podniósłby tekst (puste pole, gdy niczego nie brakuje).

Zwróć dokładnie {count} warianty. Każdy to kompletny opis gotowy do wklejenia, od haka do linii słów kluczowych, {min}–{max} znaków ze spacjami. Warianty mają się różnić mechanizmem haka i typem pytania albo CTA; w polu mechanizm_haka nazwij mechanizm z kompendium. Akapity oddzielaj pustą linią.

=== KOMPENDIUM STYLU ===
{compendium}"""


class AIWriterError(RuntimeError):
    pass


class BasisStore:
    """Podstawa opisu per post, w danych appki (data/podstawy.json). Paczki w kolejce zostają nietknięte."""

    def __init__(self, file: Path):
        self.file = file

    def _all(self) -> dict:
        return json.loads(self.file.read_text(encoding="utf-8")) if self.file.is_file() else {}

    def get(self, post_id: str) -> str:
        return self._all().get(post_id, "")

    def set(self, post_id: str, text: str) -> str:
        data = self._all()
        text = text.strip()
        if text:
            data[post_id] = text
        else:
            data.pop(post_id, None)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.file)
        return text


def sdk_available() -> bool:
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def _default_client(api_key: str):
    try:
        import anthropic
    except ImportError as exc:
        raise AIWriterError("Brak biblioteki anthropic. Zainstaluj: python -m pip install anthropic") from exc
    return anthropic.Anthropic(api_key=api_key, timeout=180.0)


def compose(profile: dict, compendium: str, basis: str, *, post_name: str, post_type: str, location: str,
            api_key: str, count: int = 3, client_factory: Callable = _default_client) -> list[dict]:
    if not basis.strip():
        raise AIWriterError("Wpisz podstawę opisu: wszystko, co ma się znaleźć w tekście.")
    if not compendium.strip():
        raise AIWriterError("Brak kompendium stylu tej marki w appce (desktop/style).")
    if not api_key:
        raise AIWriterError("Brak klucza API. Dopisz ANTHROPIC_API_KEY=... do desktop/.env i uruchom appkę ponownie.")
    system = TASK.format(name=profile.get("name", ""), handle=profile.get("handle", ""), count=count,
                         min=profile.get("caption_min", 500), max=profile.get("caption_max", 1200), compendium=compendium)
    kind = "karuzela" if post_type == "carousel" else "rolka"
    user = f"Materiał: {post_name} ({kind}){f', lokalizacja: {location}' if location else ''}.\n\nPODSTAWA OPISU:\n{basis.strip()}"

    client = client_factory(api_key)
    try:
        import anthropic
        errors = (anthropic.APIError,)
    except ImportError:
        errors = ()
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        )
    except errors as exc:
        raise AIWriterError(_explain(exc)) from exc

    if response.stop_reason == "refusal":
        raise AIWriterError("Model odmówił ułożenia tego opisu. Zmień sformułowanie podstawy i spróbuj ponownie.")
    if response.stop_reason == "max_tokens":
        raise AIWriterError("Odpowiedź została ucięta (limit długości). Spróbuj ponownie albo skróć podstawę.")
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        variants = json.loads(text)["warianty"]
    except (ValueError, KeyError, TypeError) as exc:
        raise AIWriterError("Model zwrócił odpowiedź w nieoczekiwanym formacie. Spróbuj ponownie.") from exc
    return [{"description": v["opis"].strip(), "hook_mechanism": v.get("mechanizm_haka", ""),
             "missing": v.get("brakujace_konkrety", "").strip()} for v in variants if v.get("opis", "").strip()]


def _explain(exc: Exception) -> str:
    import anthropic
    if isinstance(exc, anthropic.AuthenticationError):
        return "Klucz API został odrzucony. Sprawdź ANTHROPIC_API_KEY w desktop/.env."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "Klucz API nie ma dostępu do tego modelu albo konto nie ma aktywnych płatności."
    if isinstance(exc, anthropic.RateLimitError):
        return "Za dużo zapytań naraz. Odczekaj minutę i spróbuj ponownie."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Brak połączenia z API Claude. Sprawdź internet."
    if isinstance(exc, anthropic.BadRequestError):
        return f"API odrzuciło zapytanie: {getattr(exc, 'message', exc)}"
    if isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500:
        return "Serwery Claude mają chwilowy problem. Spróbuj za chwilę."
    return f"Błąd API Claude: {exc}"
