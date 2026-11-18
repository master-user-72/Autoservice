Set args = WScript.Arguments
bat = args(0)
mode = args(1)
command = "cmd /c """ & bat & """ hidden " & mode
CreateObject("WScript.Shell").Run command, 0, True
