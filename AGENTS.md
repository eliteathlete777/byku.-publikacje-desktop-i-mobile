# AGENTS.md — BYKU.PUBLIKACJE (panel desktop + mobile)

Instrukcja dla agenta (ChatGPT/Codex). Przeniesione z Claude Code 03.10.2026. Szczegóły: `docs/skills/*/SKILL.md`
(te same skille są w `~/.codex/skills`) i `docs/PRZENIESIENIE-DO-CHATGPT.md`.

## Co to jest
- `desktop/` — panel Damiana: Python (`run.py`, ThreadingHTTPServer) + vanilla JS, `http://127.0.0.1:8902`.
- Importuje rdzeń BYQ Studio z `source_root` = `C:\Users\DELL\Desktop\aplikacje\05_APLIKACJE_SKRYPTY\byku-publisher-desktop`
  (kolejka paczek `studio-kolejka`, uploadery `tiktok_uploader.py` / `meta_uploader.py`). To osobne repo — patrz jego `AGENTS.md`.
- `mobile/` — PWA + PHP pod Hostinger, NIE wdrożone (brak danych SSH).

## Uruchamianie
- Restart: zabij `pythonw run.py`, potem `explorer.exe "C:\Users\DELL\Desktop\BYKU.PUBLIKACJE DESKTOP v2.lnk"`.
  NIGDY nie startuj panelu ani uploaderów z terminala agenta (uploadery muszą mieć rodzica explorer).
  Zdrowie: `GET /api/health`. Nie restartuj, gdy `GET /api/uploads` ma `running: true` (choć panel przejmuje żywe uploadery po restarcie).
- Testy: w `desktop/` → `python -m unittest discover -s tests -t .` (50 testów, muszą przejść). JS: `node --check plik.js`.
- Git: gałąź robocza `claude/determined-planck-zjocfn` (nie zmergowana do `main`), `git -c safe.directory=*`.
  REPO JEST PUBLICZNE — żadnych sekretów. `desktop/config.json` (lokalne zmiany) i `desktop/.env` nie idą do repo.

## AI w panelu (opisy z podstawy)
- `desktop/.env`: `AI_PROVIDER=openai` + `OPENAI_API_KEY=...` (Damian wkleja sam), `OPENAI_MODEL` (domyślnie gpt-5).
  Claude zostaje jako druga opcja (`ANTHROPIC_API_KEY`, `CLAUDE_MODEL`). Kod: `desktop/backend/ai_writer.py`.
- Treść opisu WYŁĄCZNIE z „podstawy” Damiana; kompendium = forma. 250–1200 znaków. Skill `byku-opisy-styl`.

## Proces twórczy (zakładka Dodaj — kolejności nie zmieniać)
Film wrzucony → Odtworzenie filmu → Okładka (studio miniatury, czcionka TYLKO Anton) → Opis z podstawy →
Lokalizacja → Akceptacja treści → Termin → TikTok → IG + FB (wrzut ze Stołu publikacji, końcowe Zaplanuj klika Damian).

## Potwierdzanie wrzutów
- Checkboxy nóg: TikTok i Meta (IG + FB razem). Damian odhacza ręcznie; wrzut z panelu z ✓ na wszystkich etapach
  (muzyka się nie liczy) odhacza sam (`legacy_bridge._auto_confirm`).
- Źródło prawdy platform: TikTok Studio → Posty (`tiktokstudio/content`) oraz Meta → Zawartość → Zaplanowane /
  Opublikowane (`business.facebook.com/latest/posts/scheduled_posts|published_posts`). NIE siatka Terminarza.
- Po „Odśwież kalendarz” powstaje `desktop/data/rozbieznosci.json` (`GET /api/legs/mismatches`).
  Zadanie agenta: dla każdej rozbieżności otwórz te listy zdalnie (CDP/computer-use), znajdź wpis po początku opisu
  i dacie, popraw odczyt (`studio/rdzen/kalendarz_live.py`) albo checkbox, opisz wniosek w skillu.
