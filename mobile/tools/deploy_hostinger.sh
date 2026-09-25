#!/usr/bin/env bash
# Wdrożenie BYKU.PUBLIKACJE MOBILE na Hostinger (SSH, port 65002) + kontrola po wdrożeniu.
#
# Wymagane zmienne środowiskowe (NIGDY w repozytorium):
#   HOSTINGER_HOST      np. 123.45.67.89           (hPanel → Zaawansowane → Dostęp SSH)
#   HOSTINGER_USER      np. u123456789
#   HOSTINGER_PORT      domyślnie 65002
#   HOSTINGER_WEB_DIR   katalog publiczny, np. domains/twojadomena.pl/public_html/mobile
#   BYKU_PUBLIC_URL     np. https://twojadomena.pl/mobile
#   SSH: klucz w ~/.ssh (zalecane) albo SSHPASS + sshpass
# Opcjonalnie przy pierwszym wdrożeniu (tworzy konto logowania):
#   BYKU_MOBILE_LOGIN, BYKU_MOBILE_PASSWORD (min. 12 znaków)
set -euo pipefail
cd "$(dirname "$0")/.."

: "${HOSTINGER_HOST:?Ustaw HOSTINGER_HOST}" "${HOSTINGER_USER:?Ustaw HOSTINGER_USER}" "${HOSTINGER_WEB_DIR:?Ustaw HOSTINGER_WEB_DIR}" "${BYKU_PUBLIC_URL:?Ustaw BYKU_PUBLIC_URL}"
PORT="${HOSTINGER_PORT:-65002}"
PRIVATE_DIR="${HOSTINGER_PRIVATE_DIR:-byku-mobile-private}"   # względem katalogu domowego, poza public_html
SSH=(ssh -p "$PORT" -o StrictHostKeyChecking=accept-new)
RSYNC_SSH="ssh -p $PORT -o StrictHostKeyChecking=accept-new"
if [[ -n "${SSHPASS:-}" ]]; then SSH=(sshpass -e "${SSH[@]}"); RSYNC_SSH="sshpass -e $RSYNC_SSH"; fi
REMOTE="$HOSTINGER_USER@$HOSTINGER_HOST"

echo "1/5 Testy przed wdrożeniem"
npm test --silent >/dev/null

echo "2/5 Paczka produkcyjna (tylko pliki uruchomieniowe)"
DIST="$(mktemp -d)"
cp -r index.html styles.css sw.js manifest.webmanifest .htaccess icons src "$DIST/"
mkdir -p "$DIST/api" && cp -r api/index.php api/.htaccess api/lib "$DIST/api/"

echo "3/5 Wysyłka na $REMOTE:$HOSTINGER_WEB_DIR"
"${SSH[@]}" "$REMOTE" "mkdir -p '$HOSTINGER_WEB_DIR' ~/'$PRIVATE_DIR' && chmod 700 ~/'$PRIVATE_DIR'"
rsync -rlz --delete --exclude 'api/local-config.php' -e "$RSYNC_SSH" "$DIST/" "$REMOTE:$HOSTINGER_WEB_DIR/"
rsync -z -e "$RSYNC_SSH" api/tools/make-config.php "$REMOTE:$PRIVATE_DIR/make-config.php"
rm -rf "$DIST"

echo "4/5 Konfiguracja serwera (katalog prywatny poza public_html)"
"${SSH[@]}" "$REMOTE" "cd ~ && P=\$(cd '$PRIVATE_DIR' && pwd) && printf '<?php\nreturn [\"private_dir\" => \"%s\"];\n' \"\$P\" > '$HOSTINGER_WEB_DIR/api/local-config.php'"
if [[ -n "${BYKU_MOBILE_LOGIN:-}" && -n "${BYKU_MOBILE_PASSWORD:-}" ]]; then
  "${SSH[@]}" "$REMOTE" "cd ~ && BYKU_PASSWORD='$BYKU_MOBILE_PASSWORD' php '$PRIVATE_DIR/make-config.php' \"\$(cd '$PRIVATE_DIR' && pwd)\" '$BYKU_MOBILE_LOGIN'"
fi

echo "5/5 Kontrola po wdrożeniu: $BYKU_PUBLIC_URL"
fail=0
check() { local want="$1" url="$2" got; got=$(curl -s -o /dev/null -w '%{http_code}' "$url"); if [[ "$got" == "$want" ]]; then echo "  OK  $want $url"; else echo "  BŁĄD oczekiwano $want, jest $got: $url"; fail=1; fi; }
check 200 "$BYKU_PUBLIC_URL/"
check 200 "$BYKU_PUBLIC_URL/manifest.webmanifest"
check 200 "$BYKU_PUBLIC_URL/sw.js"
check 401 "$BYKU_PUBLIC_URL/api/index"
check 403 "$BYKU_PUBLIC_URL/api/lib/server.php"
check 403 "$BYKU_PUBLIC_URL/api/local-config.php"
http_url="${BYKU_PUBLIC_URL/https:/http:}"
code=$(curl -s -o /dev/null -w '%{http_code}' "$http_url/"); [[ "$code" == "301" ]] && echo "  OK  HTTP → HTTPS" || { echo "  BŁĄD brak przekierowania na HTTPS ($code)"; fail=1; }
curl -sI "$BYKU_PUBLIC_URL/" | grep -qi '^strict-transport-security' && echo "  OK  HSTS" || { echo "  BŁĄD brak HSTS"; fail=1; }
session=$(curl -s "$BYKU_PUBLIC_URL/api/session"); [[ "$session" == *'"authenticated":false'* ]] && echo "  OK  API odpowiada, sesja wymagana" || { echo "  BŁĄD API: $session"; fail=1; }
exit $fail
