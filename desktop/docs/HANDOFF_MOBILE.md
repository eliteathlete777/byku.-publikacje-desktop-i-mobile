# Handoff — BYKU.PUBLIKACJE MOBILE

Cel: osobna aplikacja telefoniczna do obsługi paczek „TikTok gotowy, Instagram czeka”. Nie jest mobilną kopią całego desktopu.

## Zakres pierwszego wydania

1. Lista paczek z Google Drive filtrowana marką.
2. Duża miniaturka i podgląd wideo/karuzeli.
3. Pobranie źródłowego filmu albo wszystkich slajdów.
4. Kopiowanie opisu i hashtagów osobnymi przyciskami.
5. Otwieranie Instagrama; końcowy klik oraz muzyka pozostają ręczne.
6. Pokazanie nowszej wersji po zmianie `content_revision`.
7. Zdarzenia użytkownika z `event_id`; import idempotentny.
8. Ręczny haczyk jako osobna operacja kanału, nigdy pole importowanego ZIP-a.

## Kod początkowy

Referencja UI: `generator-opisow-dropa/mobile`. Kontrakt i dane eksportu: `BYKU-PUBLIKACJE-DESKTOP/backend/mobile_packages.py` oraz `docs/WSPOLNY_KONTRAKT_MOBILE_DESKTOP.md`.

## Pierwszy test odbioru

Paczka ATLET z TikTok `scheduled`, Instagram `unknown`: telefon pokazuje film, opis i hashtagi tej samej rewizji. Ponowny import nie tworzy duplikatu. Starsza rewizja nie nadpisuje nowszej.

