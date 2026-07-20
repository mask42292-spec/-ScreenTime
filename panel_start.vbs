Set WshShell = CreateObject("WScript.Shell")
dirPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
batPath = dirPath & "\panel_start.bat"
WshShell.Run """" & batPath & """", 0, False
