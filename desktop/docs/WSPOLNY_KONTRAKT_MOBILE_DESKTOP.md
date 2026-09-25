# Wspólny kontrakt BYKU.PUBLIKACJE

Desktop i Mobile są osobnymi aplikacjami oraz osobnymi kodami. Łączy je wyłącznie wersjonowany kontrakt paczki i serwera.

## Tożsamość i wersja

Klucz paczki: `post_id + marka`. Wersja treści: SHA-256 zawartości `post.json`, `opis.txt` i `miniaturka.png`. Transport telefonu używa `schema_version`, `content_revision` i sum każdego pliku.

## Źródła prawdy

- Produkcyjne paczki: istniejący `studio-kolejka`.
- Ręczny haczyk: wyłącznie `platformy_stan[channel].haczyk` zapisany świadomą akcją użytkownika.
- Dowód platformy: osobne pole `platform_evidence`; nigdy nie stawia haczyka.
- Google Drive: transport plików, nie baza stanów i nie druga kolejka produkcyjna.
- Historia uczenia: SQLite desktopu; reguły stylu są oddzielne dla ATLET i RIGGER.

## Paczka telefonu

Obowiązkowe pola manifestu: `schema_version`, `post_id`, `brand`, `content_revision`, `exported_at`, `channel`, `source_state`, `files[{name,sha256}]`.

Mobile może zapisać własne zdarzenia: pobrano, skopiowano opis, otwarto Instagram, wysłano, ręczny haczyk. Import transportowy nigdy sam nie zmienia archiwum, dowodu platformy, terminu ani haczyka.

## Foldery Google Drive

- Root: `1O2DJuWIarEjfObcvDnNgiLgjj6L085CD`
- ATLET: `1Ln2SdkFZWY784sJn73Gv6VTIX7g-tZ6G`
- RIGGER: `1MozqWoI71Cg2R_n9PHEOdlEVpVTIO2si`

Każda marka używa katalogów logicznych: `do-instagrama`, `nowsza-wersja`, `zakonczone`. Nie mieszać marek i nie tworzyć drugiego roota bez jawnej migracji.

