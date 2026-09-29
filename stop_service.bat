@echo off
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

echo Stoppe Dienst 'LandliebeWaage'...
"%~dp0LandliebeWaage.exe" stop "%~dp0LandliebeWaage.xml"
echo.
echo Dienststatus:
"%~dp0LandliebeWaage.exe" status "%~dp0LandliebeWaage.xml"
echo.
pause
