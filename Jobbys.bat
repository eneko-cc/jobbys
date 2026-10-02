@echo off
title Jobbys
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 start.py
  goto end
)
python --version >nul 2>nul
if %errorlevel%==0 (
  python start.py
  goto end
)
echo [Jobbys] Python n'est pas installe. Installation en cours...
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
echo [Jobbys] Python est installe. Ferme cette fenetre et double-clique a nouveau sur Jobbys.
:end
pause
