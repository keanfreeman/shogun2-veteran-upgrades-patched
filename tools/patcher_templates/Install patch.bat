@echo off
rem Veteran Upgrades: Patched Edition - Install patch (runs patch_game.ps1 with Windows PowerShell)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0patch_game.ps1" install
pause
