@echo off
chcp 65001 > nul
title ViddRop Studio Pro - Serveur Web
color 0C

echo ============================================================
echo   ⚡ VIDDROP STUDIO PRO - SERVEUR WEB
echo ============================================================
echo.
echo   Demarrage du serveur local sur le port 8000...
echo   Le site sera accessible sur :
echo   - Ce PC       : http://localhost:8000
echo   - Autres PCs  : http://[VOTRE-IP-LOCALE]:8000
echo.
echo ============================================================

cd /d "%~dp0"

:: Ouvrir automatiquement le navigateur apres 2 secondes
start "" "http://localhost:8000"

python server.py

pause
