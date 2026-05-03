@echo off
start /min python "%~dp0bridge.py"
timeout /t 3 /nobreak >nul
start "" "%~dp0index.html"
