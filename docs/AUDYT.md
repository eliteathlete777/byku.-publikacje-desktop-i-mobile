# Audyt stanu — 25.09.2026

Punkt wyjścia: commit `446a630` (import z lokalnego `github-repo`). Każdą funkcję sprawdzono w kodzie i testach,
nie na podstawie opisu w REALIZACJA/RAPORT.

## Stan zastany

| Obszar | Deklaracja w dokumentach | Faktyczny stan w kodzie |
|---|---|---|
| Testy desktop | „7/7 OK” | Nie uruchamiały się poza komputerem właściciela: zależne od `C:\...\byku-publisher-desktop` (stary rdzeń poza repo) i Pillow |
| Rdzeń magazynu | — | Cały odczyt/zapis przez `studio.rdzen` spoza repozytorium; brak rdzenia = wyjątek przy każdym wywołaniu |
| Kalendarz | „dzień/tydzień/miesiąc/lista” | **Martwe przyciski**: Dzień, Miesiąc, Lista nic nie robiły; upuszczenie ignorowało „Bez terminu” przez literówkę (`'Bez termin'`); godzina zawsze 18:45 |
| Biblioteka, Publikacje, Do dokończenia | osobne widoki | Ten sam widok tabeli z inną nazwą |
| Hashtagi | edycja i usuwanie | Jedno pole tekstowe; brak podpowiedzi, kontroli limitu 30, deduplikacji |
| Marki i styl | — | Brak panelu; `remember_style` nigdy nie wywoływane — uczenie stylu nie działało |
| Uczenie | aktywacja po teście | Aktywacja przechodziła z pustym testem `{}`; dodawanie lekcji przez `prompt()` |
| Paczka telefonu | manifest z sumami | ZIP tworzony tylko raz (stara zawartość przy nowej wersji), katalog paczki nie czyszczony, brak ról plików, brak informacji „TikTok opublikowany / Instagram czeka” |
| Google Drive | integracja | Tylko ID folderów w configu; brak jakiegokolwiek transferu |
| Mobile — logowanie | — | **Brak**. Dane z publicznego `index.json`, bez serwera i autoryzacji |
| Mobile — offline | ostatni odczyt | Dane w `localStorage` bez żadnej ochrony; service worker cache'ował wszystkie odpowiedzi |
| Mobile — ikony PWA | instalowalna | Tylko SVG — Android/iOS wymagają PNG 192/512 |
| Hosting | — | Nic nie wdrożone |

## Błędy znalezione i naprawione

1. **Ręczny haczyk tworzył fałszywy dowód platformy** — `set_manual_check` ustawia `stan=potwierdzony`, a widok zamieniał to na `platform_evidence=scheduled`. Wykryte nowym testem; naprawione w `publication_view.channel_view`.
2. Edycja opisu po akceptacji zostawiała status „zaakceptowany” (liczyła się dowolna akceptacja w historii).
3. `ScheduleService.undo` usuwał wpis historii przed próbą cofnięcia — błąd zapisu gubił historię.
4. `/api/open-folder` działał tylko na Windows (`os.startfile`) — teraz także macOS/Linux.
5. Serwer desktop przyjmował żądania z dowolnej strony (brak kontroli `Origin`/`Host`) — dowolna strona WWW mogła wywołać zapis na `127.0.0.1`. Dodano blokadę.
6. Brak limitu rozmiaru body w serwerze desktop.
7. Test „LIVE ≠ haczyk” sprawdzał tylko widok, nie zapis — dodano test zapisu.

## Niebezpieczne operacje — zachowane blokady

- `allow_publication=false`, `allow_production_writes=false` — domyślnie, bez przełącznika w UI.
- Końcowe kliknięcie publikacji — zawsze ręczne (desktop i telefon).
- Import zdarzeń telefonu nigdy nie zmienia haczyka, dowodu, terminu ani archiwum (test).
- Tryb `production` nigdy nie użyje rdzenia zastępczego (test).

## Świadomie odłożone (z uzasadnieniem)

| Pozycja | Powód |
|---|---|
| T06 — automatyczny dispatch uploaderów | Wymaga jawnej decyzji właściciela i testu na kontach; adapter gotowy, blokada `allow_publication` |
| T10 — przełączenie właściciela magazynu | Decyzja właściciela; wymaga `allow_production_writes=true` |
| T15 — wykonywanie propozycji kodu | Celowo poza procesem aplikacji (bezpieczeństwo) |
| Publikacja przez Instagram Graph API | Nowy zakres; opisany w `docs/PLAN_DALSZY.md` |
