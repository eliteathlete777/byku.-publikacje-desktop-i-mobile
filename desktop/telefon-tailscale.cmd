@echo off
chcp 65001 >nul
title BYKU.PUBLIKACJE - telefon przez Tailscale
set "TS=C:\Program Files\Tailscale\tailscale.exe"
set "PORT=8903"

if not exist "%TS%" (
  echo Brak Tailscale na tym komputerze.
  echo Otwieram strone pobierania - zainstaluj, zaloguj sie i uruchom ten plik ponownie.
  start "" "https://tailscale.com/download/windows"
  pause
  exit /b 1
)

"%TS%" status >nul 2>&1
if errorlevel 1 (
  echo Tailscale nie jest polaczony - loguje...
  "%TS%" up
)

echo.
echo Wystawiam serwer telefonu (127.0.0.1:%PORT%) w Twojej prywatnej sieci Tailscale...
"%TS%" serve --bg %PORT%
if errorlevel 1 (
  echo.
  echo Nie udalo sie. Najczesciej: w panelu Tailscale wylaczone HTTPS Certificates.
  echo Wlacz MagicDNS i HTTPS: https://login.tailscale.com/admin/dns
  pause
  exit /b 1
)

echo.
"%TS%" serve status
echo.
echo Gotowe. Otworz powyzszy adres https://... w Chrome na telefonie (z wlaczonym Tailscale)
echo i dodaj appke do ekranu glownego. Ustawienie zostaje po restarcie komputera.
pause
