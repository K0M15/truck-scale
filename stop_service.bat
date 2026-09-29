@echo off
cd /d "%~dp0"
echo Stoppe Dienst 'LandliebeWaage'...
"%~dp0LandliebeWaage.exe" stop "%~dp0LandliebeWaage.xml"
echo Dienststatus:
"%~dp0LandliebeWaage.exe" status "%~dp0LandliebeWaage.xml"
pause
