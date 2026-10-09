@echo off
setlocal
rem Builds "KCD ROOM SPLITTER.exe" into the dist folder next to this file.
rem Needs Python 3 on this computer and internet the first time (to get PyInstaller).
rem The finished .exe runs on computers without Python.

set BUILD=%TEMP%\kcdbuild
set VENV=%BUILD%\venv
if not exist "%VENV%\Scripts\python.exe" python -m venv "%VENV%" || goto :fail
"%VENV%\Scripts\python" -m pip install -q --disable-pip-version-check pyinstaller==6.11.1 || goto :fail
"%VENV%\Scripts\python" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "KCD ROOM SPLITTER" --distpath "%~dp0dist" --workpath "%BUILD%\work" ^
    --specpath "%BUILD%\work" --paths "%~dp0." "%~dp0kcd_room_splitter.py" || goto :fail
echo.
echo Built: %~dp0dist\KCD ROOM SPLITTER.exe
pause
exit /b 0

:fail
echo.
echo The build did not finish. See the messages above.
pause
exit /b 1
