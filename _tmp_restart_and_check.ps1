$ErrorActionPreference = "Continue"

# Kill old uvicorn on 8000 if still up
$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
  Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 2
}

$cwd = "G:\Meu Drive\BASE ANTIGRAVITY\apps\api"
$py = "C:\Users\User\AppData\Local\Programs\Python\Python311\python.exe"
Start-Process -FilePath $py -ArgumentList "-m","uvicorn","src.main:app","--host","127.0.0.1","--port","8000","--log-level","warning" -WorkingDirectory $cwd -WindowStyle Hidden
Start-Sleep -Seconds 6

try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/app" -UseBasicParsing -TimeoutSec 30
  Write-Output ("STATUS=" + $r.StatusCode)
  Write-Output ("HAS_FILTER_FN=" + ($r.Content.Contains("filterByChannel")))
  Write-Output ("HAS_CHIP_ALL=" + ($r.Content.Contains("filterByChannel('All')")))
} catch {
  Write-Output ("ERR: " + $_.Exception.Message)
}

Set-Location "G:\Meu Drive\BASE ANTIGRAVITY"
Remove-Item -Force "_tmp_verify_chips.py" -ErrorAction SilentlyContinue
git add -- "apps/api/src/presentation/routers/web_ui.py"
git status -sb
git diff --cached --stat
git log -3 --oneline
