# Start analytics proxy in background
$nodePath = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $nodePath) {
    Write-Host "Node.js is not installed. Please install Node.js first." -ForegroundColor Red
    exit 1
}

# Check if proxy is already running
try {
    $null = Invoke-WebRequest -Uri "http://localhost:11435/health" -Method GET -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop
    Write-Host "Analytics proxy is already running on http://localhost:11435" -ForegroundColor Yellow
    exit 0
} catch {}

# Start proxy in background
$process = Start-Process -FilePath "node" -ArgumentList "`"$PSScriptRoot\proxy.mjs`"" -WindowStyle Hidden -PassThru
Start-Sleep -Milliseconds 500

# Verify it started
try {
    $null = Invoke-WebRequest -Uri "http://localhost:11435/health" -Method GET -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    Write-Host "Analytics proxy started on http://localhost:11435 (PID: $($process.Id))" -ForegroundColor Green
    Write-Host "Logs will be written to $PSScriptRoot\..\logs\" -ForegroundColor Cyan
} catch {
    Write-Host "Failed to start analytics proxy. Check if Node.js is installed." -ForegroundColor Red
    exit 1
}