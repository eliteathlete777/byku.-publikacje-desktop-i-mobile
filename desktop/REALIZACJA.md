# BYKU.PUBLIKACJE DESKTOP — zadania

Aktualizacja: 25.09.2026. Status `verified` = potwierdzone testem automatycznym w tym repozytorium.
Tryb domyślny: bezpieczny podgląd produkcji (`allow_production_writes=false`, `allow_publication=false`).

| Zadanie | Status | Dowód |
|---|---|---|
| T01 Mapa funkcji | verified | `docs/MACIERZ_FUNKCJI.md`, `docs/MANIFEST_SKRYPTOW.json` |
| T02 Konfiguracja, start, skrót | verified* | `start.cmd`, `tools/install_shortcut.ps1`; *skrót do potwierdzenia na Windows (D1) |
| T03 Adapter, rdzeń Studio/zastępczy | verified | `CoreSafetyTests`, testy działają bez dysku C: |
| T04 Stół publikacji i szczegóły | verified | `tools/ui_smoke.py` |
| T05 Treść: opis, hashtagi, lokalizacja, miniatura, szkice | verified | `ContentTests`, `BrandTests`, UI smoke |
| T06 Dispatch uploaderów | odłożone świadomie | wymaga decyzji właściciela i testu na kontach |
| T07 Dowody i ręczne haczyki | verified | test „haczyk ≠ dowód” (naprawiony błąd) |
| T08 Kalendarz | verified | `ScheduleTests`, UI smoke (tryby, warianty, cofanie) |
| T09 Paczki telefonu v2 | verified | `MobileTests`, e2e |
| T10 Przełączenie właściciela magazynu | odłożone świadomie | decyzja właściciela |
| T11 Manifest skryptów | verified | — |
| T12 Dziennik zdarzeń | verified | `LearningTests` |
| T13 Uczenie stylu (akceptacja → lekcja) | verified | `test_approved_change_becomes_style_lesson` |
| T14 Lekcje procesu z testem | verified | `test_lesson_requires_passed_test_and_can_be_reverted` |
| T15 Propozycje kodu | częściowo, świadomie | zapis i status; wykonanie poza aplikacją |
| T16 Zakładka Uczenie | verified | UI smoke |
| T17 Marki i styl | verified | `BrandTests`, UI smoke |
| T18 Transfer Google Drive | verified | `test_drive_transfer_copies_verified_package` |
| T19 Wysyłka na serwer telefonu + import zgłoszeń | verified | `test_server_transfer_and_event_pull`, e2e |
| T20 Kanały, Biblioteka, System | verified | UI smoke |
| T21 Ochrona lokalnego API (Origin/Host, limit body) | verified | `test_foreign_origin_blocked` |

## Otwarte (kolejność)

- **D1** — Na komputerze właściciela: `tools\install_shortcut.ps1`, start ze skrótu, otwarcie prawdziwej kolejki w trybie podglądu, sprawdzenie panelu System (rdzeń: `studio`).
- **D2** — Ustawić `google_drive.local_sync_dir` na folder Dysku Google synchronizowany lokalnie.
- **D3** — Po wdrożeniu mobile: `mobile_server.url` + token w `.env`.
- **D4** — Decyzja właściciela: T10 (`allow_production_writes=true`), potem T06.
