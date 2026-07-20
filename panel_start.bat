@echo off
set "SCRIPT_DIR=%~dp0"
for /f "delims=" %%i in ('dir /b /ad /on "%USERPROFILE%\AppData\Roaming\Tencent\Marvis\MarvisAgent\*" 2^>nul ^| findstr "^[0-9]" ^| sort /r') do set "PY_DIR=%USERPROFILE%\AppData\Roaming\Tencent\Marvis\MarvisAgent\%%i" & goto :found_py
for /f "delims=" %%i in ('dir /b /ad /on "%ProgramFiles%\Tencent\Marvis\MarvisAgent\*" 2^>nul ^| findstr "^[0-9]" ^| sort /r') do set "PY_DIR=%ProgramFiles%\Tencent\Marvis\MarvisAgent\%%i" & goto :found_py
echo Python runtime not found
pause
exit /b 1
:found_py
set "PYTHON=%PY_DIR%\runtime\python311\python.exe"
start "" /B "%PYTHON%" "%SCRIPT_DIR%server.py"
start "" /B "%PYTHON%" "%SCRIPT_DIR%float_ball.py"
