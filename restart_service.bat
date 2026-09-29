@echo off
cd /d "%~dp0"
echo Starte Dienst 'LandliebeWaage' neu...
"%~dp0LandliebeWaage.exe" restart "%~dp0LandliebeWaage.xml"
echo Dienststatus:
"%~dp0LandliebeWaage.exe" status "%~dp0LandliebeWaage.xml"
pause
