@echo off
chcp 65001 >nul
title Dashboard de Subvenciones - Trivium (MORIARTY)
cd /d "%~dp0"
echo ========================================================
echo   Iniciando Dashboard Automatizado de Subvenciones...
echo   Se abrira automaticamente en http://localhost:8501
echo ========================================================
.\.venv\Scripts\streamlit.exe run src/visualization/app.py
pause
