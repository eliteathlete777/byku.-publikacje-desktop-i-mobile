# Wdrożenie na Hostinger — BYKU.PUBLIKACJE

> **Wstrzymane (2026-09-27).** Telefon łączy się bezpośrednio z desktopem przez Tailscale — zob. `TELEFON_TAILSCALE.md`. Ta instrukcja zostaje na wypadek powrotu do Hostingera; workflow FTP usunięto z `.github/workflows` (jest w historii Gita), moduł `hostinger_sync.py` jest nadal w kodzie, wyłączony w `config.json`.

Docelowo: appka telefonu pod `https://<domena>/publikacje/`, paczki pod `https://<domena>/publikacje/paczki/`. Jeden serwer, zero CORS.

```
public_html/publikacje/         ← mobile/ (GitHub Actions, automatycznie)
public_html/publikacje/paczki/  ← paczki z desktopu (FTPS, przycisk / automat po eksporcie)
```

## 1. Konto FTP (hPanel, raz)

hPanel → Pliki → Konta FTP. Zanotuj: host (np. `ftp.twojadomena.pl` lub IP), użytkownika, hasło. Folder `public_html/publikacje` utworzy się sam przy pierwszym wdrożeniu.

## 2. Appka telefonu — automatyczne wdrożenie (GitHub Actions)

GitHub → repozytorium → Settings → Secrets and variables → Actions → **New repository secret**:

| Sekret | Wartość |
|---|---|
| `HOSTINGER_FTP_SERVER` | host FTP |
| `HOSTINGER_FTP_USERNAME` | użytkownik FTP |
| `HOSTINGER_FTP_PASSWORD` | hasło FTP |

Opcjonalnie zmienna (zakładka Variables) `HOSTINGER_MOBILE_DIR`, domyślnie `public_html/publikacje/`. Dla konta FTP zakorzenionego już w `public_html` ustaw `publikacje/`.

Od teraz każdy push do `main` zmieniający `mobile/` → testy (Mobile + kontrakt end-to-end) → wgranie. Ręcznie: Actions → „Mobile → Hostinger” → Run workflow. Bez sekretów workflow kończy się ostrzeżeniem, nie błędem.

## 3. Desktop — wysyłka paczek

`desktop/config.json`:

```json
"hostinger": {
  "enabled": true,
  "host": "ftp.twojadomena.pl",
  "port": 21,
  "user": "UŻYTKOWNIK_FTP",
  "tls": true,
  "remote_dir": "public_html/publikacje/paczki",
  "public_url": "https://twojadomena.pl/publikacje/"
}
```

Hasło **tylko** w zmiennej środowiskowej (nigdy w pliku):

```powershell
setx BYKU_HOSTINGER_FTP_PASSWORD "hasło-ftp"
```

Zamknij i otwórz ponownie `start.cmd`. Panel systemu pokaże „Hostinger: połączony”. Od tej chwili „Przygotuj na telefon” sam wysyła paczkę; przycisk „Wyślij paczki na Hostinger” (zakładka Publikowanie) robi to ręcznie. Wysyłane są tylko zmienione pliki, `index.json` zawsze na końcu.

## 4. Telefon

Otwórz `https://<domena>/publikacje/` → menu przeglądarki → „Dodaj do ekranu głównego”. Ustawienia: adres zostaw `paczki/index.json`.

## 5. Prywatność (zalecane)

Paczki to niepublikowane materiały. hPanel → Zaawansowane → **Katalogi chronione hasłem** → `public_html/publikacje`. Telefon zapyta o hasło raz; appka i pobieranie paczek działają dalej (ten sam serwer). `.htaccess` blokuje już listowanie katalogów i indeksowanie w Google.

## Kontrola po wdrożeniu

1. `https://<domena>/publikacje/` otwiera appkę, plakietka ONLINE.
2. `https://<domena>/publikacje/paczki/index.json` zwraca JSON z `packages`.
3. W appce „Odśwież i sprawdź zgodność” → karty paczek → „Pobierz film” → „każda suma SHA-256 jest zgodna”.
