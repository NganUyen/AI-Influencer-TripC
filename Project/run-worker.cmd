@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "BACKEND_DIR=%SCRIPT_DIR%python_services"
set "BACKEND_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"

if not exist "%BACKEND_PYTHON%" (
  echo Backend venv not found at "%BACKEND_PYTHON%".
  echo Create it first with:
  echo   cd /d "%BACKEND_DIR%"
  echo   C:\Users\boizb\AppData\Local\Programs\Python\Python311\python.exe -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)

if not defined DEBUG (
  set "DEBUG=true"
)

pushd "%BACKEND_DIR%"
"%BACKEND_PYTHON%" worker.py
set "EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %EXIT_CODE%
