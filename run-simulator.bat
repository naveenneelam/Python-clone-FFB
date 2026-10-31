@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m pyffb gui --simulate
) else (
  python -m pyffb gui --simulate
)
