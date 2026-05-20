Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Hide the console window that hosts this PowerShell process
Add-Type -Namespace Win32 -Name Native -MemberDefinition @"
    [DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
    [DllImport("user32.dll")]   public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
"@
[Win32.Native]::ShowWindow([Win32.Native]::GetConsoleWindow(), 0)

# --- Config ---
$historyFile = "$env:USERPROFILE\.claude_launcher_history.txt"
$maxHistory  = 10

# --- Colors ---
$bg     = [System.Drawing.Color]::FromArgb(30, 30, 30)
$fg     = [System.Drawing.Color]::FromArgb(220, 220, 220)
$accent = [System.Drawing.Color]::FromArgb(0, 120, 212)
$inputBg = [System.Drawing.Color]::FromArgb(45, 45, 45)
$inputBd = [System.Drawing.Color]::FromArgb(60, 60, 60)
$green  = [System.Drawing.Color]::FromArgb(100, 200, 100)
$red    = [System.Drawing.Color]::FromArgb(200, 100, 100)
$dim    = [System.Drawing.Color]::FromArgb(150, 150, 150)

# --- Helper ---
function New-Control($type, $props) {
    $c = New-Object $type
    foreach ($key in $props.Keys) { $c.$key = $props[$key] }
    $c
}

# --- Load History ---
$history  = @()
$lastPath = ""
if (Test-Path $historyFile) {
    $history = @(Get-Content $historyFile | Where-Object { $_ -ne "" })
    if ($history.Count -gt 0) { $lastPath = $history[0] }
}

# --- Form ---
$form = New-Object System.Windows.Forms.Form -Property @{
    Text = "Claude Launcher"; Size = New-Object System.Drawing.Size(700, 350)
    StartPosition = "CenterScreen"; BackColor = $bg; ForeColor = $fg
    FormBorderStyle = "FixedDialog"; MaximizeBox = $false
}

# --- Title ---
$form.Controls.Add((New-Control System.Windows.Forms.Label @{
    Text = "Claude Code Launcher"
    Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
    ForeColor = $fg; Size = New-Object System.Drawing.Size(660, 35)
    Location = New-Object System.Drawing.Point(20, 15)
}))

# --- Folder Row ---
$form.Controls.Add((New-Control System.Windows.Forms.Label @{
    Text = "Folder:"; Font = New-Object System.Drawing.Font("Segoe UI", 10)
    ForeColor = $fg; Size = New-Object System.Drawing.Size(60, 25)
    Location = New-Object System.Drawing.Point(20, 65)
}))

$pathBox = New-Object System.Windows.Forms.TextBox -Property @{
    Size = New-Object System.Drawing.Size(500, 25)
    Location = New-Object System.Drawing.Point(80, 63)
    BackColor = $inputBg; ForeColor = $fg; BorderStyle = "FixedSingle"
    Font = New-Object System.Drawing.Font("Segoe UI", 9)
    Text = $lastPath; ReadOnly = $true
}
$form.Controls.Add($pathBox)

$browse = New-Object System.Windows.Forms.Button -Property @{
    Text = "Browse..."; Size = New-Object System.Drawing.Size(90, 28)
    Location = New-Object System.Drawing.Point(590, 61)
    BackColor = $inputBg; ForeColor = $fg; FlatStyle = "Flat"
    Font = New-Object System.Drawing.Font("Segoe UI", 9)
}
$browse.FlatAppearance.BorderColor = $inputBd
$browse.Add_Click({
    $fb = New-Object System.Windows.Forms.FolderBrowserDialog
    $fb.Description = "Select project folder"
    if ($fb.ShowDialog() -eq "OK") { $pathBox.Text = $fb.SelectedPath }
})
$form.Controls.Add($browse)

# --- Recent Folders ---
$form.Controls.Add((New-Control System.Windows.Forms.Label @{
    Text = "Recent:"; Font = New-Object System.Drawing.Font("Segoe UI", 10)
    ForeColor = [System.Drawing.Color]::Gray; Size = New-Object System.Drawing.Size(60, 25)
    Location = New-Object System.Drawing.Point(20, 105)
}))

$recentCombo = New-Object System.Windows.Forms.ComboBox -Property @{
    Size = New-Object System.Drawing.Size(600, 25)
    Location = New-Object System.Drawing.Point(80, 103)
    BackColor = $inputBg; ForeColor = $fg; FlatStyle = "Flat"
    DropDownStyle = "DropDownList"; Font = New-Object System.Drawing.Font("Segoe UI", 9)
}
[void]$recentCombo.Items.Add("-- select a recent folder --")
foreach ($h in $history) { [void]$recentCombo.Items.Add($h) }
$recentCombo.SelectedIndex = 0
$recentCombo.Add_SelectedIndexChanged({
    if ($recentCombo.SelectedIndex -gt 0) { $pathBox.Text = $recentCombo.SelectedItem.ToString() }
})
$form.Controls.Add($recentCombo)

# --- Status ---
$status = New-Object System.Windows.Forms.Label -Property @{
    Text = "Checking prerequisites..."
    Font = New-Object System.Drawing.Font("Segoe UI", 9)
    Size = New-Object System.Drawing.Size(660, 20); Location = New-Object System.Drawing.Point(20, 150)
    ForeColor = [System.Drawing.Color]::Gray
}
$form.Controls.Add($status)

$form.Controls.Add((New-Control System.Windows.Forms.Label @{
    Text = "Opus: kimi-k2.6  |  Sonnet: glm-5.1  |  Haiku: deepseek-v4-flash"
    Font = New-Object System.Drawing.Font("Segoe UI", 8)
    Size = New-Object System.Drawing.Size(660, 20); Location = New-Object System.Drawing.Point(20, 175)
    ForeColor = $dim
}))

# --- Prerequisite Checks ---
function Test-Ollama {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:11434" -Method GET -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        $script:ollamaOk = $true; "Ollama: running"
    } catch {
        $script:ollamaOk = $false; "Ollama: not running -- start Ollama first"
    }
}
function Test-Claude {
    $script:claudeOk = $null -ne (Get-Command claude -ErrorAction SilentlyContinue)
    if ($script:claudeOk) { "claude: found" } else { "claude: not found on PATH" }
}
function Test-Proxy {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:11435/health" -Method GET -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop
        $script:proxyOk = $true; "Proxy: active"
    } catch {
        $script:proxyOk = $false; "Proxy: off"
    }
}

$status.Text = "$(Test-Ollama)  |  $(Test-Claude)  |  $(Test-Proxy)"
$status.ForeColor = if ($script:ollamaOk -and $script:claudeOk) { $green } else { $red }

# --- Launch Button ---
$launch = New-Object System.Windows.Forms.Button -Property @{
    Text = "Launch Claude"; Size = New-Object System.Drawing.Size(660, 50)
    Location = New-Object System.Drawing.Point(20, 210)
    BackColor = $accent; ForeColor = [System.Drawing.Color]::White
    FlatStyle = "Flat"; Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
}
$launch.FlatAppearance.BorderSize = 0
$launch.Add_Click({
    $path = $pathBox.Text.Trim()

    if (-not $path -or -not (Test-Path $path)) {
        [System.Windows.Forms.MessageBox]::Show("Please select a valid project folder.", "Invalid Folder", "OK", "Error")
        return
    }
    if (-not $script:ollamaOk) {
        [System.Windows.Forms.MessageBox]::Show("Ollama is not running. Start Ollama first.", "Ollama Not Running", "OK", "Error")
        return
    }
    if (-not $script:claudeOk) {
        [System.Windows.Forms.MessageBox]::Show("'claude' not found on PATH. Install Claude Code CLI and restart.", "Claude CLI Missing", "OK", "Error")
        return
    }

    # Save history (most recent first, deduplicated)
    @($path) + @($history | Where-Object { $_ -ne $path }) |
        Select-Object -First $maxHistory | Set-Content $historyFile

    # Resolve system prompt
    $systemPromptPath = Join-Path $PSScriptRoot "system_prompt.txt"
    $systemPromptArg  = ""
    if (Test-Path $systemPromptPath) {
        $systemPromptArg = " --append-system-prompt-file `"$systemPromptPath`""
    }

    # Set environment variables on current process (inherited by child)
    if ($script:proxyOk) {
        $env:ANTHROPIC_BASE_URL        = "http://localhost:11435"
    } else {
        $env:ANTHROPIC_BASE_URL        = "http://localhost:11434"
    }
    $env:ANTHROPIC_AUTH_TOKEN           = "ollama"

    # Model mapping
    $env:ANTHROPIC_DEFAULT_OPUS_MODEL   = "kimi-k2.6:cloud"
    $env:ANTHROPIC_DEFAULT_SONNET_MODEL = "glm-5.1:cloud"
    $env:ANTHROPIC_DEFAULT_HAIKU_MODEL  = "deepseek-v4-flash:cloud"

    # Display names (shown in /model picker)
    $env:ANTHROPIC_DEFAULT_OPUS_MODEL_NAME   = "Kimi K2.6 (Opus)"
    $env:ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION = "Tier A - architecture, deep debugging, hard problems"
    $env:ANTHROPIC_DEFAULT_SONNET_MODEL_NAME = "GLM-5.1 (Sonnet)"
    $env:ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION = "Mid-tier - sustained coding, refactors, daily driver"
    $env:ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME  = "DeepSeek V4 Flash (Haiku)"
    $env:ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION = "Fast and cheap - quick edits, scaffolding, summaries"

    # Capabilities (confirmed working with Ollama Cloud via API tests)
    $env:ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES   = "effort,xhigh_effort,max_effort,thinking,adaptive_thinking,interleaved_thinking"
    $env:ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES = "effort,xhigh_effort,max_effort,thinking,adaptive_thinking,interleaved_thinking"
    $env:ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES  = "effort,thinking"

    # Context
    $env:OLLAMA_NUM_CTX                 = "65536"

    # Launch Claude Code in a new PowerShell window
    Start-Process powershell.exe -ArgumentList "-NoExit","-Command","`"Set-Location '$path'; claude$systemPromptArg`""
    $form.Close()
})
$form.Controls.Add($launch)

[System.Windows.Forms.Application]::Run($form)