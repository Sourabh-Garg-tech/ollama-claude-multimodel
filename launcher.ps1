Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

# --- Config ---
$scriptPath = Join-Path $PSScriptRoot "launch-claude.ps1"
$modelsPath = Join-Path $PSScriptRoot "models.json"
$historyFile = "$env:USERPROFILE\.claude_mm_history.txt"
$maxHistory = 10

# --- Load Models ---
if (-not (Test-Path $modelsPath)) {
    [System.Windows.Forms.MessageBox]::Show("models.json not found", "Error")
    exit 1
}
$roles = (Get-Content $modelsPath -Raw | ConvertFrom-Json).roles

# --- Load History ---
$history = @()
if (Test-Path $historyFile) {
    $history = @(Get-Content $historyFile | Where-Object { $_ -ne "" })
}
$lastPath = if ($history.Count -gt 0) { $history[0] } else { "" }

# --- Pre-flight checks ---
function Test-Ollama {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:11434" -Method GET -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        return $true
    } catch { return $false }
}

function Test-Proxy {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:4000/health/liveliness" -Method GET -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        return $true
    } catch { return $false }
}

# --- Routing preview logic ---
$planningKeywords = @("architecture", "design", "strategy", "plan", "roadmap", "structure", "organize", "approach", "blueprint", "system design", "refactor the", "rewrite the", "migrate from")
$complexKeywords = @("analyze", "compare", "evaluate", "assess", "deep dive")

function Get-Route {
    param([string]$Message)
    if (-not $Message) { return "executor" }
    $len = $Message.Length
    if ($len -lt 200 -and $Message.Trim().EndsWith("?")) { return "validator" }
    $lower = $Message.ToLower()
    foreach ($kw in $planningKeywords) { if ($lower.Contains($kw)) { return "planner" } }
    if ($Message -match '\.py\b|\.js\b|\.ts\b|\.go\b|\.rs\b|\.java\b') { return "coder" }
    if ($Message -match '\bfix\b|\bdebug\b|\bimplement\b|\bbuild\b|\bcompile\b') { return "coder" }
    if ($Message -match '\berror\b|\bbug\b|\bfunction\b|\bclass\b|\bmethod\b') { return "coder" }
    if ($Message -match '```') { return "coder" }
    if ($len -ge 2000) {
        foreach ($kw in $complexKeywords) { if ($lower.Contains($kw)) { return "planner" } }
    }
    return "executor"
}

$routeLabels = @{
    planner   = "V4 Pro (Deep Reasoning)"
    executor  = 'V4 Flash (Fast + Cheap)'
    coder     = "Kimi K2.6 (Best Coding)"
    validator = "GLM-5.1 (Quick Lookups)"
}

# --- Colors ---
$bgColor       = [System.Drawing.Color]::FromArgb(24, 24, 27)
$cardColor     = [System.Drawing.Color]::FromArgb(38, 38, 42)
$cardHover     = [System.Drawing.Color]::FromArgb(48, 48, 54)
$autoSelect    = [System.Drawing.Color]::FromArgb(6, 78, 59)
$manualSelect  = [System.Drawing.Color]::FromArgb(12, 90, 110)
$textColor     = [System.Drawing.Color]::White
$dimColor      = [System.Drawing.Color]::FromArgb(160, 160, 170)
$accentColor   = [System.Drawing.Color]::FromArgb(56, 189, 248)
$greenColor    = [System.Drawing.Color]::FromArgb(74, 222, 128)
$redColor      = [System.Drawing.Color]::FromArgb(248, 113, 113)
$yellowColor   = [System.Drawing.Color]::FromArgb(250, 204, 21)
$borderColor   = [System.Drawing.Color]::FromArgb(58, 58, 62)
$inputBgColor  = [System.Drawing.Color]::FromArgb(30, 30, 34)
$btnColor      = [System.Drawing.Color]::FromArgb(56, 189, 248)

# --- Form ---
$form = New-Object System.Windows.Forms.Form
$form.Text = "Multi-Model Router"
$form.Size = New-Object System.Drawing.Size(580, 620)
$form.StartPosition = "CenterScreen"
$form.TopMost = $true
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.BackColor = $bgColor
$form.ForeColor = $textColor

$y = 0

# --- Title bar ---
$titlePanel = New-Object System.Windows.Forms.Panel
$titlePanel.Size = New-Object System.Drawing.Size(580, 50)
$titlePanel.Location = New-Object System.Drawing.Point(0, 0)
$titlePanel.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 34)
$null = $form.Controls.Add($titlePanel)

$titleLbl = New-Object System.Windows.Forms.Label
$titleLbl.Text = "  Multi-Model Router"
$titleLbl.Location = New-Object System.Drawing.Point(8, 12)
$titleLbl.Size = New-Object System.Drawing.Size(350, 26)
$titleLbl.Font = New-Object System.Drawing.Font("Segoe UI", 13, [System.Drawing.FontStyle]::Bold)
$titleLbl.ForeColor = $textColor
$null = $titlePanel.Controls.Add($titleLbl)

$titleSub = New-Object System.Windows.Forms.Label
$titleSub.Text = "Auto-switch: best model per request"
$titleSub.Location = New-Object System.Drawing.Point(300, 18)
$titleSub.Size = New-Object System.Drawing.Size(260, 20)
$titleSub.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$titleSub.ForeColor = $dimColor
$titleSub.TextAlign = [System.Drawing.ContentAlignment]::TopRight
$null = $titlePanel.Controls.Add($titleSub)

$y = 58

# --- Project Folder ---
$folderLbl = New-Object System.Windows.Forms.Label
$folderLbl.Text = "Project Folder"
$folderLbl.Location = New-Object System.Drawing.Point(20, $y)
$folderLbl.Size = New-Object System.Drawing.Size(120, 18)
$folderLbl.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$folderLbl.ForeColor = $dimColor
$null = $form.Controls.Add($folderLbl)

$folderCombo = New-Object System.Windows.Forms.ComboBox
$folderCombo.Size = New-Object System.Drawing.Size(440, 28)
$folderCombo.Location = New-Object System.Drawing.Point(20, ($y + 20))
$folderCombo.DropDownStyle = "DropDown"
$folderCombo.Items.AddRange($history)
$folderCombo.Text = $lastPath
$folderCombo.BackColor = $inputBgColor
$folderCombo.ForeColor = $textColor
$folderCombo.Font = New-Object System.Drawing.Font("Consolas", 9)
$null = $form.Controls.Add($folderCombo)

$browseBtn = New-Object System.Windows.Forms.Button
$browseBtn.Text = "..."
$browseBtn.Location = New-Object System.Drawing.Point(470, ($y + 18))
$browseBtn.Size = New-Object System.Drawing.Size(80, 30)
$browseBtn.FlatStyle = "Flat"
$browseBtn.BackColor = $cardColor
$browseBtn.ForeColor = $textColor
$browseBtn.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$browseBtn.FlatAppearance.BorderColor = $borderColor
$browseBtn.Cursor = [System.Windows.Forms.Cursors]::Hand
$browseBtn.Add_Click({
    $fb = New-Object System.Windows.Forms.FolderBrowserDialog
    if ($fb.ShowDialog() -eq "OK") { $folderCombo.Text = $fb.SelectedPath }
})
$null = $form.Controls.Add($browseBtn)

$y += 56

# --- Separator ---
$sep1 = New-Object System.Windows.Forms.Panel
$sep1.Size = New-Object System.Drawing.Size(540, 1)
$sep1.Location = New-Object System.Drawing.Point(20, $y)
$sep1.BackColor = $borderColor
$null = $form.Controls.Add($sep1)

$y += 8

# --- Status indicators ---
$statusPanel = New-Object System.Windows.Forms.Panel
$statusPanel.Size = New-Object System.Drawing.Size(540, 24)
$statusPanel.Location = New-Object System.Drawing.Point(20, $y)
$statusPanel.BackColor = [System.Drawing.Color]::Transparent
$null = $form.Controls.Add($statusPanel)

$ollamaStatus = New-Object System.Windows.Forms.Label
$ollamaStatus.Location = New-Object System.Drawing.Point(0, 2)
$ollamaStatus.AutoSize = $true
$ollamaStatus.Font = New-Object System.Drawing.Font("Consolas", 9)
$null = $statusPanel.Controls.Add($ollamaStatus)

$proxyStatus = New-Object System.Windows.Forms.Label
$proxyStatus.Location = New-Object System.Drawing.Point(200, 2)
$proxyStatus.AutoSize = $true
$proxyStatus.Font = New-Object System.Drawing.Font("Consolas", 9)
$null = $statusPanel.Controls.Add($proxyStatus)

# Run checks
$ollamaOk = Test-Ollama
$proxyOk = Test-Proxy

if ($ollamaOk) { $ollamaStatus.Text = "Ollama: Running"; $ollamaStatus.ForeColor = $greenColor }
else { $ollamaStatus.Text = "Ollama: Down"; $ollamaStatus.ForeColor = $redColor }

if ($proxyOk) { $proxyStatus.Text = "Proxy: Ready"; $proxyStatus.ForeColor = $greenColor }
else { $proxyStatus.Text = "Proxy: Off"; $proxyStatus.ForeColor = $yellowColor }

$y += 32

# --- Separator ---
$sep2 = New-Object System.Windows.Forms.Panel
$sep2.Size = New-Object System.Drawing.Size(540, 1)
$sep2.Location = New-Object System.Drawing.Point(20, $y)
$sep2.BackColor = $borderColor
$null = $form.Controls.Add($sep2)

$y += 10

# --- Role Cards ---
$roleCards = @{}
$selectedRole = "auto"
$cardW = 257
$cardH = 68
$cardGap = 6

foreach ($r in $roles) {
    $card = New-Object System.Windows.Forms.Panel
    $card.Tag = $r.role
    $card.BackColor = $cardColor

    if ($r.role -eq "auto") {
        $card.Size = New-Object System.Drawing.Size(540, $cardH)
    } else {
        $card.Size = New-Object System.Drawing.Size($cardW, $cardH)
    }

    $lbl = New-Object System.Windows.Forms.Label
    $lbl.Text = "$($r.label.ToUpper())"
    $lbl.Location = New-Object System.Drawing.Point(12, 8)
    $lbl.Size = New-Object System.Drawing.Size(80, 18)
    $lbl.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Bold)
    $lbl.ForeColor = $accentColor
    $lbl.Tag = "label"
    $null = $card.Controls.Add($lbl)

    $tag = New-Object System.Windows.Forms.Label
    $tag.Text = $r.tag
    $tag.Location = New-Object System.Drawing.Point(95, 8)
    $tag.Size = New-Object System.Drawing.Size(140, 18)
    $tag.Font = New-Object System.Drawing.Font("Consolas", 8)
    $tag.ForeColor = $dimColor
    $tag.Tag = "tag"
    $null = $card.Controls.Add($tag)

    $desc = New-Object System.Windows.Forms.Label
    $desc.Text = $r.description
    $desc.Location = New-Object System.Drawing.Point(12, 28)
    if ($r.role -eq "auto") {
        $desc.Size = New-Object System.Drawing.Size(510, 20)
    } else {
        $desc.Size = New-Object System.Drawing.Size(230, 20)
    }
    $desc.Font = New-Object System.Drawing.Font("Segoe UI", 8)
    $desc.ForeColor = $dimColor
    $desc.Tag = "desc"
    $null = $card.Controls.Add($desc)

    if ($r.role -eq "auto") {
        $meta = New-Object System.Windows.Forms.Label
        $meta.Text = "questions -> GLM  |  code -> Kimi  |  planning -> V4 Pro  |  else -> V4 Flash"
        $meta.Location = New-Object System.Drawing.Point(12, 48)
        $meta.Size = New-Object System.Drawing.Size(510, 16)
        $meta.Font = New-Object System.Drawing.Font("Consolas", 7.5)
        $meta.ForeColor = $greenColor
        $null = $card.Controls.Add($meta)
    } else {
        $meta = New-Object System.Windows.Forms.Label
        $costVal = $r.cost
        $speedVal = $r.speed
        $meta.Text = "$costVal  |  $speedVal tok/s"
        $meta.Location = New-Object System.Drawing.Point(12, 48)
        $meta.Size = New-Object System.Drawing.Size(230, 16)
        $meta.Font = New-Object System.Drawing.Font("Consolas", 7.5)
        $meta.ForeColor = $greenColor
        $null = $card.Controls.Add($meta)
    }

    # Click handler
    $card.Add_Click({
        $script:selectedRole = $this.Tag
        foreach ($c in $roleCards.Values) {
            $c.BackColor = $cardColor
        }
        if ($this.Tag -eq "auto") { $this.BackColor = $autoSelect }
        else { $this.BackColor = $manualSelect }
    }.GetNewClosure())

    # Hover effects
    $card.Add_MouseEnter({
        if ($script:selectedRole -ne $this.Tag) { $this.BackColor = $cardHover }
    }.GetNewClosure())
    $card.Add_MouseLeave({
        if ($script:selectedRole -ne $this.Tag) { $this.BackColor = $cardColor }
        elseif ($this.Tag -eq "auto") { $this.BackColor = $autoSelect }
        else { $this.BackColor = $manualSelect }
    }.GetNewClosure())

    $null = $form.Controls.Add($card)
    $roleCards[$r.role] = $card
}

# Layout: Auto full width, then 2x2 grid
$col2X = [int](20 + $cardW + $cardGap)
$roleCards["auto"].Location = New-Object System.Drawing.Point(20, $y)

$y = [int]($y + $cardH + $cardGap)
$roleCards["planner"].Location = New-Object System.Drawing.Point(20, $y)
$roleCards["executor"].Location = New-Object System.Drawing.Point($col2X, $y)

$y = [int]($y + $cardH + $cardGap)
$roleCards["coder"].Location = New-Object System.Drawing.Point(20, $y)
$roleCards["validator"].Location = New-Object System.Drawing.Point($col2X, $y)

# Default: Auto selected
$roleCards["auto"].BackColor = $autoSelect

$y += $cardH + 14

# --- Separator ---
$sep3 = New-Object System.Windows.Forms.Panel
$sep3.Size = New-Object System.Drawing.Size(540, 1)
$sep3.Location = New-Object System.Drawing.Point(20, $y)
$sep3.BackColor = $borderColor
$null = $form.Controls.Add($sep3)

$y += 10

# --- Routing Preview ---
$previewLbl = New-Object System.Windows.Forms.Label
$previewLbl.Text = "Routing Preview"
$previewLbl.Location = New-Object System.Drawing.Point(20, $y)
$previewLbl.Size = New-Object System.Drawing.Size(120, 18)
$previewLbl.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$previewLbl.ForeColor = $dimColor
$null = $form.Controls.Add($previewLbl)

$previewInput = New-Object System.Windows.Forms.TextBox
$previewInput.Size = New-Object System.Drawing.Size(360, 28)
$previewInput.Location = New-Object System.Drawing.Point(20, ($y + 20))
$previewInput.BackColor = $inputBgColor
$previewInput.ForeColor = $textColor
$previewInput.Font = New-Object System.Drawing.Font("Consolas", 9)
$previewInput.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
$previewInput.Text = "What is Python?"
$null = $form.Controls.Add($previewInput)

$previewBtn = New-Object System.Windows.Forms.Button
$previewBtn.Text = "Test"
$previewBtn.Size = New-Object System.Drawing.Size(70, 28)
$previewBtn.Location = New-Object System.Drawing.Point(390, ($y + 20))
$previewBtn.FlatStyle = "Flat"
$previewBtn.BackColor = $cardColor
$previewBtn.ForeColor = $textColor
$previewBtn.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$previewBtn.FlatAppearance.BorderColor = $borderColor
$previewBtn.Cursor = [System.Windows.Forms.Cursors]::Hand
$null = $form.Controls.Add($previewBtn)

$previewResult = New-Object System.Windows.Forms.Label
$previewResult.Text = "GLM-5.1 (validator)"
$previewResult.Location = New-Object System.Drawing.Point(470, ($y + 24))
$previewResult.AutoSize = $true
$previewResult.Font = New-Object System.Drawing.Font("Consolas", 8.5, [System.Drawing.FontStyle]::Bold)
$previewResult.ForeColor = $greenColor
$null = $form.Controls.Add($previewResult)

$previewBtn.Add_Click({
    $msg = $previewInput.Text
    if (-not $msg) { $previewResult.Text = ""; return }
    $route = Get-Route -Message $msg
    $previewResult.Text = $routeLabels[$route]
    $previewResult.ForeColor = $greenColor
})

$previewInput.Add_KeyDown({
    if ($_.KeyCode -eq "Enter") { $previewBtn.PerformClick() }
})

$y += 56

# --- Launch Button ---
$launchBtn = New-Object System.Windows.Forms.Button
$launchBtn.Text = "LAUNCH"
$launchBtn.Size = New-Object System.Drawing.Size(540, 44)
$launchBtn.Location = New-Object System.Drawing.Point(20, $y)
$launchBtn.FlatStyle = "Flat"
$launchBtn.BackColor = $btnColor
$launchBtn.ForeColor = [System.Drawing.Color]::FromArgb(10, 10, 10)
$launchBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$launchBtn.Cursor = [System.Windows.Forms.Cursors]::Hand
$launchBtn.FlatAppearance.BorderColor = $btnColor

$launchBtn.Add_MouseEnter({ $this.BackColor = [System.Drawing.Color]::FromArgb(80, 200, 255) })
$launchBtn.Add_MouseLeave({ $this.BackColor = $btnColor })

$launchBtn.Add_Click({
    $path = $folderCombo.Text
    if (-not $path -or -not (Test-Path $path)) {
        [System.Windows.Forms.MessageBox]::Show("Select a valid project folder.", "Error", "OK", "Warning")
        return
    }

    $roleObj = $roles | Where-Object { $_.role -eq $selectedRole }
    if (-not $roleObj) {
        [System.Windows.Forms.MessageBox]::Show("Select a role.", "Error", "OK", "Warning")
        return
    }

    $modelName = $roleObj.model
    $modelLbl = $roleObj.label

    # Save folder history
    $newHistory = @($path) + ($history | Where-Object { $_ -ne $path })
    $newHistory = $newHistory | Select-Object -First $maxHistory
    $newHistory | Set-Content $historyFile

    Write-Host "Launching: $modelName ($modelLbl) in $path"

    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-File", $scriptPath,
        "-StartPath", $path,
        "-Model", $modelName,
        "-ModelLabel", $modelLbl
    )

    $form.Close()
})
$null = $form.Controls.Add($launchBtn)

$y += 54

# --- Footer ---
$footer = New-Object System.Windows.Forms.Label
$footer.Text = "Ollama Cloud  |  LiteLLM Proxy :4000  |  Auto-switch enabled"
$footer.Location = New-Object System.Drawing.Point(20, $y)
$footer.Size = New-Object System.Drawing.Size(540, 18)
$footer.Font = New-Object System.Drawing.Font("Consolas", 8)
$footer.ForeColor = [System.Drawing.Color]::FromArgb(90, 90, 100)
$null = $form.Controls.Add($footer)

# --- Final size ---
$form.ClientSize = New-Object System.Drawing.Size(580, ($y + 22))

[System.Windows.Forms.Application]::Run($form)