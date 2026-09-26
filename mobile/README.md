# BYKU.PUBLIKACJE MOBILE

Osobne, instalowalne PWA do paczek „TikTok gotowy — Instagram czeka”. Nie zawiera generatora ani pełnego panelu desktopowego.

## Źródło paczek

Domyślnie `paczki/index.json` względem adresu appki — na Hostingerze to `https://<domena>/publikacje/paczki/index.json`, gdzie desktop wysyła paczki (zob. `DEPLOY_HOSTINGER.md`). Można podać dowolny inny URL z CORS. Minimalny indeks:

```json
{"packages":[{"brand":"atlet","manifest_url":"atlet/do-instagrama/post-1/manifest.json"}]}
```

Adresy względne są rozwiązywane względem indeksu. Folder z manifestem zawiera pliki wymienione w `files`. Serwer musi zezwalać na CORS. Manifest jest zgodny z `WSPOLNY_KONTRAKT_MOBILE_DESKTOP.md`.

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
