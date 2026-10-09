@echo off
setlocal
rem Drag a multi-room KCD .job file onto this file.
rem It makes one .job per room in a new folder next to the original.

if "%~1"=="" (
    echo Drag a KCD .job file onto this icon.
    pause
    exit /b 1
)

set /p JOBNO=Job number (for example 1080458):
if "%JOBNO%"=="" (
    echo No job number entered. Nothing was made.
    pause
    exit /b 1
)

python "%~dp0kcdsplit.py" "%~1" "%JOBNO%" "%~dp1%JOBNO% rooms"
echo.
echo The room files are in: %~dp1%JOBNO% rooms
pause
