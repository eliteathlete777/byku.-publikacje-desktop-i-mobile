"""Układanie opisu z „podstawy opisu” przez Claude albo ChatGPT, według kompendium stylu marki.

Kompendium idzie w całości jako instrukcja systemowa (stała, cache'owana), podstawa jako wiadomość.
Model zwraca 3 warianty w ustalonym JSON-ie; kontrolę zgodności robi potem BrandService.lint.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

MODEL = "claude-sonnet-5"  # nadpisywany przez CLAUDE_MODEL w desktop/.env
FALLBACK_BETA = "server-side-fallback-2026-07-01"
OPENAI_MODEL = "gpt-5"  # nadpisywany przez OPENAI_MODEL w desktop/.env
PROVIDERS = {
    "claude": {"module": "anthropic", "env": "ANTHROPIC_API_KEY", "label": "Claude"},
    "openai": {"module": "openai", "env": "OPENAI_API_KEY", "label": "ChatGPT"},
}

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


def pick_provider(setting: str, anthropic_key: str, openai_key: str) -> str:
    """AI_PROVIDER z .env wygrywa; bez niego bierzemy to API, do którego jest klucz (przy obu: Claude)."""
    if setting in PROVIDERS:
        return setting
    return "openai" if openai_key and not anthropic_key else "claude"


def model_for(provider: str, openai_model: str = "", claude_model: str = "") -> str:
    return (openai_model or OPENAI_MODEL) if provider == "openai" else (claude_model or MODEL)


def sdk_available(provider: str = "claude") -> bool:
    try:
        __import__(PROVIDERS[provider]["module"])
        return True
    except ImportError:
        return False


def _default_client(api_key: str, provider: str = "claude"):
    module = PROVIDERS[provider]["module"]
    try:
        sdk = __import__(module)
    except ImportError as exc:
        raise AIWriterError(f"Brak biblioteki {module}. Zainstaluj: python -m pip install {module}") from exc
    if provider == "openai":
        return sdk.OpenAI(api_key=api_key, timeout=180.0)
    return sdk.Anthropic(api_key=api_key, timeout=180.0)


def compose(profile: dict, compendium: str, basis: str, *, post_name: str, post_type: str, location: str,
            api_key: str, provider: str = "claude", model: str = "", count: int = 3,
            client_factory: Callable = _default_client) -> list[dict]:
    meta = PROVIDERS[provider]
    if not basis.strip():
        raise AIWriterError("Wpisz podstawę opisu: wszystko, co ma się znaleźć w tekście.")
    if not compendium.strip():
        raise AIWriterError("Brak kompendium stylu tej marki w appce (desktop/style).")
    if not api_key:
        raise AIWriterError(f"Brak klucza API. Dopisz {meta['env']}=... do desktop/.env i uruchom appkę ponownie.")
    system = TASK.format(name=profile.get("name", ""), handle=profile.get("handle", ""), count=count,
                         min=profile.get("caption_min", 500), max=profile.get("caption_max", 1200), compendium=compendium)
    kind = "karuzela" if post_type == "carousel" else "rolka"
    user = f"Materiał: {post_name} ({kind}){f', lokalizacja: {location}' if location else ''}.\n\nPODSTAWA OPISU:\n{basis.strip()}"

    client = client_factory(api_key, provider)
    try:
        errors = (__import__(meta["module"]).APIError,)
    except ImportError:
        errors = ()
    try:
        if provider == "openai":
            text = _ask_openai(client, model or OPENAI_MODEL, system, user, profile)
        else:
            text = _ask_claude(client, model or MODEL, system, user)
    except errors as exc:
        raise AIWriterError(_explain(exc, provider)) from exc
    try:
        variants = json.loads(text)["warianty"]
    except (ValueError, KeyError, TypeError) as exc:
        raise AIWriterError("Model zwrócił odpowiedź w nieoczekiwanym formacie. Spróbuj ponownie.") from exc
    return [{"description": v["opis"].strip(), "hook_mechanism": v.get("mechanizm_haka", ""),
             "missing": v.get("brakujace_konkrety", "").strip()} for v in variants if v.get("opis", "").strip()]


REFUSED = "Model odmówił ułożenia tego opisu. Zmień sformułowanie podstawy i spróbuj ponownie."
TRUNCATED = "Odpowiedź została ucięta (limit długości). Spróbuj ponownie albo skróć podstawę."


def _ask_claude(client, model: str, system: str, user: str) -> str:
    response = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
    )
    if response.stop_reason == "refusal":
        raise AIWriterError(REFUSED)
    if response.stop_reason == "max_tokens":
        raise AIWriterError(TRUNCATED)
    return next((b.text for b in response.content if b.type == "text"), "")


def _ask_openai(client, model: str, system: str, user: str, profile: dict) -> str:
    extra = {"reasoning": {"effort": "high"}} if model.startswith(("gpt-5", "o")) else {}
    response = client.responses.create(
        model=model,
        instructions=system,
        input=user,
        max_output_tokens=16000,
        prompt_cache_key=f"byku-{profile.get('handle', '')}",
        text={"format": {"type": "json_schema", "name": "warianty_opisu", "schema": SCHEMA, "strict": True}},
        **extra,
    )
    if getattr(response, "status", "") == "incomplete":
        raise AIWriterError(TRUNCATED)
    parts = [c for item in response.output if getattr(item, "type", "") == "message" for c in item.content]
    if any(getattr(c, "type", "") == "refusal" for c in parts):
        raise AIWriterError(REFUSED)
    return "".join(c.text for c in parts if getattr(c, "type", "") == "output_text")


def _explain(exc: Exception, provider: str = "claude") -> str:
    meta = PROVIDERS[provider]
    sdk = __import__(meta["module"])
    if isinstance(exc, sdk.AuthenticationError):
        return f"Klucz API został odrzucony. Sprawdź {meta['env']} w desktop/.env."
    if isinstance(exc, sdk.PermissionDeniedError):
        return "Klucz API nie ma dostępu do tego modelu albo konto nie ma aktywnych płatności."
    if isinstance(exc, sdk.RateLimitError):
        return "Za dużo zapytań naraz albo wyczerpany limit/środki na koncie API. Odczekaj minutę i sprawdź płatności."
    if isinstance(exc, sdk.APIConnectionError):
        return f"Brak połączenia z API {meta['label']}. Sprawdź internet."
    if isinstance(exc, sdk.BadRequestError):
        return f"API odrzuciło zapytanie: {getattr(exc, 'message', exc)}"
    if isinstance(exc, sdk.APIStatusError) and exc.status_code >= 500:
        return f"Serwery {meta['label']} mają chwilowy problem. Spróbuj za chwilę."
    return f"Błąd API {meta['label']}: {exc}"
