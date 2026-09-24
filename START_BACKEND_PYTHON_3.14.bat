@echo off
cd /d "%~dp0backend"
if not exist venv\Scripts\python.exe (
  echo Virtual environment not found.
  echo Run SETUP_PYTHON_3.14_WINDOWS.bat first.
  pause
  exit /b 1
)
call venv\Scripts\activate.bat
python -m uvicorn app.main:app --reload --port 8000
pause
