# Wdrożenie na Hostinger

Wymagania: plan Hostinger z dostępem SSH (Premium/Business/Cloud), PHP ≥ 8.1, SSL włączony dla domeny.

## Raz: dostęp

1. hPanel → **Zaawansowane → Dostęp SSH** → włącz SSH, zanotuj IP, port (zwykle `65002`) i użytkownika (`u123456789`).
2. hPanel → **Zaawansowane → Konfiguracja PHP** → wersja 8.2 lub nowsza.
3. hPanel → **Bezpieczeństwo → SSL** → certyfikat aktywny dla domeny.

## Wdrożenie (jedno polecenie)

```bash
export HOSTINGER_HOST=IP HOSTINGER_USER=u123456789 HOSTINGER_PORT=65002
export HOSTINGER_WEB_DIR=domains/TWOJADOMENA/public_html/mobile
export BYKU_PUBLIC_URL=https://TWOJADOMENA/mobile
export BYKU_MOBILE_LOGIN=damian BYKU_MOBILE_PASSWORD='min-12-znakow'   # tylko pierwszy raz
bash mobile/tools/deploy_hostinger.sh
```

Skrypt:
1. uruchamia testy (nie wdraża, gdy nie przejdą),
2. wysyła tylko pliki uruchomieniowe (bez testów i narzędzi),
3. tworzy katalog prywatny `~/byku-mobile-private` **poza** `public_html` (dane, sesje, konfiguracja),
4. przy pierwszym wdrożeniu tworzy konto i **wypisuje token desktopu** — wpisz go do `desktop/.env`,
5. sprawdza: strona 200, manifest 200, `sw.js` 200, `api/index` bez logowania = 401,
   `api/lib` i `local-config.php` = 403, przekierowanie HTTP→HTTPS, nagłówek HSTS.

## Po wdrożeniu — telefon

1. Otwórz `BYKU_PUBLIC_URL` w Safari (iPhone) lub Chrome (Android).
2. iPhone: Udostępnij → **Do ekranu początkowego**. Android: menu → **Zainstaluj aplikację**.
3. Zaloguj się. Na desktopie: panel **TikTok → Instagram** → „Wyślij na telefon”. Na telefonie: „Odśwież i sprawdź zgodność”.

## Zmiana hasła / dodanie osoby

```bash
ssh -p 65002 u123456789@IP
php ~/byku-mobile-private/make-config.php ~/byku-mobile-private LOGIN
```

Istniejący token desktopu zostaje. Nowy token: `BYKU_UPLOAD_TOKEN=$(openssl rand -hex 32) php ... ` (wpisz go potem do `desktop/.env`).

## Wycofanie

Pliki aplikacji można nadpisać poprzednią wersją z gita (`git checkout <commit> -- mobile && bash mobile/tools/deploy_hostinger.sh`).
Dane w `~/byku-mobile-private` nie są dotykane przez wdrożenie.
