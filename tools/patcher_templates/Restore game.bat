@echo off
rem Veteran Upgrades: Patched Edition - Restore game (runs patch_game.ps1 with Windows PowerShell)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0patch_game.ps1" restore
pause
