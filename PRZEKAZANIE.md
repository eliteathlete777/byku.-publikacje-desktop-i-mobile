# Przekazanie projektu BYKU.PUBLIKACJE — stan na 2026-09-27

Ten plik daje agentowi (lub Tobie) wszystko, co trzeba, żeby dokończyć wdrożenie
appki mobilnej na Hostingerze, bez czytania całej historii rozmowy.

## Repozytorium

- GitHub: `eliteathlete777/byku.-publikacje-desktop-i-mobile`
- Branch produkcyjny: `main`
- Ostatni scalony commit w `main`: `423cb0bd40c8f1a1e392791d0e5d123563f6a549`
  ("Panel Instagrama pod Androida + odporność appki telefonu")
- **Nie ruszać** brancha `claude/determined-planck-zjocfn` — to inna, równoległa
  przebudowa (kontrakt v2, logowanie, serwer PHP) z osobnej sesji. Koliduje
  z ok. 7 tys. linii z tym, co jest teraz w `main`. Decyzja, czy w ogóle go
  używać, jeszcze nie zapadła — domyślnie zostajemy przy tym, co jest w `main`
  (proste FTP + pliki statyczne, bez logowania).

## Struktura

```
desktop/    — appka Windows (Python, http.server), generator/kolejka/stół publikacji
mobile/     — PWA na telefon (Android), czysty JS + HTML + CSS, bez buildu
.github/workflows/deploy-mobile-hostinger.yml — testy + wdrożenie mobile/ na Hostinger
DEPLOY_HOSTINGER.md — pełna instrukcja wdrożenia krok po kroku
```

## Co już działa (sprawdzone testami i emulacją)

- `mobile`: `npm test` w folderze `mobile/` — 17/17
- `desktop/tests/test_mobile_contract.py` — kontrakt Desktop ↔ Mobile end-to-end — 4/4
- Panel telefonu: 4 kroki (podpis → materiał → Instagram → haczyk), udostępnianie
  przez systemowe menu Androida do aplikacji Instagram, kopiowanie podpisu jednym
  przyciskiem, ikony PWA do instalacji na ekranie głównym.
- `desktop/backend/hostinger_sync.py`: wysyła paczki na Hostinger przez FTPS,
  tylko zmienione pliki, `index.json` na końcu. Hasło **wyłącznie** ze zmiennej
  środowiskowej `BYKU_HOSTINGER_FTP_PASSWORD`, nigdy w pliku.

## Co NIE jest zrobione — to jest właściwy cel

**Appka nie jest jeszcze wdrożona na żadnej domenie Hostingera.** Automat w
GitHub Actions (`.github/workflows/deploy-mobile-hostinger.yml`) uruchamia się
przy każdym pushu do `main`, ale krok wdrożenia **pomija się z ostrzeżeniem**,
bo w GitHubie nie ma jeszcze sekretów FTP. Stan sprawdzony 2026-09-26 21:55 UTC:
run #2, job `deploy`, krok „Sprawdź sekrety" → ostrzeżenie, checkout i FTP-Deploy
oba `skipped`.

## Dokładnie dwa brakujące elementy

### 1. Trzy sekrety w GitHub Actions

GitHub → repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Nazwa | Wartość |
|---|---|
| `HOSTINGER_FTP_SERVER` | host FTP z hPanel → Pliki → Konta FTP |
| `HOSTINGER_FTP_USERNAME` | użytkownik FTP |
| `HOSTINGER_FTP_PASSWORD` | hasło FTP |

Opcjonalnie zmienna (zakładka Variables, nie Secrets): `HOSTINGER_MOBILE_DIR`,
domyślnie `public_html/publikacje/`. Zmień, jeśli konto FTP jest już
zakorzenione w `public_html` (wtedy `publikacje/`).

Po dodaniu sekretów: **Actions → „Mobile → Hostinger" → Run workflow** (albo
poczekaj na kolejny push do `main`).

### 2. Konfiguracja desktopu (na Windows, u użytkownika)

Plik `desktop/config.json`, sekcja `hostinger`:

```json
"hostinger": {
  "enabled": true,
  "host": "ftp.TWOJADOMENA.pl",
  "port": 21,
  "user": "UŻYTKOWNIK_FTP",
  "tls": true,
  "remote_dir": "public_html/publikacje/paczki",
  "public_url": "https://TWOJADOMENA.pl/publikacje/"
}
```

Plus w PowerShell (jednorazowo, na koncie Windows użytkownika):
```powershell
setx BYKU_HOSTINGER_FTP_PASSWORD "hasło-ftp"
```
Potem zrestartować `start.cmd`. Panel systemu w appce desktop pokaże
„Hostinger: połączony".

## Czego lokalny agent nie może pominąć

- **Hasło FTP nigdy nie trafia do repo, configu w Git, ani do żadnego czatu.**
  Tylko `BYKU_HOSTINGER_FTP_PASSWORD` (zmienna środowiskowa) i sekret GitHuba.
- Zanim cokolwiek zmieni w `mobile/` lub `desktop/backend/mobile_packages.py`
  / `hostinger_sync.py`, niech uruchomi:
  ```
  cd mobile && npm test
  cd ../desktop && python3 -m unittest tests.test_mobile_contract
  ```
  Oba muszą przejść przed pushem.
- Kontrakt danych między appkami: `desktop/docs/WSPOLNY_KONTRAKT_MOBILE_DESKTOP.md`
  — tam są wszystkie pola manifestu (`title`, `target_at`, `podpis.txt` itd.)
  i lista zdarzeń telefonu. Zmiana formatu paczki musi zostać tam opisana.

## Kontrola po wdrożeniu (jak sprawdzić, że appka naprawdę działa)

1. `https://TWOJADOMENA.pl/publikacje/` → appka się ładuje, plakietka ONLINE.
2. `https://TWOJADOMENA.pl/publikacje/paczki/index.json` → zwraca JSON
   (będzie pusty `{"packages":[]}` dopóki desktop nie wyeksportuje pierwszej
   paczki — to normalne).
3. Na desktopie: zakładka Publikowanie → „Przygotuj na telefon" → powinno
   automatycznie wysłać paczkę na Hostinger (bo `hostinger.enabled: true`).
4. Odśwież `index.json` w przeglądarce — powinna pojawić się nowa paczka.
5. Na telefonie (Chrome/Android): otwórz appkę → „Odśwież i sprawdź zgodność"
   → paczka powinna się pokazać z miniaturą, terminem i podpisem.

## Zalecane, ale opcjonalne

`.htaccess` w `mobile/` już blokuje indeksowanie i listowanie katalogów.
Dodatkowo w hPanel: **Zaawansowane → Katalogi chronione hasłem** →
`public_html/publikacje` — paczki to niepublikowane materiały treningowe/
riggerskie, warto zablokować dostęp z zewnątrz jednym hasłem na cały folder.

## Domena

Nieustalona. Zapytaj użytkownika, pod jaką domeną/subdomeną ma stanąć appka
(np. `elite-athlete.shop/publikacje` albo osobna subdomena), zanim ustawisz
`remote_dir` i `public_url` w `config.json`.
