@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv || (echo Install Python 3.11+ from python.org first & pause & exit /b 1)
)
call .venv\Scripts\activate
python -m pip install -q -r requirements.txt
python -m bluey
pause
