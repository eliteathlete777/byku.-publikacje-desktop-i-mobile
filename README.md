# BYKU.PUBLIKACJE — Desktop i Mobile

Jeden system, dwie aplikacje, jeden wersjonowany kontrakt danych.

```
desktop/     BYKU.PUBLIKACJE DESKTOP — kolejka, treść, marki, kalendarz, kanały, paczki na telefon (Python, lokalnie)
mobile/      BYKU.PUBLIKACJE MOBILE — PWA na telefon + serwer PHP (Hostinger) z obowiązkowym logowaniem
contract/    wspólny kontrakt v2 + przypadki testowe używane przez obie strony
e2e/         test całego łańcucha TikTok → paczka → serwer → telefon → zgłoszenie
docs/        audyt, plan dalszy
```

## Przepływ

```
studio-kolejka ──► DESKTOP ──► paczka (manifest v2, SHA-256) ──► Google Drive (folder synchronizowany)
                     ▲                                      └──► serwer telefonu (HTTPS, token) ──► MOBILE (logowanie)
                     └──────────── zgłoszenia z telefonu (osobno od dowodów i haczyków) ◄───────────────┘
```

## Szybki start

| Co | Polecenie |
|---|---|
| Desktop (Windows) | skrót **BYKU.PUBLIKACJE DESKTOP** na pulpicie albo `desktop\start.cmd` |
| Utworzenie skrótu | `powershell -ExecutionPolicy Bypass -File desktop\tools\install_shortcut.ps1` |
| Wszystkie testy | `cd desktop && python -m unittest discover -s tests -t .` · `cd mobile && npm test` · `python e2e/test_transfer.py` |
| Wdrożenie mobile | `mobile/DEPLOY.md` |

## Bezpieczeństwo

- W repozytorium nie ma tokenów, haseł, baz SQLite, PID-ów ani materiałów. Sekrety: `desktop/.env` (lokalnie) i katalog prywatny na serwerze (poza `public_html`).
- Desktop: `allow_publication=false`, `allow_production_writes=false` domyślnie. Końcowe kliknięcie publikacji zawsze ręczne.
- Mobile: każde żądanie danych wymaga sesji po stronie serwera; offline tylko przy ważnej sesji; wylogowanie czyści dane z telefonu.
- CI (`.github/workflows/testy.yml`) uruchamia wszystkie testy i skan plików zakazanych przy każdym pushu.

## Dokumentacja

- Audyt i znalezione błędy: `docs/AUDYT.md`
- Kontrakt: `contract/KONTRAKT.md`
- Desktop: `desktop/README.md`, zadania: `desktop/REALIZACJA.md`
- Mobile: `mobile/README.md`, zadania: `mobile/REALIZACJA.md`, wdrożenie: `mobile/DEPLOY.md`
- Plan dalszy: `docs/PLAN_DALSZY.md`
