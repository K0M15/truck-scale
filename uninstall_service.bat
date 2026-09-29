@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   Landliebe Waage - Windows Dienst Deinstallation
echo ========================================================
echo.

:: Check for Administrator privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Administratorrechte erforderlich. UAC-Abfrage wird gestartet...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

echo Stoppe Dienst...
"%~dp0LandliebeWaage.exe" stop "%~dp0LandliebeWaage.xml"

echo Deinstalliere Dienst...
"%~dp0LandliebeWaage.exe" uninstall "%~dp0LandliebeWaage.xml"

echo.
echo Dienst wurde erfolgreich entfernt.
pause
