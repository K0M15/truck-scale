@echo off
cd /d "%~dp0"
echo Starte Dienst 'LandliebeWaage'...
"%~dp0LandliebeWaage.exe" start "%~dp0LandliebeWaage.xml"
echo Dienststatus:
"%~dp0LandliebeWaage.exe" status "%~dp0LandliebeWaage.xml"
pause
