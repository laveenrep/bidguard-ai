@echo off
setlocal
cd /d "%~dp0backend"
echo ================================================
echo BidGuard AI 4.0 - Python 3.14 Setup
echo ================================================
py -3.14 --version
if errorlevel 1 (
  echo.
  echo ERROR: Python 3.14 was not found with the Python launcher.
  echo Install Python 3.14.x and try again.
  pause
  exit /b 1
)
if exist venv rmdir /s /q venv
py -3.14 -m venv venv
if errorlevel 1 goto :fail
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
echo.
echo Backend setup completed successfully.
echo Start it with: START_BACKEND_PYTHON_3.14.bat
pause
exit /b 0
:fail
echo.
echo SETUP FAILED. Read the error above.
pause
exit /b 1
