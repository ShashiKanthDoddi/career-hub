@echo off
rem One-time setup for Harshitha's Career Hub on Windows.
cd /d "%~dp0"
title Career Hub - Setup
echo ======================================================
echo    HARSHITHA'S CAREER HUB  -  ONE-TIME SETUP (Windows)
echo ======================================================
echo.
python --version >nul 2>&1
if errorlevel 1 goto nopython

echo Step 1 of 2: installing helper parts, 1 to 3 minutes...
python -m pip install --user --upgrade pip >nul 2>&1
python -m pip install --user playwright pyyaml pypdf
if errorlevel 1 goto failed
echo.
echo Step 2 of 2: downloading a backup browser, about 150 MB...
python -m playwright install chromium
echo.
echo ======================================================
echo    ALL SET, HARSHITHA!
echo ======================================================
echo Next: double-click "Open Career Hub (Windows)" and fill in the Profile tab.
echo.
pause
exit /b 0

:nopython
echo Python is not installed yet.
echo.
echo  1. A web page will open. Click the yellow "Download Python" button.
echo  2. Run the installer. At the bottom, TICK "Add python.exe to PATH".
echo  3. Click "Install Now" and wait.
echo  4. Then double-click this Setup file again.
echo.
start "" https://www.python.org/downloads/
pause
exit /b 1

:failed
echo Something went wrong. Check your internet and run Setup again.
pause
exit /b 1
