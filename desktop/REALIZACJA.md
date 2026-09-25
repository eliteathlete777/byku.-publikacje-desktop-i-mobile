# BYKU.PUBLIKACJE DESKTOP — realizacja

Aktualizacja: 2026-09-24. Tryb domyślny: bezpieczny odczyt danych produkcyjnych, zapis wyłącznie do izolowanej kolejki testowej. Publikowanie jest wyłączone do jawnego przełączenia właściciela magazynu.

| Zadanie | Status | Pliki | Dowód sprawdzenia | Pozostały problem |
|---|---|---|---|---|
| T01 Mapa funkcji | verified | `docs/MACIERZ_FUNKCJI.md`, `docs/MANIFEST_SKRYPTOW.json` | 110 skryptów sklasyfikowanych statycznie; akcje GUI zmapowane | — |
| T02 Kopia i konfiguracja | verified | `config.json`, `run.py`, `start.cmd` | osobny katalog, jedna instancja, skrót na pulpicie | zapis produkcyjny celowo wyłączony |
| T03 Adapter i stan | verified | `backend/studio_adapter.py`, `backend/publication_view.py` | 46 realnych paczek, 0 błędów; 5 testów rdzenia OK | — |
| T04 Stół i szczegóły | verified | `frontend/` | Playwright 1440/1280/1024; 20 kart ATLET, 21 miniaturek, 0 błędów konsoli | — |
| T05 Kreator treści | verified | `backend/content_service.py`, `frontend/app.js` | zapis/restart/konflikt 409 i wyczyszczenie hashtagów na izolowanej paczce | zapis produkcyjny celowo wyłączony |
| T06 Nadzór publikacji | working | `backend/job_service.py` | blokada zasobu profil/konto, trwały stan zadania | dispatch uploaderów wyłączony do testu konta |
| T07 Dowody i haczyki | verified | `backend/studio_adapter.py`, `frontend/app.js` | haczyk Instagram nie zmienia Facebooka; LIVE nie stawia haczyka | odczyt kont platform nieuruchamiany w teście |
| T08 Kalendarz i sloty | verified | `backend/schedule_service.py`, `frontend/app.js` | ekran kalendarza, 3 warianty, drag/drop, zapis i poprawny rollback bez tworzenia historii odwrotnej | zapis produkcyjny nadal celowo zablokowany |
| T09 Paczki telefonu | verified | `backend/mobile_packages.py`, `docs/WSPOLNY_KONTRAKT_MOBILE_DESKTOP.md` | manifest z sumami, gotowy opis/hashtagi, idempotentny import zdarzeń bez zmiany paczki | transport Drive pozostaje w osobnym kodzie Mobile |
| T10 Wydanie i odbiór | working | `docs/RAPORT_ODBIORU.md`, skrót | panel działa na `127.0.0.1:8899` | integracje z kontami niezweryfikowane |
| T11 Manifest skryptów | verified | `docs/MANIFEST_SKRYPTOW.json` | analiza AST 110 plików bez importowania | — |
| T12 Dziennik zdarzeń | verified | `learning/events.py`, `learning/store.py` | SQLite, migracja, deduplikacja testem | — |
| T13 Uczenie stylu | verified | `learning/style_lessons.py`, `learning/lesson_service.py` | jawne reguły, marki i wersje oddzielne; aktywacja/cofanie | — |
| T14 Lekcje procesu | verified | `learning/lesson_service.py` | wersja, dowód, test, aktywacja i cofnięcie | — |
| T15 Propozycje kodu | working | `learning/lesson_service.py` | typ `code`, stan draft/active/reverted | wykonanie kodu pozostaje celowo poza procesem aplikacji |
| T16 Zakładka Uczenie | verified | `frontend/app.js` | zdarzenia, lekcje, aktywacja i cofanie | — |

Następne zadanie: T06/T10 — kontrolowany test kont i przełączenie właściciela magazynu. Wymaga jawnej decyzji właściciela; aplikacja pozostaje w bezpiecznym odczycie produkcji.

Start roboczy: `start.cmd`. Serwer nasłuchuje wyłącznie na `127.0.0.1:8902`.
