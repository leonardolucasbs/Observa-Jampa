@echo off
set PYTHONUTF8=1
cd /d "%~dp0.."
if not exist logs mkdir logs
"%USERPROFILE%\.local\bin\uv.exe" run --no-sync python -m pages.poluentes.collect >> logs\coleta_poluentes.log 2>&1
