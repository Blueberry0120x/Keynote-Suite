' RemoteController.vbs -- Hidden launcher for RemoteController.cmd
' Runs the watchdog CMD without a visible console window.
' Place a shortcut to this file in shell:startup for auto-start on login.

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Resolve path relative to this script's location
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
cmdPath = fso.BuildPath(scriptDir, "RemoteController.cmd")

' Launch hidden (0 = hidden window, False = don't wait)
WshShell.Run "cmd /c """ & cmdPath & """", 0, False
