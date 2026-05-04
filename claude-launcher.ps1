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
    [System.Windows.Forms.MessageBox]::Show("models.json not found at: $modelsPath", "Error")
    exit 1
}
$modelsConfig = Get-Content $modelsPath -Raw | ConvertFrom-Json
$models = $modelsConfig.models

# --- Load History ---
$history = @()
if (Test-Path $historyFile) {
    $history = Get-Content $historyFile | Where-Object { $_ -ne "" }
}
$lastPath = if ($history.Count -gt 0) { $history[0] } else { "" }

# --- Form ---
$form = New-Object System.Windows.Forms.Form
$form.Text = "Claude Launcher"
$form.Size = New-Object System.Drawing.Size(520, 420)
$form.StartPosition = "CenterScreen"
$form.TopMost = $true
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

# --- Folder Label ---
$folderLabel = New-Object System.Windows.Forms.Label
$folderLabel.Text = "Project Folder:"
$folderLabel.Location = New-Object System.Drawing.Point(10, 8)
$folderLabel.AutoSize = $true
$null = $form.Controls.Add($folderLabel)

# --- Folder ComboBox ---
$folderCombo = New-Object System.Windows.Forms.ComboBox
$folderCombo.Size = New-Object System.Drawing.Size(380, 25)
$folderCombo.Location = New-Object System.Drawing.Point(10, 28)
$folderCombo.DropDownStyle = "DropDown"
$folderCombo.Items.AddRange($history)
$folderCombo.Text = $lastPath
$null = $form.Controls.Add($folderCombo)

# --- Browse Button ---
$browse = New-Object System.Windows.Forms.Button
$browse.Text = "Browse"
$browse.Location = New-Object System.Drawing.Point(400, 28)
$browse.Size = New-Object System.Drawing.Size(100, 25)

$browse.Add_Click({
    $folderBrowser = New-Object System.Windows.Forms.FolderBrowserDialog
    if ($folderBrowser.ShowDialog() -eq "OK") {
        $folderCombo.Text = $folderBrowser.SelectedPath
    }
})

$null = $form.Controls.Add($browse)

# --- Task Description Label ---
$taskLabel = New-Object System.Windows.Forms.Label
$taskLabel.Text = "What are you working on? (optional - used for smart model suggestion)"
$taskLabel.Location = New-Object System.Drawing.Point(10, 62)
$taskLabel.AutoSize = $true
$null = $form.Controls.Add($taskLabel)

# --- Task Description TextBox ---
$taskBox = New-Object System.Windows.Forms.TextBox
$taskBox.Multiline = $true
$taskBox.Size = New-Object System.Drawing.Size(490, 50)
$taskBox.Location = New-Object System.Drawing.Point(10, 82)
$taskBox.ScrollBars = "Vertical"
$null = $form.Controls.Add($taskBox)

# --- Suggest Button ---
$suggest = New-Object System.Windows.Forms.Button
$suggest.Text = "Suggest Model"
$suggest.Location = New-Object System.Drawing.Point(10, 135)
$suggest.Size = New-Object System.Drawing.Size(120, 25)

$suggest.Add_Click({
    $desc = $taskBox.Text.Trim()
    if ($desc -eq "") {
        [System.Windows.Forms.MessageBox]::Show("Enter a task description first.", "Suggest Model")
        return
    }

    $pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    $classifier = Join-Path $PSScriptRoot "smart_router\classifier.py"

    if (-not (Test-Path $pythonExe)) {
        [System.Windows.Forms.MessageBox]::Show("Python virtual environment not found. Run launch-claude.ps1 once to set it up.", "Error")
        return
    }

    try {
        $tmpPy = [System.IO.Path]::GetTempFileName() + ".py"
        @"
import sys
sys.path.insert(0, 'smart_router')
from classifier import classify_description
print(classify_description(r'''$desc'''))
"@ | Set-Content -Path $tmpPy -Encoding UTF8

        $output = & $pythonExe $tmpPy 2>$null
        Remove-Item $tmpPy -ErrorAction SilentlyContinue
        $classification = $output.Trim()

        # Find best matching model in the loaded list
        $targetModel = switch ($classification) {
            "planning"   { "deepseek-v4-pro:cloud" }
            "complex"    { "deepseek-v4-pro:cloud" }
            "code"       { "kimi-k2.6:cloud" }
            "lookup"     { "glm-5.1:cloud" }
            default      { "deepseek-v4-flash:cloud" }
        }

        $foundIdx = -1
        for ($i = 0; $i -lt $models.Count; $i++) {
            if ($models[$i].name -eq $targetModel) {
                $foundIdx = $i
                break
            }
        }

        if ($foundIdx -ge 0) {
            $modelCombo.SelectedIndex = $foundIdx
            $suggestLabel.Text = "Recommended: $($models[$foundIdx].label) for '$classification' tasks"
            $suggestLabel.ForeColor = [System.Drawing.Color]::Green
        } else {
            $suggestLabel.Text = "Classification: $classification - no exact match in model list"
            $suggestLabel.ForeColor = [System.Drawing.Color]::Orange
        }
    } catch {
        $suggestLabel.Text = "Suggestion failed: $_"
        $suggestLabel.ForeColor = [System.Drawing.Color]::Red
    }
})

$null = $form.Controls.Add($suggest)

# --- Suggestion Result Label ---
$suggestLabel = New-Object System.Windows.Forms.Label
$suggestLabel.Text = ""
$suggestLabel.Location = New-Object System.Drawing.Point(140, 140)
$suggestLabel.Size = New-Object System.Drawing.Size(360, 20)
$suggestLabel.AutoSize = $false
$null = $form.Controls.Add($suggestLabel)

# --- Model Label ---
$modelLabel = New-Object System.Windows.Forms.Label
$modelLabel.Text = "Model:"
$modelLabel.Location = New-Object System.Drawing.Point(10, 170)
$modelLabel.AutoSize = $true
$null = $form.Controls.Add($modelLabel)

# --- Model ComboBox ---
$modelCombo = New-Object System.Windows.Forms.ComboBox
$modelCombo.Size = New-Object System.Drawing.Size(490, 25)
$modelCombo.Location = New-Object System.Drawing.Point(10, 190)
$modelCombo.DropDownStyle = "DropDownList"

foreach ($m in $models) {
    $null = $modelCombo.Items.Add("$($m.label) ($($m.name))")
}
if ($modelCombo.Items.Count -gt 0) {
    $modelCombo.SelectedIndex = 1  # Default to kimi-k2.6 (implementation)
}

$null = $form.Controls.Add($modelCombo)

# --- Model Description ---
$descLabel = New-Object System.Windows.Forms.Label
$descLabel.Text = ""
$descLabel.Location = New-Object System.Drawing.Point(10, 218)
$descLabel.Size = New-Object System.Drawing.Size(490, 40)
$descLabel.ForeColor = [System.Drawing.Color]::Gray
$null = $form.Controls.Add($descLabel)

$modelCombo.Add_SelectedIndexChanged({
    $idx = $modelCombo.SelectedIndex
    if ($idx -ge 0 -and $idx -lt $models.Count) {
        $descLabel.Text = $models[$idx].description
    }
})

# Trigger initial description
if ($modelCombo.SelectedIndex -ge 0) {
    $descLabel.Text = $models[$modelCombo.SelectedIndex].description
}

# --- Launch Button ---
$launch = New-Object System.Windows.Forms.Button
$launch.Text = "Launch"
$launch.Size = New-Object System.Drawing.Size(200, 35)
$launch.Location = New-Object System.Drawing.Point(155, 275)

$launch.Add_Click({
    $path = $folderCombo.Text
    $modelIdx = $modelCombo.SelectedIndex

    if (-not (Test-Path $path)) {
        [System.Windows.Forms.MessageBox]::Show("Invalid folder path.", "Error")
        return
    }

    if ($modelIdx -lt 0) {
        [System.Windows.Forms.MessageBox]::Show("Please select a model.", "Error")
        return
    }

    $modelName = $models[$modelIdx].name
    $modelLbl = $models[$modelIdx].label

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

# --- Run ---
[System.Windows.Forms.Application]::Run($form)
