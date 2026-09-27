# Telefon ↔ komputer przez Tailscale (zamiast Hostingera)

Desktop sam serwuje appkę telefonu i paczki. Tailscale daje telefonowi prywatny, szyfrowany adres HTTPS do Twojego komputera — działa w domu i na danych komórkowych. Nic nie leży publicznie w internecie, nie ma abonamentu ani FTP.

```
Telefon (Chrome, Tailscale włączony)
   │  https://<nazwa-pc>.<tailnet>.ts.net/        ← prywatne HTTPS, tylko Twoje urządzenia
   ▼
Tailscale na PC  →  127.0.0.1:8903  serwer telefonu desktopu
                      ├─ /               appka telefonu (folder mobile/)
                      ├─ /paczki/…       paczki z „Paczka na telefon” (tylko odczyt)
                      └─ /api/events     czynności z telefonu → desktop (automatycznie)
```

Reszta API desktopu (zapis treści, haczyki, kalendarz, port 8902) **nie jest** dostępna z telefonu.

## Konfiguracja — raz, ok. 5 minut

1. **Komputer:** pobierz i zainstaluj Tailscale → https://tailscale.com/download/windows. Zaloguj się (np. kontem Google). Plan osobisty jest darmowy.
2. **Telefon:** zainstaluj „Tailscale” z Google Play, zaloguj się **tym samym kontem**, włącz przełącznik połączenia.
3. **Panel Tailscale** (https://login.tailscale.com/admin/dns): włącz **MagicDNS** oraz **HTTPS Certificates**. Bez tego telefon nie dostanie HTTPS, a Android zablokuje udostępnianie do Instagrama.
4. **Komputer:** w folderze appki kliknij dwukrotnie `telefon-tailscale.cmd`. Skrypt wystawia serwer telefonu w Twojej prywatnej sieci (`tailscale serve --bg 8903`) i pokazuje adres. Ustawienie zostaje po restarcie komputera.
5. Uruchom desktop (`start.cmd`). W lewym dolnym rogu pojawi się „Telefon: … · Tailscale”, a w karcie publikacji → Publikowanie zobaczysz adres z przyciskiem „Kopiuj adres”.
6. **Telefon:** otwórz ten adres w Chrome → menu ⋮ → „Zainstaluj aplikację” / „Dodaj do ekranu głównego”.

## Codzienna praca

- Na desktopie: karta → Publikowanie → **Paczka na telefon**. Paczka od razu jest widoczna na telefonie (appka odświeża się sama przy otwarciu; przycisk ↻ wymusza odświeżenie).
- Na telefonie: paczka → 1. Kopiuj podpis → 2. Udostępnij → Instagram → 3. muzyka, wklej, publikuj → 4. **✓ Opublikowałem**.
- Każda czynność z telefonu trafia do desktopu sama. Zgłoszenie publikacji widać na karcie jako „Telefon ✓ IG” — zatwierdzasz haczyk jednym przyciskiem.

Warunek: komputer włączony, desktop uruchomiony, Tailscale włączony na telefonie. Gdy komputer jest wyłączony, telefon pokazuje „PC Niedostępny”, trzyma ostatnio pobraną listę i wyśle zaległe czynności, gdy połączenie wróci.

## Kontrola

| Co | Gdzie | Oczekiwany wynik |
|---|---|---|
| Serwer telefonu działa | na PC: http://127.0.0.1:8903/api/ping | `{"ok": true, …}` |
| Tailscale wystawia serwer | `telefon-tailscale.cmd` / `tailscale serve status` | `https://<nazwa-pc>…ts.net → http://127.0.0.1:8903` |
| Telefon widzi komputer | plakietka w appce | **PC Połączony** |

## Zmiana portu

`desktop/config.json` → `"phone": {"enabled": true, "port": 8903, "public_url": ""}`. Po zmianie portu uruchom `tailscale serve --bg <nowy-port>`. `public_url` wpisz tylko wtedy, gdy adres ma być inny niż wykryty automatycznie z Tailscale.

## Powrót do Hostingera

Moduł FTPS (`desktop/backend/hostinger_sync.py`) został w kodzie i ma testy — jest tylko wyłączony (`"hostinger": {"enabled": false}`). Instrukcja: `DEPLOY_HOSTINGER.md`.
