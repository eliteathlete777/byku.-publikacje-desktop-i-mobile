---
name: byku-publikacje-panel
description: Panel desktop BYKU.PUBLIKACJE (Python + JS, 127.0.0.1:8902) — gdzie leży, jak uruchamiać/restartować, konfiguracja, klucze API, funkcje (Stół publikacji, wrzut z checkboxami, Odśwież kalendarz, opis z podstawy przez AI, edytor miniatury, samouczek, Marki i styl), testy i GitHub. Użyj ZAWSZE, gdy Damian mówi o „appce/panelu BYKU.PUBLIKACJE”, „stole publikacji”, prosi o zmianę w panelu, test panelu, restart, wrzucenie na GitHuba, klucz API albo dodanie funkcji.
---

# Panel BYKU.PUBLIKACJE (desktop)

## Położenie i uruchamianie
- Repo: `C:\Users\DELL\Documents\Codex\2026-09-25\wy\work\BYKU-PUBLIKACJE` (desktop/ + mobile/ PWA+PHP pod Hostinger — mobile NIE wdrożony, brak danych SSH).
- GitHub: `eliteathlete777/byku.-publikacje-desktop-i-mobile`, praca na gałęzi `claude/determined-planck-zjocfn` (nie zmergowana do `main`). Git wymaga `git -c safe.directory=*`.
- `desktop/config.json` ma LOKALNE zmiany (allow_production_writes=true, allow_publication=true, style_source_dir) — **nie commitować**.
- Sekrety: `desktop/.env` (ignorowany): `ANTHROPIC_API_KEY` (wpisany przez Damiana), `OPENAI_API_KEY` (pusty), `OPENAI_MODEL`, `CLAUDE_MODEL`, `AI_PROVIDER`. Claude NIGDY nie wpisuje ani nie wyciąga kluczy — tylko pokazuje Damianowi dokładny plik i linię.
- Start/restart (config czytany raz na starcie): zabij `pythonw run.py`, potem `explorer.exe "C:\Users\DELL\Desktop\BYKU.PUBLIKACJE DESKTOP v2.lnk"` (NIE z Bash — uploadery muszą mieć rodzica explorer). Sprawdzenie: `GET http://127.0.0.1:8902/api/health`.
- Rdzeń: panel importuje BYQ Studio z `source_root` = `...\05_APLIKACJE_SKRYPTY\byku-publisher-desktop` (kolejka `studio-kolejka`). Stary GUI: skrót „BYQ Studio.lnk” (`studio\uruchom.py`).
- Testy panelu: w `desktop/` → `python -m unittest discover -s tests -t .` (44 testy). Front: `node --check frontend/js/...`.

## Funkcje
- **Dodaj** (pierwsza zakładka, `frontend/js/views/add.js`, `backend/import_service.py`): przeciągnij foldery / folder nadrzędny / pliki albo „Wybierz folder… / pliki…”. Folder = rolka, nazwa folderu = nazwa rolki i pliku w paczce. Z folderu idzie NAJWIĘKSZY film (mniejszy plik = odpad produkcji, np. MP3). Marka obowiązkowa, lokalizacja wsadu opcjonalna. Film leci strumieniem `POST /api/import/reel?brand&title&name&location`, duplikaty tytułu w marce są pomijane (`POST /api/import/check`). Paczka = szkic z pustym opisem (`core.create_draft`, zapis z `wymus=True`), okładka startowa = klatka z filmu (ffmpeg z imageio_ffmpeg). Bramka wrzutu nie przepuści szkicu bez opisu. Pod spodem lista „Od filmu do Zaplanuj”: Film → Opis z podstawy (≥250) → Okładka (klatka / poprawiona) → Lokalizacja → Akceptacja → Termin → TikTok → IG + FB; klik etapu otwiera kartę. Tak działał stary Generator (goły film na start).
- **Stół publikacji** → panel „Wrzut na platformy”: zaakceptowane paczki z terminem, przyciski Wrzuć TikTok / Wrzuć IG + FB → okno potwierdzenia (lokalizacja, termin) → start w tle (`legacy_bridge.prepare_publication` → `most_publikacji.przygotuj_wrzut` + `uruchom_uploader`). Lista „Uruchomione w tej sesji” = **checkboxy etapów** (Film przygotowany (HD), Przeglądarka otwarta, Właściwe konto, Film wgrany, Opis wklejony, Okładka, Muzyka, Lokalizacja, Termin ustawiony, Gotowe — kliknij Zaplanuj). Surowych logów Damian NIE chce w UI — tylko jedno zdanie problemu. API: `GET /api/uploads`.
- Strażnik (STALL 120 s), auto-zdejmowanie osieroconych blokad, blokada per kanał, archiwizacja logów — szczegóły w skillu `byku-wrzut-platformy`.
- **📅 ↻ Odśwież kalendarz** (obok ↻): w tle `kalendarz_live` czyta TikTok Studio „Posty” (opublikowane + zaplanowane) i Meta (Terminarz −2..+2 tyg., scheduled_posts, published_posts) i odhacza paczki. Zablokowane, gdy trwa wrzut. API: `POST/GET /api/calendar/refresh`.
- **Opis z podstawy (AI)**: zakładka Treść → pole „Podstawa opisu” (zapis `data/podstawy.json`) → „Ułóż opis z podstawy” → 3 warianty. Dostawca: Claude (domyślnie `claude-sonnet-5`, `CLAUDE_MODEL`) albo ChatGPT (`OPENAI_API_KEY`, Responses API). Treść WYŁĄCZNIE z podstawy (kompendium = forma), pole Lokalizacja karty NIE idzie do modelu, kontrola wierności (liczby spoza podstawy, stara lokalizacja). Min. 250 znaków. `backend/ai_writer.py`.
- **Miniatura**: klik w miniaturę otwiera edytor; brak miniatury → klatka z filmu / pierwszy slajd. Opis edytowalny w Podglądzie.
- **Marki i styl**: kompendia `desktop/style/` (źródło: `Desktop\OFICJALNE STYLE BYKU`), banki haków/CTA, słowa kluczowe zamiast hashtagów.
- **Samouczek** 🎓 (15 kroków, `tour.js`).
- Doradca AI przy wrzucie został USUNIĘTY na życzenie Damiana (revert) — skrypty mają same klikać bezbłędnie.

## Zasady pracy z Damianem
- Pisze po polsku, często dyktuje (literówki z rozpoznawania mowy). Chce raportu wyniku, nie procesu; dokładnych ścieżek plików przy instrukcjach.
- Commit lokalny + push na gałąź po każdej zmianie panelu (bez config.json), stopka `Co-Authored-By: Claude …`.
- Pamięć projektu: `C:\Users\DELL\.claude\projects\C--Users-DELL-Downloads\memory\project_byku_publikacje.md`.
