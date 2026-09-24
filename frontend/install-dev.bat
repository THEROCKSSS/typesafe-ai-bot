@echo off
cd /d "%~dp0"
call npm install --save-dev vite @vitejs/plugin-react --no-fund --no-audit --loglevel=error
echo EXIT_CODE=%ERRORLEVEL%
