# Wspólny kontrakt BYKU.PUBLIKACJE

Desktop i Mobile są osobnymi aplikacjami oraz osobnymi kodami. Łączy je wyłącznie wersjonowany kontrakt paczki i serwera.

## Tożsamość i wersja

Klucz paczki: `post_id + marka`. Wersja treści: SHA-256 zawartości `post.json`, `opis.txt` i `miniaturka.png`. Transport telefonu używa `schema_version`, `content_revision` i sum każdego pliku.

## Źródła prawdy

- Produkcyjne paczki: istniejący `studio-kolejka`.
- Ręczny haczyk: wyłącznie `platformy_stan[channel].haczyk` zapisany świadomą akcją użytkownika.
- Dowód platformy: osobne pole `platform_evidence`; nigdy nie stawia haczyka.
- Hostinger (`/publikacje/paczki/`): transport plików, nie baza stanów i nie druga kolejka produkcyjna. Google Drive pozostaje opcją — telefon przyjmuje dowolny adres `index.json` z CORS.
- Historia uczenia: SQLite desktopu; reguły stylu są oddzielne dla ATLET i RIGGER.

## Paczka telefonu

Obowiązkowe pola manifestu: `schema_version`, `post_id`, `brand`, `content_revision`, `exported_at`, `channel`, `source_state`, `files[{name,sha256}]`.

Pola opcjonalne (desktop wysyła, telefon używa, gdy są): `title` — nazwa materiału na karcie, `target_at` — lokalny termin publikacji `RRRR-MM-DD GG:MM`. Plik `podpis.txt` (opis + pusta linia + hashtagi) jest gotowym podpisem do wklejenia; gdy go brak, telefon skleja podpis z `opis-do-skopiowania.txt` i `hashtagi.txt`. Starsze paczki bez tych pól działają dalej.

`exported_at` ma precyzję milisekund (ISO 8601, UTC, `Z`) — rozstrzyga, która rewizja jest nowsza.

## Indeks paczek

Desktop po każdym eksporcie zapisuje `mobile-packages/index.json`:

```json
{"schema_version":1,"generated_at":"…","packages":[{"post_id":"…","brand":"atlet","content_revision":"…","exported_at":"…","manifest_url":"atlet/do-instagrama/<post_id>-<rewizja16>/manifest.json"}]}
```

Jedna pozycja na `post_id + brand` (najnowsza rewizja). `manifest_url` jest względny do indeksu, pliki paczki są względne do manifestu.

## Zdarzenia telefonu (słownik v1)

| Typ | Znaczenie | Dodatkowe pola |
|---|---|---|
| `downloaded` | pobrano komplet źródeł (SHA-256 zgodne) | `files` |
| `description_copied` | skopiowano opis | — |
| `hashtags_copied` | skopiowano hashtagi | — |
| `instagram_opened` | otwarto Instagram | — |
| `sent` | wysłano | — |
| `manual_hook` | świadomy ręczny haczyk Instagram | `value` |

Aliasy przyjmowane przez desktop (starsze nazwy): `caption_copied` → `description_copied`, `manual_check` → `manual_hook`.

Eksport z telefonu: `{"schema_version":1,"source":"mobile","exported_at":"…","events":[…]}` → desktop, zakładka Uczenie → „Import z telefonu” (`POST /api/mobile-events/import`). Deduplikacja po `event_id`, ponowny import jest bezpieczny. Import transportowy nigdy sam nie zmienia archiwum, dowodu platformy, terminu ani haczyka.

## Przepływ

1. Desktop: „Przygotuj na telefon” → paczka + `index.json` → automatyczna wysyłka FTPS na Hostinger (jeśli włączona).
2. Mobile (`https://<domena>/publikacje/`): „Odśwież i sprawdź zgodność” → `paczki/index.json` → manifesty → pobranie z kontrolą SHA-256.
3. Mobile: „Eksportuj czynności” → plik JSON → Desktop: „Import z telefonu”.

Test end-to-end kontraktu: `desktop/tests/test_mobile_contract.py` (uruchamiany też w GitHub Actions przed każdym wdrożeniem).

## Foldery Google Drive

- Root: `1O2DJuWIarEjfObcvDnNgiLgjj6L085CD`
- ATLET: `1Ln2SdkFZWY784sJn73Gv6VTIX7g-tZ6G`
- RIGGER: `1MozqWoI71Cg2R_n9PHEOdlEVpVTIO2si`

Każda marka używa katalogów logicznych: `do-instagrama`, `nowsza-wersja`, `zakonczone`. Nie mieszać marek i nie tworzyć drugiego roota bez jawnej migracji.

