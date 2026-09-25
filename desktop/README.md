# BYKU.PUBLIKACJE DESKTOP

Lokalny panel (Python 3.11+, bez zależności do działania) na `http://127.0.0.1:8902`.
Pracuje na istniejącej kolejce `studio-kolejka` przez rdzeń BYQ Studio (`source_root`) — bez przepisywania uploaderów.

## Uruchomienie

1. Skrót **BYKU.PUBLIKACJE DESKTOP** na pulpicie (tworzy go `tools\install_shortcut.ps1`) albo `start.cmd`.
2. Panel otwiera się w przeglądarce. Druga próba uruchomienia otwiera już działający panel.

## Panele

| Panel | Co robi |
|---|---|
| Stół publikacji | metryki, priorytet TikTok → IG, filtry, status każdej platformy, następny krok |
| Do dokończenia | braki plików, brak opisu, treść bez akceptacji |
| TikTok → Instagram | kandydaci (opublikowane TikToki pierwsze), paczki, Drive, wysyłka na telefon, zgłoszenia z telefonu |
| Kalendarz | dzień / tydzień / miesiąc / lista, przeciąganie z wyborem godziny, 3 warianty rozkładu, cofanie |
| Kanały | tablica statusów osobno dla TikTok, Instagram, Facebook |
| Biblioteka | siatka rolek i karuzel |
| Marki i styl | ton, haki, CTA, hashtagi stałe/rotacyjne, zakazane słowa, lokalizacje, limity, sloty, wzorce stylu, pełny Generator |
| Uczenie | lekcje stylu/procesu/kodu: test → aktywacja → cofnięcie; dziennik zdarzeń |
| Archiwum, System | zakończone; tryb, blokady, rdzeń, Drive, serwer, zadania, blokady profili |

Szczegóły publikacji (panel boczny): podgląd wideo/karuzeli, edytor opisu z licznikiem i kontrolą marki,
hashtagi (dodaj, usuń, usuń wszystkie, podpowiedz), lokalizacja, zmiana miniatury, 3 szkice opisu,
kanały z ręcznym haczykiem (oddzielnie od dowodu platformy), paczka telefonu, historia.

Przycisk, którego nie można użyć w bieżącej konfiguracji, jest wyłączony **i pokazuje powód**.

## Konfiguracja (`config.json`)

| Klucz | Znaczenie |
|---|---|
| `mode` | `production` (prawdziwa kolejka) albo `sandbox` (`sandbox_queue`) |
| `core` | `auto` / `studio` / `fallback`. Produkcja zawsze wymaga rdzenia Studio |
| `allow_production_writes` | `false` = bezpieczny podgląd (zapis zablokowany) |
| `allow_publication` | `false` = przygotowanie publikacji i sygnał muzyki zablokowane |
| `google_drive.local_sync_dir` | folder Dysku Google synchronizowany na komputerze, np. `G:\\Mój dysk\\BYKU-PUBLIKACJE` |
| `mobile_server.url` | adres serwera telefonu, np. `https://twojadomena.pl/mobile` |

Sekrety tylko w `desktop/.env` (ignorowany przez git) — wzór: `.env.example`.

### Serwer telefonu

1. Wdroż mobile (`mobile/DEPLOY.md`) — skrypt wypisze token desktopu.
2. `desktop/.env`: `BYKU_MOBILE_UPLOAD_TOKEN=<token>`; `config.json`: `mobile_server.url`.
3. Panel System pokaże „Token w .env: Jest”, a przyciski „Wyślij na telefon” się odblokują.

## Testy

```
python -m unittest discover -s tests -t .     # 31 testów: kontrakt, bezpieczeństwo, treść, kalendarz, paczki, Drive, serwer, API
python tools/ui_smoke.py --shots out/          # Chromium: 10 paneli, 0 błędów konsoli, 0 martwych przycisków, przepływy
python tools/make_sandbox.py                   # kolejka testowa w data/sandbox-queue
```

Testy działają bez BYQ Studio (rdzeń zastępczy tylko w sandboxie).

## Struktura

```
backend/   config, core (Studio/zastępczy), studio_adapter, publication_view, content_service,
           schedule_service, brand_service, mobile_packages (paczki, Drive, serwer), job_service,
           legacy_bridge (Generator, uploadery, weryfikacja), contract
learning/  SQLite: zdarzenia i lekcje
frontend/  index.html, styles.css, js/ (core, drawer, main, views/*)
defaults/  domyślne profile marek (nadpisania lokalnie w data/brands.json)
tools/     make_sandbox, ui_smoke, install_shortcut.ps1, generate_audit
```
