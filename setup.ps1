#requires -Version 5.1
# Setup script for Smart Router

$venvPath = Join-Path $PSScriptRoot ".venv"

$pythonCmd = "python"
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
} elseif (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python 3.10+ is required. Install Python and try again." -ForegroundColor Red
    exit 1
}

# Check Python version
$pyVersion = & $pythonCmd --version 2>&1
Write-Host "Found: $pyVersion" -ForegroundColor Cyan

# Create venv
if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    & $pythonCmd -m venv $venvPath
} else {
    Write-Host "Virtual environment already exists." -ForegroundColor Green
}

# Install deps
$pipExe = Join-Path $venvPath "Scripts\pip.exe"
Write-Host "Installing dependencies..." -ForegroundColor Cyan
& $pipExe install --upgrade pip
& $pipExe install -r (Join-Path $PSScriptRoot "requirements.txt")

# Verify
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
Write-Host "Verifying installation..." -ForegroundColor Cyan
& $pythonExe -c "import litellm, yaml; print('LiteLLM:', litellm.__version__)"

# Run tests
Write-Host "Running tests..." -ForegroundColor Cyan
& $pythonExe (Join-Path $PSScriptRoot "test_router.py")

Write-Host "`nSetup complete. You can now launch Claude Code via 'Claude Launcher.bat'." -ForegroundColor Green
