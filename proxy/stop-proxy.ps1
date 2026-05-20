# Stop a background analytics proxy process
$procs = Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" |
    Where-Object { $_.CommandLine -like '*proxy.mjs*' }

if ($procs) {
    $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Write-Host "Analytics proxy stopped." -ForegroundColor Green
} else {
    Write-Host "No analytics proxy process found." -ForegroundColor Yellow
}