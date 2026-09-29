# Autostart Verwaltung fuer Landliebe Waage (Benutzer-Ebene, keine Admin-Rechte erforderlich)
param(
    [ValidateSet("enable", "disable", "status")]
    [string]$Action = "status"
)

$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$entryName = "LandliebeWaage"
$targetScript = "wscript.exe `"$PSScriptRoot\start_background.vbs`""

switch ($Action) {
    "enable" {
        Set-ItemProperty -Path $runKey -Name $entryName -Value $targetScript
        Write-Host "[OK] Autostart bei Benutzer-Anmeldung wurde aktiviert." -ForegroundColor Green
        Write-Host "     Befehl: $targetScript"
    }
    "disable" {
        Remove-ItemProperty -Path $runKey -Name $entryName -ErrorAction SilentlyContinue
        Write-Host "[OK] Autostart wurde deaktiviert." -ForegroundColor Yellow
    }
    "status" {
        $val = (Get-ItemProperty -Path $runKey -Name $entryName -ErrorAction SilentlyContinue).$entryName
        if ($val) {
            Write-Host "[STATUS] Autostart ist AKTIVIERT:" -ForegroundColor Green
            Write-Host "         $val"
        } else {
            Write-Host "[STATUS] Autostart ist DEAKTIVIERT." -ForegroundColor Yellow
        }
    }
}
