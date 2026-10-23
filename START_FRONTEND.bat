@echo off
cd /d "%~dp0frontend"
if not exist node_modules (
  echo Installing frontend dependencies...
  npm install
  if errorlevel 1 goto :fail
)
npm run dev
pause
exit /b 0
:fail
echo Frontend installation failed.
pause
exit /b 1
