@echo off
rem Veteran Upgrades: Patched Edition - Patch status (runs patch_game.ps1 with Windows PowerShell)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0patch_game.ps1" status
pause
