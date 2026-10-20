@echo off
rem Job Saving Bot - start it on this computer.
rem The first run sets up its own Python environment (.venv) in this folder and
rem installs requirements.txt. A .venv copied over from another computer does
rem not work here, so it is checked every time and set up again when broken.
setlocal
cd /d "%~dp0"
set "JSB_PY=%~dp0.venv\Scripts\python.exe"
set "JSB_PYW=%~dp0.venv\Scripts\pythonw.exe"

set "JSB_CHECK=import PySide6, playwright, gspread"
if not exist "%JSB_PY%" goto setup
"%JSB_PY%" -c "%JSB_CHECK%" >nul 2>&1 && goto run
rem A working .venv that only misses a package added in an update: install it.
"%JSB_PY%" -c "import sys" >nul 2>&1 || goto broken
echo Updating Job Saving Bot's Python packages...
"%JSB_PY%" -m pip install -r requirements.txt
"%JSB_PY%" -c "%JSB_CHECK%" >nul 2>&1 && goto run
:broken
echo The Python environment in this folder is broken or incomplete - setting it up again...
rmdir /s /q ".venv"

:setup

call :find_python
if not defined BASE_PY (
  echo.
  echo Python 3.10 - 3.14 was not found on this computer.
  where winget >nul 2>&1
  if errorlevel 1 goto no_python
  choice /m "Install Python 3.13 now with winget"
  if errorlevel 2 goto no_python
  winget install -e --id Python.Python.3.13 --scope user --accept-package-agreements --accept-source-agreements
  call :find_python
  if not defined BASE_PY (
    echo Python was installed. Close this window and double-click Job Saving Bot.bat again.
    pause
    exit /b 1
  )
)

echo Setting up Job Saving Bot's Python environment - one time only, a few minutes...
%BASE_PY% -m venv .venv
if not exist "%JSB_PY%" (
  echo Could not create the .venv folder here. Is this folder read-only?
  pause
  exit /b 1
)
"%JSB_PY%" -m pip install --upgrade pip >nul 2>&1
"%JSB_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Installing the requirements failed - check the internet connection and try again.
  rmdir /s /q ".venv"
  pause
  exit /b 1
)

:run
if not exist "C:\Program Files\Google\Chrome\Application\chrome.exe" if not exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" if not exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
  echo Google Chrome is not installed. Install it from https://www.google.com/chrome/ ,
  echo or set chrome_path in %LOCALAPPDATA%\JobSavingBot\settings.json .
  pause
)
if /i "%~1"=="debug" (
  rem "Job Saving Bot.bat debug" keeps a console open with any error message
  "%JSB_PY%" app.py
  pause
  exit /b
)
start "" "%JSB_PYW%" app.py
exit /b 0

:no_python
echo Install Python 3.13 from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH"), then double-click Job Saving Bot.bat again.
pause
exit /b 1

:find_python
rem BASE_PY = the first Python 3.10-3.14 found (what PySide6 6.11 supports): the py launcher first, then python on PATH.
set "BASE_PY="
for %%V in (3.14 3.13 3.12 3.11 3.10) do (
  if not defined BASE_PY (
    py -%%V -c "import sys" >nul 2>&1 && set "BASE_PY=py -%%V"
  )
)
if not defined BASE_PY (
  python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] < (3, 15) else 1)" >nul 2>&1 && set "BASE_PY=python"
)
rem Python's own install folders: a Python installed a moment ago (winget, above) is
rem not on this window's PATH yet, and python.org's installer may never add it.
for %%V in (314 313 312 311 310) do (
  if not defined BASE_PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "BASE_PY="%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe""
  if not defined BASE_PY if exist "%ProgramFiles%\Python%%V\python.exe" set "BASE_PY="%ProgramFiles%\Python%%V\python.exe""
)
exit /b 0
