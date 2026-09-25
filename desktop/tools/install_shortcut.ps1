# Tworzy skrót "BYKU.PUBLIKACJE DESKTOP" na pulpicie (uruchamia start.cmd z ikoną aplikacji).
# Użycie: powershell -ExecutionPolicy Bypass -File tools\install_shortcut.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath("Desktop")
$link = Join-Path $desktop "BYKU.PUBLIKACJE DESKTOP.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = Join-Path $root "start.cmd"
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = (Join-Path $root "assets\byku-publikacje.ico") + ",0"
$shortcut.WindowStyle = 7
$shortcut.Description = "BYKU.PUBLIKACJE DESKTOP - panel publikacji"
$shortcut.Save()
Write-Host "Skrót gotowy: $link"
