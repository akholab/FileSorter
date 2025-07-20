' Smart File Indexer - Hidden VBS Launcher
' This VBScript starts the program without any visible windows

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get the directory where this script is located
strScriptPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strScriptPath

' Check if pythonw.exe is available
Set objExec = objShell.Exec("pythonw.exe --version")
If objExec.ExitCode <> 0 Then
    ' Try with python.exe if pythonw is not available
    objShell.Run "python.exe launcher.py", 0, False
Else
    ' Use pythonw.exe for completely hidden execution
    objShell.Run "pythonw.exe launcher.py", 0, False
End If

Set objShell = Nothing
Set objFSO = Nothing 