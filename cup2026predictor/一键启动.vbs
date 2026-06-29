' World Cup Predictor - Silent Launcher
' Just starts launcher.py with hidden window, launcher does all the work

Q = Chr(34)
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strDir = fso.GetParentFolderName(WScript.ScriptFullName)
strPy = "C:\Users\MACHENIKE\AppData\Local\Python\pythoncore-3.14-64\python.exe"
strLauncher = strDir & "\launcher.py"

WshShell.CurrentDirectory = strDir

' Launch with hidden window
WshShell.Run Q & strPy & Q & " " & Q & strLauncher & Q, 0, False
