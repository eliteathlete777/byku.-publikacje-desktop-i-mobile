# Wspólny kontrakt BYKU.PUBLIKACJE — wersja 2

Desktop i Mobile to osobne aplikacje z osobnym kodem. Łączy je tylko ten kontrakt:
format paczki telefonu, format indeksu i API serwera mobilnego.

- Wersja schematu: **2** (`schema_version: 2`). Wersja 1 jest wycofana: mobile ją odrzuca jako „niezgodna”.
- Walidatory (muszą dawać ten sam wynik dla `fixtures/cases.json`):
  - Desktop (Python): `desktop/backend/contract.py`
  - Mobile klient (JS): `mobile/src/contract.js`
  - Mobile serwer (PHP): `mobile/api/lib/contract.php`
- Zmiana kontraktu = zmiana tego pliku + `fixtures/` + wszystkich trzech walidatorów + testy po obu stronach.
  Testy obu stron czytają te same pliki z `contract/fixtures/`.

## Tożsamość i wersja

| Pole | Znaczenie |
|---|---|
| `package_id` | `<brand>--<post_id>`; klucz paczki na telefonie i serwerze |
| `post_id` | identyfikator paczki w `studio-kolejka` |
| `brand` | `atlet` albo `rigger` |
| `content_revision` | SHA-256 (64 znaki hex) z `post.json`, `opis.txt`, `miniaturka.png` |
| `exported_at` | czas eksportu, ISO 8601 UTC (`2026-09-25T10:00:00Z`) |

Kolejność wersji ustala **wyłącznie** `exported_at`. `content_revision` jest hashem i nie da się go porządkować.
Starszy `exported_at` nigdy nie zastępuje nowszego — ani na serwerze, ani na telefonie.
Ta sama rewizja pobrana ponownie nie tworzy duplikatu.

## Manifest paczki (`manifest.json`)

```json
{
  "schema_version": 2,
  "package_id": "atlet--post-1",
  "post_id": "post-1",
  "brand": "atlet",
  "title": "Pompki na poręczach",
  "type": "reel",
  "content_revision": "<64 hex>",
  "exported_at": "2026-09-25T10:00:00Z",
  "channel": "instagram",
  "caption": "Opis gotowy do skopiowania",
  "hashtags": "#byku #trening",
  "location": "Katowice",
  "platforms": {
    "tiktok":    {"evidence": "published", "manual_checked": true},
    "instagram": {"evidence": "unknown",   "manual_checked": false},
    "facebook":  {"evidence": "unknown",   "manual_checked": false}
  },
  "transfer": {"from": "tiktok", "to": "instagram", "tiktok": "published", "instagram": "pending"},
  "files": [
    {"name": "film.mp4", "role": "video", "sha256": "<64 hex>", "size": 123},
    {"name": "miniaturka.png", "role": "thumbnail", "sha256": "<64 hex>", "size": 45},
    {"name": "opis-do-skopiowania.txt", "role": "caption", "sha256": "<64 hex>", "size": 10},
    {"name": "hashtagi.txt", "role": "hashtags", "sha256": "<64 hex>", "size": 10}
  ]
}
```

Reguły:

- `type`: `reel` wymaga co najmniej jednego pliku `role: video`; `carousel` wymaga co najmniej 2 plików `role: slide`, każdy z liczbowym `order` (bez powtórzeń).
- Obowiązkowe role: `thumbnail`, `caption`, `hashtags` (plik hashtagów może być pusty — usunięte hashtagi są dozwolone).
- `name`: sama nazwa pliku; bez `/`, `\`, `..`, bez kropki na początku; bez powtórzeń; `manifest.json` nie występuje na liście.
- `sha256`: 64 znaki hex; `size`: liczba całkowita ≥ 0.
- `channel`: zawsze `instagram` (paczki transferu TikTok → Instagram).
- `platforms.*.evidence`: `unknown | scheduled | published | failed` — dowód wykryty automatycznie.
- `platforms.*.manual_checked`: ręczny haczyk użytkownika. **Nigdy** nie jest wyliczany z dowodu.
- `transfer.tiktok`: `published | scheduled | manual_checked`; `transfer.instagram`: zawsze `pending` w chwili eksportu.

## Indeks (`GET /api/index` serwera mobilnego)

```json
{"schema_version": 2, "generated_at": "2026-09-25T10:00:00Z", "packages": [ <manifest>, ... ]}
```

Indeks zawiera wyłącznie aktualne (najnowsze) rewizje. Każdy manifest ma dodatkowo pole `base_url`
nadane przez serwer — z niego mobile pobiera pliki (`<base_url>&name=<plik>`).

## API serwera mobilnego (Hostinger, `mobile/api/`)

Wszystkie odpowiedzi to JSON. Brak ważnej sesji = `401` i **zero danych**.

| Metoda i ścieżka | Kto | Opis |
|---|---|---|
| `POST /api/login` `{login, password}` | telefon | tworzy sesję (cookie `HttpOnly; Secure; SameSite=Strict`) |
| `POST /api/logout` | telefon | niszczy sesję |
| `GET /api/session` | telefon | `{authenticated, user, expires_at}` |
| `GET /api/index` | telefon (sesja) | indeks paczek |
| `GET /api/file?package=<id>&rev=<rev>&name=<plik>` | telefon (sesja) | strumień pliku |
| `POST /api/events` `{events:[...]}` | telefon (sesja) | zapis zdarzeń telefonu, deduplikacja po `event_id` |
| `PUT /api/upload/file?package=&rev=&name=` | desktop (token) | wysyła jeden plik; serwer sprawdza SHA-256 z nagłówka `X-Sha256` |
| `POST /api/upload/commit` `<manifest>` | desktop (token) | publikuje rewizję w indeksie; `409` gdy starsza niż obecna |
| `GET /api/events/export` | desktop (token) | zdarzenia telefonu do importu na desktopie |

Token desktopu: nagłówek `Authorization: Bearer <token>`. Na serwerze przechowywany jest tylko hash tokenu.
Żądania telefonu `POST` wymagają nagłówka `X-Byku-Client: mobile` (ochrona CSRF razem z `SameSite=Strict`).

## Zdarzenia telefonu

`{event_id, type, package_id, post_id, brand, occurred_at}`; `type` ∈
`downloaded | caption_copied | hashtags_copied | instagram_opened | manual_check`.

Zdarzenie `manual_check` to **ręczne zgłoszenie użytkownika** z telefonu. Desktop pokazuje je osobno
i nigdy nie zamienia go automatycznie w dowód platformy ani haczyk w `studio-kolejka`.

## Źródła prawdy

- Produkcyjne paczki: istniejący `studio-kolejka` (desktop).
- Ręczny haczyk: wyłącznie `platformy_stan[channel].haczyk` zapisany świadomą akcją na desktopie.
- Dowód platformy: osobne pole `platform_evidence`; nigdy nie stawia haczyka.
- Google Drive i serwer mobilny: transport plików, nie baza statusów i nie druga kolejka.
- Historia uczenia: SQLite desktopu; reguły stylu są oddzielne dla ATLET i RIGGER.

## Foldery Google Drive

- Root: `1O2DJuWIarEjfObcvDnNgiLgjj6L085CD`
- ATLET: `1Ln2SdkFZWY784sJn73Gv6VTIX7g-tZ6G`
- RIGGER: `1MozqWoI71Cg2R_n9PHEOdlEVpVTIO2si`

Desktop zapisuje paczki do lokalnie zsynchronizowanego folderu Dysku Google (Google Drive dla komputerów),
w układzie `<marka>/do-instagrama/<post_id>/`. Nie są potrzebne żadne tokeny Google w kodzie.
Nie mieszać marek i nie tworzyć drugiego roota bez jawnej migracji.
