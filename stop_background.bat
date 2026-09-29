@echo off
echo Beende Hintergrund-Prozesse von Landliebe Waage...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*service_runner.py*' -or $_.CommandLine -like '*app.main*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host ('Prozess beendet: PID ' + $_.ProcessId) }"
echo Fertig.
pause
