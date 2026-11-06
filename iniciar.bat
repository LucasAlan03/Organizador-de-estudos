@echo off
rem Inicia o Organizador MMA em http://127.0.0.1:8765
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente nao encontrado. Rode: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)
rem abre o navegador 3 segundos depois, quando o servidor ja subiu
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8765"
".venv\Scripts\python.exe" -m app
pause
