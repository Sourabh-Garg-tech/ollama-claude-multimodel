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
    $history = Get-Content $historyFile | Where-Object { $_ -ne "" }
}
$lastPath = if ($history.Count -gt 0) { $history[0] } else { "" }

# --- Colors ---
$bgColor = [System.Drawing.Color]::FromArgb(30, 30, 30)
$cardColor = [System.Drawing.Color]::FromArgb(45, 45, 45)
$autoColor = [System.Drawing.Color]::FromArgb(0, 77, 64)
$textColor = [System.Drawing.Color]::White
$dimColor = [System.Drawing.Color]::FromArgb(160, 160, 160)
$accentColor = [System.Drawing.Color]::FromArgb(0, 180, 216)
$greenColor = [System.Drawing.Color]::FromArgb(76, 175, 80)
$borderColor = [System.Drawing.Color]::FromArgb(70, 70, 70)

# --- Form ---
$form = New-Object System.Windows.Forms.Form
$form.Text = "Multi-Model Router"
$form.Size = New-Object System.Drawing.Size(560, 500)
$form.StartPosition = "CenterScreen"
$form.TopMost = $true
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.BackColor = $bgColor
$form.ForeColor = $textColor

# --- Header ---
$header = New-Object System.Windows.Forms.Label
$header.Text = "Auto-switch: picks the best model per request"
$header.Location = New-Object System.Drawing.Point(15, 12)
$header.Size = New-Object System.Drawing.Size(530, 22)
$header.ForeColor = $accentColor
$header.Font = New-Object System.Drawing.Font("Consolas", 10, [System.Drawing.FontStyle]::Bold)
$null = $form.Controls.Add($header)

# --- Folder Label ---
$folderLabel = New-Object System.Windows.Forms.Label
$folderLabel.Text = "Project Folder"
$folderLabel.Location = New-Object System.Drawing.Point(15, 44)
$folderLabel.AutoSize = $true
$folderLabel.ForeColor = $dimColor
$null = $form.Controls.Add($folderLabel)

# --- Folder ComboBox ---
$folderCombo = New-Object System.Windows.Forms.ComboBox
$folderCombo.Size = New-Object System.Drawing.Size(420, 25)
$folderCombo.Location = New-Object System.Drawing.Point(15, 62)
$folderCombo.DropDownStyle = "DropDown"
$folderCombo.Items.AddRange($history)
$folderCombo.Text = $lastPath
$folderCombo.BackColor = $cardColor
$folderCombo.ForeColor = $textColor
$null = $form.Controls.Add($folderCombo)

# --- Browse Button ---
$browse = New-Object System.Windows.Forms.Button
$browse.Text = "Browse"
$browse.Location = New-Object System.Drawing.Point(445, 61)
$browse.Size = New-Object System.Drawing.Size(90, 27)
$browse.FlatStyle = "Flat"
$browse.BackColor = $cardColor
$browse.ForeColor = $textColor
$browse.FlatAppearance.BorderColor = $borderColor
$browse.Add_Click({
    $fb = New-Object System.Windows.Forms.FolderBrowserDialog
    if ($fb.ShowDialog() -eq "OK") { $folderCombo.Text = $fb.SelectedPath }
})
$null = $form.Controls.Add($browse)

# --- Separator ---
$sep = New-Object System.Windows.Forms.Label
$sep.Text = ""
$sep.Location = New-Object System.Drawing.Point(15, 96)
$sep.Size = New-Object System.Drawing.Size(520, 1)
$sep.BackColor = $borderColor
$null = $form.Controls.Add($sep)

# --- Role Cards ---
$roleCards = @{}
$selectedRole = "auto"

foreach ($r in $roles) {
    $card = New-Object System.Windows.Forms.Panel
    $card.Size = New-Object System.Drawing.Size(250, 70)
    $card.BackColor = $cardColor
    $card.BorderStyle = [System.Windows.Forms.BorderStyle]::None
    $card.Tag = $r.role

    $lbl = New-Object System.Windows.Forms.Label
    $lbl.Text = "$($r.label.ToUpper())  $($r.tag)"
    $lbl.Location = New-Object System.Drawing.Point(10, 6)
    $lbl.Size = New-Object System.Drawing.Size(230, 18)
    $lbl.Font = New-Object System.Drawing.Font("Consolas", 9, [System.Drawing.FontStyle]::Bold)
    $lbl.ForeColor = $accentColor
    $lbl.Tag = "label"
    $null = $card.Controls.Add($lbl)

    $desc = New-Object System.Windows.Forms.Label
    $desc.Text = $r.description
    $desc.Location = New-Object System.Drawing.Point(10, 26)
    $desc.Size = New-Object System.Drawing.Size(230, 28)
    $desc.ForeColor = $dimColor
    $desc.Tag = "desc"
    $null = $card.Controls.Add($desc)

    if ($r.role -eq "auto") {
        $cost = New-Object System.Windows.Forms.Label
        $cost.Text = "Routes automatically by request type"
        $cost.Location = New-Object System.Drawing.Point(10, 54)
        $cost.Size = New-Object System.Drawing.Size(230, 14)
        $cost.Font = New-Object System.Drawing.Font("Consolas", 8)
        $cost.ForeColor = $greenColor
        $cost.Tag = "cost"
        $null = $card.Controls.Add($cost)
    } else {
        $cost = New-Object System.Windows.Forms.Label
        $cost.Text = "$($r.cost)  |  $($r.speed) tok/s"
        $cost.Location = New-Object System.Drawing.Point(10, 54)
        $cost.Size = New-Object System.Drawing.Size(230, 14)
        $cost.Font = New-Object System.Drawing.Font("Consolas", 8)
        $cost.ForeColor = $greenColor
        $cost.Tag = "cost"
        $null = $card.Controls.Add($cost)
    }

    $card.Add_Click({
        $script:selectedRole = $this.Tag
        foreach ($c in $roleCards.Values) {
            $c.BackColor = $cardColor
        }
        $this.BackColor = if ($this.Tag -eq "auto") { $autoColor } else { [System.Drawing.Color]::FromArgb(0, 100, 120) }
    }.GetNewClosure())

    $null = $form.Controls.Add($card)
    $roleCards[$r.role] = $card
}

# Layout: Auto card full width on top, then 2x2 grid for manual roles
$roleCards["auto"].Location = New-Object System.Drawing.Point(15, 104)
$roleCards["auto"].Size = New-Object System.Drawing.Size(520, 70)

$manualY = 182
$roleCards["planner"].Location = New-Object System.Drawing.Point(15, $manualY)
$roleCards["executor"].Location = New-Object System.Drawing.Point(285, $manualY)
$roleCards["coder"].Location = New-Object System.Drawing.Point(15, $manualY + 78)
$roleCards["validator"].Location = New-Object System.Drawing.Point(285, $manualY + 78)

# Default: Auto selected
$roleCards["auto"].BackColor = $autoColor

# --- Info Label ---
$infoLabel = New-Object System.Windows.Forms.Label
$infoLabel.Text = "Auto: questions -> GLM, code -> Kimi, planning -> V4 Pro, else -> V4 Flash"
$infoLabel.Location = New-Object System.Drawing.Point(15, 340)
$infoLabel.Size = New-Object System.Drawing.Size(520, 18)
$infoLabel.ForeColor = [System.Drawing.Color]::FromArgb(100, 100, 100)
$infoLabel.Font = New-Object System.Drawing.Font("Consolas", 8)
$null = $form.Controls.Add($infoLabel)

# --- Launch Button ---
$launch = New-Object System.Windows.Forms.Button
$launch.Text = "Launch"
$launch.Size = New-Object System.Drawing.Size(520, 40)
$launch.Location = New-Object System.Drawing.Point(15, 365)
$launch.FlatStyle = "Flat"
$launch.BackColor = $accentColor
$launch.ForeColor = $textColor
$launch.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$launch.Cursor = [System.Windows.Forms.Cursors]::Hand
$launch.FlatAppearance.BorderColor = $accentColor

$launch.Add_Click({
    $path = $folderCombo.Text
    if (-not (Test-Path $path)) {
        [System.Windows.Forms.MessageBox]::Show("Invalid folder path.", "Error")
        return
    }

    $roleObj = $roles | Where-Object { $_.role -eq $selectedRole }
    if (-not $roleObj) {
        [System.Windows.Forms.MessageBox]::Show("Select a role.", "Error")
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

$null = $form.Controls.Add($launch)

# --- Status Bar ---
$statusBar = New-Object System.Windows.Forms.Label
$statusBar.Text = "Ollama Cloud  |  Auto-switch enabled  |  LiteLLM Proxy :4000"
$statusBar.Location = New-Object System.Drawing.Point(15, 415)
$statusBar.Size = New-Object System.Drawing.Size(520, 18)
$statusBar.ForeColor = [System.Drawing.Color]::FromArgb(100, 100, 100)
$statusBar.Font = New-Object System.Drawing.Font("Consolas", 8)
$null = $form.Controls.Add($statusBar)

# --- Run ---
$form.Size = New-Object System.Drawing.Size(560, 470)
[System.Windows.Forms.Application]::Run($form)