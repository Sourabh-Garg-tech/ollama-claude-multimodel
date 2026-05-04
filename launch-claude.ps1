#requires -Version 5.1
param(
    [string]$StartPath = "",
    [string]$Model = "",
    [string]$ModelLabel = ""
)

if ($StartPath -and (Test-Path $StartPath)) {
    Set-Location -LiteralPath $StartPath
}

if (-not $Model) {
    Write-Host "[ERROR] No model specified. Use -Model <model-name>." -ForegroundColor Red
    exit 1
}

Write-Host "Starting Pipeline + Claude Code with $Model ($ModelLabel)..." -ForegroundColor Cyan

# --- Config ---
$proxyPort = 4000
$proxyUrl = "http://localhost:$proxyPort"
$proxyConfig = Join-Path $PSScriptRoot "proxy_config.yaml"
$routerDir = Join-Path $PSScriptRoot "router"
$venvPath = Join-Path $PSScriptRoot ".venv"

# --- Check Python / Virtual Env ---
$pythonCmd = "python"
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
} elseif (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python is required. Install Python 3.10+ and try again." -ForegroundColor Red
    exit 1
}

# --- Create venv if missing ---
if (-not (Test-Path $venvPath)) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    & $pythonCmd -m venv $venvPath
}

$pipExe = Join-Path $venvPath "Scripts\pip.exe"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

# --- Install deps if needed ---
if (-not (Test-Path (Join-Path $venvPath "Scripts\litellm.exe"))) {
    Write-Host "Installing LiteLLM proxy + dependencies..." -ForegroundColor Yellow
    & $pipExe install -r (Join-Path $PSScriptRoot "requirements.txt")
}

# --- Pre-flight: Ollama ---
function Test-OllamaRunning {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:11434" -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        return $true
    } catch { return $false }
}

function Test-ModelAvailable {
    param([string]$ModelName)
    try {
        $body = @{ name = $ModelName } | ConvertTo-Json -Compress
        $null = Invoke-WebRequest -Uri "http://localhost:11434/api/show" -Method POST -Body $body -TimeoutSec 15 -UseBasicParsing -ErrorAction Stop
        return $true
    } catch { return $false }
}

if (-not (Test-OllamaRunning)) {
    Write-Host "[ERROR] Ollama is not running. Start Ollama first." -ForegroundColor Red; exit 1
}
if (-not (Test-ModelAvailable -ModelName $Model)) {
    Write-Host "[ERROR] Model '$Model' is not available." -ForegroundColor Red; exit 1
}
if (-not (Get-Command "claude" -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] 'claude' CLI not found on PATH." -ForegroundColor Red; exit 1
}

# --- Start LiteLLM Proxy ---
Write-Host "Starting LiteLLM proxy on $proxyUrl ..." -ForegroundColor Cyan

$proxyLogOut = Join-Path $PSScriptRoot "logs\proxy-out.log"
$proxyLogErr = Join-Path $PSScriptRoot "logs\proxy-err.log"
$null = New-Item -ItemType Directory -Path (Split-Path $proxyLogOut) -Force -ErrorAction SilentlyContinue

$env:PYTHONPATH = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"

$litellmExe = Join-Path $venvPath "Scripts\litellm.exe"

$proxyJob = Start-Process -FilePath $litellmExe -ArgumentList @(
    "--config", $proxyConfig,
    "--port", $proxyPort,
    "--host", "127.0.0.1"
) -WorkingDirectory $PSScriptRoot -RedirectStandardOutput $proxyLogOut -RedirectStandardError $proxyLogErr -WindowStyle Hidden -PassThru

# Wait for proxy to be ready
$maxWait = 60
$waited = 0
while ($waited -lt $maxWait) {
    try {
        $null = Invoke-WebRequest -Uri "$proxyUrl/health/liveliness" -Method GET -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop
        Write-Host "Proxy is ready." -ForegroundColor Green
        break
    } catch {
        Start-Sleep -Seconds 1
        $waited++
    }
}

if ($waited -ge $maxWait) {
    Write-Host "[WARNING] Proxy did not become ready within $maxWait seconds. Check logs/proxy.log" -ForegroundColor Yellow
}

# --- Usage Logging ---
$logDir = Join-Path (Get-Location) "logs"
if (-not (Test-Path $logDir)) { $null = New-Item -ItemType Directory -Path $logDir -Force }
$logFile = Join-Path $logDir "usage.csv"
if (-not (Test-Path $logFile)) { Set-Content -Path $logFile -Value "Timestamp,Model,Label" -Encoding UTF8 }
$timestamp = (Get-Date).ToUniversalTime().ToString("o")
Add-Content -Path $logFile -Value "$timestamp,$Model,$ModelLabel" -Encoding UTF8

# --- Point Claude at the Proxy ---
$env:ANTHROPIC_BASE_URL = $proxyUrl
$env:ANTHROPIC_AUTH_TOKEN = "sk-smart-router"
$env:ANTHROPIC_API_KEY = "sk-smart-router"
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"

# Keep Ollama models warm
$env:OLLAMA_KEEP_ALIVE = "30m"
$env:OLLAMA_NUM_CTX = "65536"

# --- System Prompt ---
$prompt = @"
You are Claude, operating as a software engineering assistant.

Rules:
- Route all tasks through the Plan->Execute->Validate->Escalate pipeline.
- Invoke all installed skills and plugins automatically whenever they apply.
- Prefer minimal, concise output. Only change what is necessary. Stop when the task is complete.
"@

# --- Launch Claude ---
claude --model $Model --append-system-prompt $prompt

# --- Cleanup: stop proxy on exit ---
if ($proxyJob -and -not $proxyJob.HasExited) {
    Stop-Process -Id $proxyJob.Id -Force -ErrorAction SilentlyContinue
}
