# Wspólny kontrakt BYKU.PUBLIKACJE

Desktop i Mobile są osobnymi aplikacjami oraz osobnymi kodami. Łączy je wyłącznie wersjonowany kontrakt paczki i serwera.

## Tożsamość i wersja

Klucz paczki: `post_id + marka`. Wersja treści: SHA-256 zawartości `post.json`, `opis.txt` i `miniaturka.png`. Transport telefonu używa `schema_version`, `content_revision` i sum każdego pliku.

## Źródła prawdy

- Produkcyjne paczki: istniejący `studio-kolejka`.
- Ręczny haczyk: wyłącznie `platformy_stan[channel].haczyk` zapisany świadomą akcją użytkownika.
- Dowód platformy: osobne pole `platform_evidence`; nigdy nie stawia haczyka.
- Serwer telefonu desktopu (`phone.port`, domyślnie 8903, wystawiony przez Tailscale): transport plików i przyjęcie czynności, nie baza stanów i nie druga kolejka produkcyjna. Hostinger (FTPS) jest wstrzymany, ale kod zostaje. Telefon przyjmuje też dowolny adres `index.json` z CORS.
- Historia uczenia: SQLite desktopu; reguły stylu są oddzielne dla ATLET i RIGGER.

## Paczka telefonu

Obowiązkowe pola manifestu: `schema_version`, `post_id`, `brand`, `content_revision`, `exported_at`, `channel`, `source_state`, `files[{name,sha256}]`.

Pola opcjonalne (desktop wysyła, telefon używa, gdy są): `title` — nazwa materiału (plik), `headline` — tytuł karty z pierwszego akapitu opisu (telefon pokazuje `headline`, potem `title`), `media_type` — `reel` albo `carousel`, `target_at` — lokalny termin publikacji `RRRR-MM-DD GG:MM`. Plik `podpis.txt` (opis + pusta linia + hashtagi) jest gotowym podpisem do wklejenia; gdy go brak, telefon skleja podpis z `opis-do-skopiowania.txt` i `hashtagi.txt`. Starsze paczki bez tych pól działają dalej.

`exported_at` ma precyzję milisekund (ISO 8601, UTC, `Z`) — rozstrzyga, która rewizja jest nowsza.

Materiał: rolka ma w paczce dokładnie jeden film — `*-hd.mp4`, jeśli Studio go wygenerowało, inaczej oryginał; niedokończone `*.part.*` są pomijane. Karuzela ma wszystkie slajdy.

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

Eksport z telefonu: `{"schema_version":1,"source":"mobile","exported_at":"…","events":[…]}` → automatycznie `POST /api/events` na serwerze telefonu (po każdej czynności; zaległe przy powrocie połączenia), zapasowo plik → desktop, zakładka Uczenie → „Import z telefonu” (`POST /api/mobile-events/import`). Desktop pokazuje czynności w Historii karty, a `manual_hook` jako „Telefon ✓ IG” z przyciskiem zatwierdzenia haczyka. Deduplikacja po `event_id`, ponowny import jest bezpieczny. Import transportowy nigdy sam nie zmienia archiwum, dowodu platformy, terminu ani haczyka.

## Przepływ

1. Desktop: „Paczka na telefon” → paczka + `index.json` w `data/mobile-packages` (od razu widoczne dla serwera telefonu).
2. Telefon (`https://<nazwa-pc>.<tailnet>.ts.net/`): odświeżenie przy otwarciu lub ↻ → `paczki/index.json` → manifesty → pobranie z kontrolą SHA-256.
3. Telefon: każda czynność → `POST api/events` → desktop (`mobile-events.jsonl`).

Testy end-to-end: `desktop/tests/test_mobile_contract.py` i `desktop/tests/test_phone_server.py` (uruchamiane w GitHub Actions przy każdym pushu i PR).

## Foldery Google Drive

- Root: `1O2DJuWIarEjfObcvDnNgiLgjj6L085CD`
- ATLET: `1Ln2SdkFZWY784sJn73Gv6VTIX7g-tZ6G`
- RIGGER: `1MozqWoI71Cg2R_n9PHEOdlEVpVTIO2si`

Każda marka używa katalogów logicznych: `do-instagrama`, `nowsza-wersja`, `zakonczone`. Nie mieszać marek i nie tworzyć drugiego roota bez jawnej migracji.

