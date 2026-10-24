' Launch the Jupiter wallpaper without a console window.
' Used by the Startup entry created by python/autostart.py; double-clicking
' this file works too. Delay is in milliseconds (override with the
' JUPITER_START_DELAY_MS environment variable).
Option Explicit

Dim fso, shell, root, delayMs, configured
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' Project root = parent of the scripts folder that holds this file.
root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))

' At logon the desktop (Progman/WorkerW) and Chrome need a moment to be ready.
delayMs = 20000
configured = shell.Environment("Process")("JUPITER_START_DELAY_MS")
If IsNumeric(configured) And Len(configured) > 0 Then delayMs = CLng(configured)
WScript.Sleep delayMs

shell.CurrentDirectory = root
' 0 = hidden window, False = do not wait for it to exit.
shell.Run """" & root & "\scripts\start_wallpaper.cmd""", 0, False
