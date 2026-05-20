Set objFSO  = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("WScript.Shell")

scriptDir  = objFSO.GetParentFolderName(WScript.ScriptFullName)
ps1Path    = scriptDir & "\launcher.ps1"

' Build the command: powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\path\to\launcher.ps1"
cmdLine = "powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1Path & """"

objShell.Run cmdLine, 0, False