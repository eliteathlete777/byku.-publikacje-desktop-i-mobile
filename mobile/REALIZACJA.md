# Realizacja BYKU.PUBLIKACJE MOBILE

## Zakres

- [x] Oddzielny kod PWA, bez kopiowania pełnego desktopu.
- [x] Lista paczek filtrowana marką ATLET/RIGGER.
- [x] Film lub komplet slajdów, pobieranie ze sprawdzeniem SHA-256.
- [x] Osobne kopiowanie opisu i hashtagów.
- [x] Ręczne przejście do Instagrama; muzyka i końcowy klik poza aplikacją.
- [x] `post_id + brand`, ochrona przed duplikatem i starszą rewizją.
- [x] Zdarzenia z `event_id`; ręczny haczyk wyłącznie jako jawna akcja.
- [x] Stale widoczne „Odśwież i sprawdź zgodność”.
- [x] Stany: aktualna, nowsza, niekompletna, niezgodna, offline z ostatnim odczytem.

## Decyzje

`content_revision` jest hashem i nie daje się porządkować. Kierunek zmiany rewizji jest ustalany przez `exported_at`; starsza data nigdy nie nadpisuje lokalnej paczki. Google Drive jest transportem przez wersjonowany indeks i manifesty, a nie źródłem statusów publikacji.

## Testy

Testy jednostkowe obejmują kontrakt odbiorowy, brak źródła, złą markę/schemat, nową i starszą rewizję, idempotentne odświeżenie, idempotentne zdarzenia i offline. Test przeglądarkowy jest wykonywany na mobilnym viewportcie po zbudowaniu wydania.
