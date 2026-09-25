# BYKU.PUBLIKACJE MOBILE

Instalowalna aplikacja PWA na telefon + serwer PHP (Hostinger). Zadanie: dostarczyć na telefon materiały
„TikTok gotowy — Instagram czeka”: plik (film albo slajdy), miniaturę, opis, hashtagi i stan publikacji.

## Bezpieczeństwo

| Warstwa | Ochrona |
|---|---|
| Serwer | każda trasa z danymi (`index`, `file`, `events`) wymaga sesji → inaczej `401` i zero danych |
| Sesja | losowy token 256 bit w cookie `HttpOnly; Secure; SameSite=Strict`; na serwerze tylko hash; wygasa po 12 h bez ruchu lub po 7 dniach |
| Hasło | bcrypt (`password_hash`), limit 5 błędnych prób / 15 min na IP |
| CSRF | `SameSite=Strict` + wymagany nagłówek `X-Byku-Client` |
| Pliki | wydawane wyłącznie przez `api/file` z kontrolą nazwy; tylko aktualna wersja; katalog danych **poza** `public_html` |
| Desktop → serwer | token Bearer (na serwerze tylko SHA-256 tokenu), SHA-256 każdego pliku, starsza wersja odrzucana |
| Telefon | ostatni odczyt offline widoczny tylko przy ważnej sesji; wylogowanie / wygaśnięcie / `401` czyści dane i pliki; service worker nie przechowuje API ani materiałów |
| HTTPS | wymuszone w `.htaccess` + HSTS + CSP |

W kodzie klienta nie ma sekretów ani kluczy.

## Ekrany

- **Logowanie** — bez niego nic nie jest widoczne.
- **Lista** — stały przycisk **„Odśwież i sprawdź zgodność”**, stan: *aktualna / dostępna nowsza wersja / niekompletna / niezgodna / offline*, filtr marki.
- **Paczka** — podgląd wideo albo karuzeli (po sprawdzeniu SHA-256), kroki 1–5, przyciski:
  *Udostępnij / zapisz film (slajdy)*, *Kopiuj opis*, *Kopiuj hashtagi*, *Kopiuj opis + hashtagi*, *Pobierz miniaturę*,
  *Otwórz Instagram*, *Zgłoś: opublikowane na Instagramie*.

Plik z niezgodną sumą SHA-256 jest blokowany (nie da się go udostępnić ani pobrać).
Zgłoszenie z telefonu trafia na desktop jako osobne zdarzenie — nie zmienia haczyka ani dowodu.

## Struktura

```
index.html styles.css sw.js manifest.webmanifest icons/   PWA
src/contract.js   walidator kontraktu v2 (ten sam wynik co desktop i PHP)
src/domain.js     łączenie indeksu, wersje, stany, SHA-256
src/session.js    sesja na telefonie, czyszczenie danych, klient API
src/app.js        interfejs
api/index.php     trasy API;  api/lib/server.php  sesje, paczki, zdarzenia;  api/lib/contract.php
api/tools/make-config.php   konfiguracja (konsola SSH)
tools/deploy_hostinger.sh   wdrożenie + kontrola
tests/            52 testy: kontrakt, domena, sesja, prawdziwy serwer PHP
```

## Lokalnie

```
npm test                              # wymaga Node 20+ i PHP 8.1+
php api/tools/make-config.php /tmp/byku-private damian
BYKU_PRIVATE_DIR=/tmp/byku-private BYKU_INSECURE_COOKIE=1 npm run serve   # http://127.0.0.1:8903
```

`BYKU_INSECURE_COOKIE` tylko lokalnie (HTTP). Na serwerze cookie jest zawsze `Secure`.

Wdrożenie: `DEPLOY.md`.
