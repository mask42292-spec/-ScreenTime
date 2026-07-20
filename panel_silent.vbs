Set WshShell = CreateObject("WScript.Shell")
dirPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

port = 19999
portFile = dirPath & "\.port"
Set fso = CreateObject("Scripting.FileSystemObject")
If fso.FileExists(portFile) Then
    Set f = fso.OpenTextFile(portFile, 1)
    If Not f.AtEndOfStream Then port = f.ReadLine
    f.Close
End If

WshShell.Run "wscript.exe """ & dirPath & "\panel_start.vbs""", 0, False
WScript.Sleep 3000
WshShell.Run "http://localhost:" & port
