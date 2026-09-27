# Tworzy skrót "BYKU.PUBLIKACJE DESKTOP" na pulpicie (uruchamia start.cmd z ikoną aplikacji).
# Użycie: powershell -ExecutionPolicy Bypass -File tools\install_shortcut.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath("Desktop")
$link = Join-Path $desktop "BYKU.PUBLIKACJE DESKTOP.lnk"
$launcher = Get-Command pythonw.exe, pyw.exe, python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $launcher) {
    throw "Nie znaleziono Pythona 3 (pythonw.exe / pyw.exe / python.exe)."
}
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = $launcher.Source
$shortcut.Arguments = '"' + (Join-Path $root "run.py") + '"'
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = (Join-Path $root "assets\byku-publikacje.ico") + ",0"
$shortcut.WindowStyle = 7
$shortcut.Description = "BYKU.PUBLIKACJE DESKTOP - panel publikacji"
$shortcut.Save()
Write-Host "Skrót gotowy: $link"
