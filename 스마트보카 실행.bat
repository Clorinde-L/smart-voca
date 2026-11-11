@echo off
rem 2026-11-11 - smart-voca - Launch Smart Voca by double-click (no console window)
rem File: (project root) .bat launcher
rem NOTE: keep this file ASCII-only. cmd.exe reads .bat files in the system code page,
rem       so UTF-8 Korean text here breaks parsing ("was unexpected at this time").
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" goto :no_venv
rem pythonw runs Python without a console window; "start" lets this window close right away.
start "" ".venv\Scripts\pythonw.exe" -m smartvoca
exit /b 0

:no_venv
echo [Smart Voca] The virtual environment (.venv) was not found.
echo Please follow the "Install" steps in README.md first.
pause
exit /b 1
