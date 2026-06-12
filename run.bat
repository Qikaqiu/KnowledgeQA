@echo off
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
