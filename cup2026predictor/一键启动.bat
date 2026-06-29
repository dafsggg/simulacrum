@echo off
for %%I in ("%~dp0.") do set "DIR=%%~sI"
cd /d "%DIR%"

start "" /min "C:\Users\MACHENIKE\AppData\Local\Python\pythoncore-3.14-64\python.exe" "launcher.py"

exit
