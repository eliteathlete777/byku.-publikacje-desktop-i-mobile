# BYKU.PUBLIKACJE MOBILE — zadania

Aktualizacja: 25.09.2026. `verified` = potwierdzone testem automatycznym.

| Zadanie | Status | Dowód |
|---|---|---|
| M01 Obowiązkowe logowanie (serwer) | verified | `server.test.js`: brak sesji → 401 dla indeksu i plików |
| M02 Poprawna sesja daje dostęp | verified | `server.test.js`, e2e |
| M03 Wygasła sesja → ponowne logowanie | verified | serwer (zegar +8 dni) i klient (`session.test.js`) |
| M04 Wylogowanie blokuje dane | verified | serwer + klient + e2e (localStorage i pliki usunięte) |
| M05 Offline nie ujawnia danych niezalogowanemu | verified | `session.test.js`, e2e offline po wylogowaniu |
| M06 Błędna suma SHA-256 blokuje plik | verified | `domain.test.js`, serwer (upload 422), e2e (podmieniony plik) |
| M07 Starsza wersja nie zastępuje nowszej | verified | klient + serwer (409) |
| M08 Ponowne odświeżenie bez duplikatów | verified | klient + serwer + e2e |
| M09 Stany: aktualna / nowsza / niekompletna / niezgodna / offline | verified | `domain.test.js`, e2e |
| M10 Kopiowanie opisu i hashtagów | verified | e2e (schowek = treść z desktopu) |
| M11 Wideo, karuzela, miniatura | verified | e2e (podgląd, 3 slajdy, pobranie miniatury) |
| M12 Zgłoszenie publikacji → desktop | verified | e2e (bez zmiany haczyka) |
| M13 PWA: manifest, ikony PNG, service worker | verified | e2e |
| M14 Wspólny kontrakt v2 | verified | `contract.test.js` + PHP + Python na tych samych przypadkach |
| M15 Wdrożenie Hostinger | **zablokowane — dane SSH** | skrypt `tools/deploy_hostinger.sh` gotowy z kontrolą po wdrożeniu |
| M16 Test na fizycznym telefonie (instalacja, udostępnianie do Instagrama) | po M15 | — |

## Otwarte

- **M15** — potrzebne: dane SSH Hostingera + domena/ścieżka (patrz `DEPLOY.md`).
- **M16** — po wdrożeniu: instalacja na iPhone/Android, udostępnienie filmu bezpośrednio do Instagrama.
