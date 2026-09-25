# Plan dalszy

Kolejność. Każdy krok kończy się testem.

1. **Wdrożenie mobile na Hostinger** (`mobile/DEPLOY.md`), test na fizycznym iPhone/Androidzie: instalacja, logowanie, udostępnienie filmu do Instagrama, tryb samolotowy.
2. **Desktop na prawdziwej kolejce**: skrót, panel System → rdzeń `studio`, przegląd kart w trybie podglądu, ustawienie `google_drive.local_sync_dir`, pierwsza paczka na telefon.
3. **Decyzja właściciela: zapis produkcyjny** (`allow_production_writes=true`) — edycja opisów, terminów, haczyków na prawdziwej kolejce.
4. **Decyzja właściciela: przygotowanie publikacji** (`allow_publication=true`) — uploadery Studio przez `legacy_bridge`, końcowe kliknięcie nadal ręczne.
5. **Automatyzacja uruchamiana z telefonu (propozycja)** — przycisk w mobile → webhook n8n (Hostinger) → przygotowanie publikacji przez oficjalne Instagram Graph API (konto firmowe/twórcy), zatwierdzenie jednym przyciskiem na telefonie. Muzyka z biblioteki Instagrama pozostaje ręczna (API jej nie obsługuje). Wymaga: tokenu Meta w sekretach n8n, nowego typu zdarzenia w kontrakcie (v3) z testami po obu stronach.

## Zasady dla kolejnego agenta

- Zmiana kontraktu = `contract/KONTRAKT.md` + `contract/fixtures/cases.json` + trzy walidatory + testy po obu stronach.
- Nie usuwać blokad `allow_*`, nie automatyzować końcowego kliknięcia, nie traktować zgłoszeń z telefonu ani LIVE jako haczyka.
- Przed pushem: `desktop` unittest + `tools/ui_smoke.py`, `mobile` `npm test`, `e2e/test_transfer.py` (to samo robi CI).
