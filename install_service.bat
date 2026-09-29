@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   Landliebe Waage - Windows Dienst Installation
echo ========================================================
echo.

:: Check for Administrator privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Administratorrechte erforderlich. UAC-Abfrage wird gestartet...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

echo [1/3] Pruefe WinSW Wrapper (LandliebeWaage.exe)...
if not exist "%~dp0LandliebeWaage.exe" (
    echo [FEHLER] LandliebeWaage.exe nicht gefunden!
    pause
    exit /b 1
)

echo [2/3] Registriere Windows-Dienst 'LandliebeWaage'...
"%~dp0LandliebeWaage.exe" install "%~dp0LandliebeWaage.xml"
if %errorlevel% neq 0 (
    echo [HINWEIS] Falls der Dienst bereits existiert, wird er aktualisiert.
    "%~dp0LandliebeWaage.exe" refresh "%~dp0LandliebeWaage.xml"
)

echo.
echo [3/3] Starte Windows-Dienst 'LandliebeWaage'...
"%~dp0LandliebeWaage.exe" start "%~dp0LandliebeWaage.xml"

echo.
echo ========================================================
echo   Dienststatus:
"%~dp0LandliebeWaage.exe" status "%~dp0LandliebeWaage.xml"
echo ========================================================
echo.
echo Fertig! Web-Oberflaeche erreichbar unter: http://localhost:8080
echo.
pause
