@echo off
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PY%" (
  "%PY%" "%~dp0session_start.py"
) else (
  py -3 "%~dp0session_start.py"
)
