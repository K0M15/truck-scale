' Startet den Landliebe-Waage Server unsichtbar im Hintergrund mit automatischem Neustart bei Absturz
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\truck-scale"
WshShell.Run """C:\truck-scale\.venv\Scripts\python.exe"" ""C:\truck-scale\service_runner.py""", 0, False
