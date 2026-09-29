@echo off
cd /d "%~dp0"
echo ========================================================
echo   Dienststatus 'LandliebeWaage':
"%~dp0LandliebeWaage.exe" status "%~dp0LandliebeWaage.xml"
echo ========================================================
pause
