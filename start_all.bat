@echo off
set "SCRIPT_DIR=%~dp0"
:: Scan AppData first, then Program Files
for /f "delims=" %%i in ('dir /b /ad /on "%USERPROFILE%\AppData\Roaming\Tencent\Marvis\MarvisAgent\*" 2^>nul ^| findstr "^[0-9]" ^| sort /r') do set "PY_DIR=%USERPROFILE%\AppData\Roaming\Tencent\Marvis\MarvisAgent\%%i" & goto :found_py
for /f "delims=" %%i in ('dir /b /ad /on "%ProgramFiles%\Tencent\Marvis\MarvisAgent\*" 2^>nul ^| findstr "^[0-9]" ^| sort /r') do set "PY_DIR=%ProgramFiles%\Tencent\Marvis\MarvisAgent\%%i" & goto :found_py
echo Python runtime not found in AppData or ProgramFiles
pause
exit /b 1
:found_py
set "PYTHON=%PY_DIR%\runtime\python311\python.exe"
"%PYTHON%" -m pip install flask psutil pywin32 pillow -q 2>nul
start "" /B "%PYTHON%" "%SCRIPT_DIR%collector.py"
timeout /t 1 /nobreak >nul
start "" /B "%PYTHON%" "%SCRIPT_DIR%server.py"
start "" /B "%PYTHON%" "%SCRIPT_DIR%float_ball.py"
