@echo off
rem Double-click to open Harshitha's Career Hub. (No brackets inside IF blocks: the file name has them.)
cd /d "%~dp0"
if "%~1"=="min" goto run
start "Career Hub - keep this window open" /min cmd /c call "%~f0" min
exit /b

:run
set PYTHONUTF8=1
set CAREERHUB_LAUNCHER=1

:loop
python career_hub.py
if "%errorlevel%"=="42" goto loop
if not "%errorlevel%"=="0" pause
