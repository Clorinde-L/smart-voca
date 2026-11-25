@echo off
rem 2026-11-11 - smart-voca - Launch Smart Voca by double-click
rem 2026-11-25 - Web version: starts a local server and opens the browser (ADR-18)
rem File: (project root) .bat launcher
rem NOTE: keep this file ASCII-only. cmd.exe reads .bat files in the system code page,
rem       so UTF-8 Korean text here breaks parsing ("was unexpected at this time").
rem NOTE: uses python.exe (not pythonw) so a console window stays open while the server runs.
rem       Closing that window stops the server.
cd /d "%~dp0"
title Smart Voca server
if not exist ".venv\Scripts\python.exe" goto :no_venv
rem PYTHONIOENCODING keeps Korean messages readable in the console.
set PYTHONIOENCODING=utf-8
chcp 65001 >nul
".venv\Scripts\python.exe" -m smartvoca
if errorlevel 1 pause
exit /b 0

:no_venv
echo [Smart Voca] The virtual environment (.venv) was not found.
echo Please follow the "Install" steps in README.md first.
pause
exit /b 1
