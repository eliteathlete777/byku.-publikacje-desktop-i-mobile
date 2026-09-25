@echo off
rem BYKU.PUBLIKACJE DESKTOP — start panelu (http://127.0.0.1:8902). Jedna instancja.
cd /d "%~dp0"
where pythonw.exe >nul 2>nul
if %errorlevel%==0 (
  start "BYKU.PUBLIKACJE DESKTOP" pythonw.exe "%~dp0run.py"
  exit /b 0
)
where pyw.exe >nul 2>nul
if %errorlevel%==0 (
  start "BYKU.PUBLIKACJE DESKTOP" pyw.exe -3 "%~dp0run.py"
  exit /b 0
)
echo Nie znaleziono Pythona 3 (pythonw.exe / pyw.exe). Zainstaluj Python 3.11+ z python.org.
pause
exit /b 1
