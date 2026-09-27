# BYKU.PUBLIKACJE MOBILE

Osobne, instalowalne PWA do paczek „TikTok gotowy — Instagram czeka”. Nie zawiera generatora ani pełnego panelu desktopowego.

## Źródło paczek

Appkę i paczki serwuje sam desktop (serwer telefonu, domyślnie `127.0.0.1:8903`), a telefon łączy się z nim przez Tailscale — zob. `../TELEFON_TAILSCALE.md`. Dlatego domyślny adres to względne `paczki/index.json`, a czynności telefonu lecą automatycznie `POST api/events` do tego samego komputera (plik JSON zostaje jako zapas). Można podać dowolny inny URL indeksu z CORS. Minimalny indeks:

```json
{"packages":[{"brand":"atlet","manifest_url":"atlet/do-instagrama/post-1/manifest.json"}]}
```

Adresy względne są rozwiązywane względem indeksu. Folder z manifestem zawiera pliki wymienione w `files`. Manifest jest zgodny z `WSPOLNY_KONTRAKT_MOBILE_DESKTOP.md`. Rolka dostaje dokładnie jeden film (wersja `*-hd`, jeśli jest), karuzela — wszystkie slajdy.

## Uruchomienie i testy

```powershell
npm test
npx serve .
```

## Zasady bezpieczeństwa stanu

- klucz paczki: `post_id + brand`;
- nowsza rewizja zastępuje starszą tylko według `exported_at`;
- import i odświeżenie nie zmieniają haczyków, terminów ani statusów;
- zdarzenia użytkownika mają `event_id` i są deduplikowane;
- każdy pobierany materiał jest sprawdzany SHA-256.
