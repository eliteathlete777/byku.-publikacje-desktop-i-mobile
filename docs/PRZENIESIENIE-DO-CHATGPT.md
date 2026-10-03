# Przeniesienie BYKU z Claude Code do ChatGPT (Codex) — 03.10.2026

## Co się NIE zmienia
Aplikacja działa lokalnie na komputerze Damiana i nie zależy od subskrypcji Claude:
panel BYKU.PUBLIKACJE (`127.0.0.1:8902`, skrót „BYKU.PUBLIKACJE DESKTOP v2”), BYQ Studio, uploadery,
kolejka paczek, zalogowane okna przeglądarek marek. Zmienia się tylko asystent, który to rozwija i pilnuje.

## Gdzie jest wiedza
| Co | Gdzie |
|---|---|
| Zasady pracy Damiana (globalne) | `C:\Users\DELL\.codex\AGENTS.md` |
| Panel — instrukcja agenta | `BYKU-PUBLIKACJE\AGENTS.md` |
| Uploadery — instrukcja agenta | `byku-publisher-desktop\AGENTS.md` |
| Skille (te same co w Claude) | `C:\Users\DELL\.codex\skills\byku-*` + kopia `BYKU-PUBLIKACJE\docs\skills\` |
| Pełna kopia lokalna (kod + kolejka, bez profili przeglądarek) | `C:\Users\DELL\Desktop\BYKU-KOPIA-2026-10-03` (2,76 GB) |
| Pamięć Claude (oryginał) | `C:\Users\DELL\.claude\projects\C--Users-DELL-Downloads\memory\` (+ kopia w BYKU-KOPIA) |

## Git
- Panel: `github.com/eliteathlete777/byku.-publikacje-desktop-i-mobile` (PUBLICZNE), gałąź `claude/determined-planck-zjocfn`.
- Uploadery: lokalny commit na gałęzi `kopia/2026-10-03-przed-chatgpt` (117 plików — wcześniej większość kodu była tylko na dysku).
  Repo `byku-publisher-desktop` na GitHubie nie istnieje → załóż PRYWATNE repo o tej nazwie i wykonaj w folderze uploaderów:
  `git push -u origin kopia/2026-10-03-przed-chatgpt`.

## AI w panelu (opisy z podstawy)
W `BYKU-PUBLIKACJE\desktop\.env`: `AI_PROVIDER=openai` i `OPENAI_API_KEY=` (klucz wkleja Damian), restart panelu ze skrótu.
Bez tych linii panel użyje Claude API (`ANTHROPIC_API_KEY`) — to płatne API, niezależne od subskrypcji Claude.

## Otwarte sprawy (stan 03.10)
1. Lista Meta „Zaplanowane” wróciła pusta przy ostatnim odczycie (Opublikowane działa) — dłuższe czekanie / przewijanie kontenera tabeli w `kalendarz_live._zrzut_meta`.
2. „Odśwież kalendarz” w panelu: Rigger padł „Connection closed while reading from the driver”, ten sam odczyt uruchomiony osobno działał — sprawdzić drugi `sync_playwright` w tym samym wątku.
3. Atlet: TikTok (Edge :9224) i Meta (Edge :9222) były zamknięte — odczyt otworzył nowe okna i TikTok dał 0 kart.
4. Gałąź panelu niezmergowana do `main`; mobile niewdrożone (brak SSH Hostinger).
5. Pierwszy pełny przebieg Meta bez pomocy: 29.09 „ze mi sie przytyło” doszło do terminu, minuta nie siadła — naprawione (spinbutton bez limitu 45), do potwierdzenia na następnym wrzucie.
